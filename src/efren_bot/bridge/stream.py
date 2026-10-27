"""Bounded stream-json projection. Never retains assistant text or tool content."""

import json

from efren_bot.bridge.contracts import BridgeResult, canonical, strict_json

PARTIAL_WARNING = "Lectura de un único hilo; el contexto puede ser parcial."
THREAD_WARNING = (
    "Lectura acotada a una llamada y un máximo de 100 mensajes; puede faltar contexto. "
    "El enlace debe corresponder al mensaje padre del hilo."
)


class StreamFailure(ValueError):
    def __init__(self, code="invalid_result"):
        self.code = code
        super().__init__(code)


def event_json(raw):
    def pairs(items):
        data = {}
        for key, value in items:
            if key in data:
                raise StreamFailure()
            data[key] = value
        return data

    def invalid(value):
        raise StreamFailure()

    try:
        # CLI accounting metadata can contain floats. Only discarded metadata gets
        # this parser; tool arguments and final result use strict no-float JSON.
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if type(data) is not dict:
            raise StreamFailure()
        return data
    except (ValueError, UnicodeError, RecursionError, TypeError) as exc:
        raise StreamFailure() from exc


class StreamProjection:
    def __init__(self, profile, url):
        self.profile, self.url = profile, url
        self.buffer = bytearray()
        self.turns = set()
        self.tool_id = None
        self.tool_success = False
        self.result = None

    def feed(self, raw):
        self.buffer.extend(raw)
        if len(self.buffer) > self.profile.limits.max_stdout_bytes:
            raise StreamFailure("output_limit")
        while b"\n" in self.buffer:
            line, _, remaining = self.buffer.partition(b"\n")
            self.buffer = bytearray(remaining)
            self.event(event_json(bytes(line)))

    def event(self, event):
        if self.result is not None:
            raise StreamFailure()  # duplicated result or trailing stream
        if event.get("error") is not None:
            raise StreamFailure("cli_failed")
        kind = event.get("type")
        if kind == "assistant":
            message = event.get("message", {})
            identifier = message.get("id")
            if type(identifier) is not str or not identifier or len(identifier) > 256:
                raise StreamFailure()
            self.turns.add(identifier)
            if len(self.turns) > self.profile.limits.max_turns:
                raise StreamFailure("output_limit")
            for block in message.get("content", []):
                if block.get("type") != "tool_use":
                    continue  # no text/thinking retained
                if (
                    self.tool_id is not None
                    or block.get("name") != self.profile.connector.tool_name
                    or canonical(block.get("input")) != canonical(self.profile.arguments(self.url))
                    or type(block.get("id")) is not str
                    or not block["id"]
                ):
                    raise StreamFailure("policy_denied")
                self.tool_id = block["id"]
        elif kind == "user":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") != "tool_result":
                    continue
                if (
                    self.tool_success
                    or not self.tool_id
                    or block.get("tool_use_id") != self.tool_id
                    or block.get("is_error", False) is not False
                ):
                    raise StreamFailure("cli_failed")
                self.tool_success = True
        elif kind == "result":
            if (
                event.get("subtype") != "success"
                or event.get("is_error") is not False
                or not self.tool_success
                or type(event.get("result")) is not str
            ):
                raise StreamFailure("cli_failed")
            raw = event["result"].encode("utf-8")
            if len(raw) > self.profile.limits.max_result_bytes:
                raise StreamFailure("output_limit")
            try:
                result = BridgeResult.from_json(strict_json(raw))
                if PARTIAL_WARNING not in result.warnings:
                    result.warnings.append(PARTIAL_WARNING)
                if self.profile.schema_version == 2 and THREAD_WARNING not in result.warnings:
                    result.warnings.append(THREAD_WARNING)
                result = BridgeResult.from_json(result.model_dump(mode="json"))
                self.result = result.for_run(self.url, self.profile.limits.max_result_bytes)
            except ValueError as exc:
                raise StreamFailure() from exc
        elif kind == "system":
            if event.get("subtype") not in {
                "init",
                "hook_started",
                "hook_progress",
                "hook_response",
            }:
                raise StreamFailure()
            if event.get("subtype") == "hook_response" and (
                event.get("exit_code", 0) != 0 or event.get("outcome", "success") != "success"
            ):
                raise StreamFailure("policy_denied")
        else:
            raise StreamFailure()  # unsupported stream variants need review, not guessing

    def finish(self, budget):
        if self.buffer or self.result is None or not self.tool_success:
            raise StreamFailure()
        if (
            budget["violation"]
            or budget["used"] is not True
            or budget["tool_use_id"] != self.tool_id
        ):
            raise StreamFailure("policy_denied")
        return self.result
