"""Closed JSON protocol; parsing never returns input in an error message."""

import json
import re
import unicodedata
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def strict_json(raw: bytes | str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("invalid JSON")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("invalid JSON")

    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=invalid)
        if not isinstance(data, dict):
            raise ValueError("invalid JSON")
        # Also rejects lone surrogates before DB/logging/HTTP serialization.
        canonical(data)
        return data
    except (UnicodeError, RecursionError, TypeError) as exc:
        raise ValueError("invalid JSON") from exc


def canonical(value) -> bytes:
    def standard(item):
        if type(item) is dict:
            if any(type(k) is not str for k in item):
                raise ValueError("invalid JSON")
            for child in item.values():
                standard(child)
        elif type(item) is list:
            for child in item:
                standard(child)
        elif type(item) not in {str, int, bool, type(None)}:
            raise ValueError("invalid JSON")

    standard(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def text_value(value: str) -> str:
    if not value.strip() or any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in value):
        raise ValueError("invalid text")
    return value


def text_type(maximum):
    return Annotated[
        str,
        StringConstraints(strict=True, min_length=1, max_length=maximum),
        AfterValidator(text_value),
    ]


Fingerprint = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ErrorCode = Literal[
    "interrupted",
    "timeout",
    "cli_failed",
    "output_limit",
    "invalid_result",
    "policy_denied",
    "capability_unavailable",
    "profile_mismatch",
]
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @classmethod
    def from_json(cls, data: dict):
        # JSON mode accepts UUID/aware ISO strings, but strict scalars stay strict.
        return cls.model_validate_json(canonical(data))


class BridgeResult(Closed):
    summary: text_type(4000)
    proposed_actions: list[text_type(1000)] = Field(max_length=12)
    missing_context: list[text_type(1000)] = Field(max_length=12)
    evidence_refs: list[text_type(2048)] = Field(max_length=12)
    warnings: list[text_type(1000)] = Field(max_length=12)

    def for_run(self, url: str, maximum: int):
        if self.evidence_refs != [url]:
            raise ValueError("invalid evidence")
        if len(canonical(self.model_dump(mode="json"))) > maximum:
            raise ValueError("result too large")
        return self


class BridgeRunView(Closed):
    id: UUID
    requested_slack_permalink: str
    profile_id: str
    profile_version: int
    profile_fingerprint: Fingerprint
    status: RunStatus
    cancel_requested: bool
    created_at: AwareDatetime
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    deadline_at: AwareDatetime
    result: BridgeResult | None
    error_code: ErrorCode | None


class CreateRun(Closed):
    idempotency_key: UUID
    requested_slack_permalink: text_type(2048)


class BridgeClaim(Closed):
    run: BridgeRunView
    lease_token: UUID
    lease_expires_at: AwareDatetime


class Empty(Closed):
    pass


class ClaimInput(Closed):
    runner_id: UUID
    profile_fingerprint: Fingerprint
    cli_version: Annotated[str, StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    cli_sha256: Digest
    policy_verified: Literal[True]

    @model_validator(mode="before")
    @classmethod
    def real_boolean(cls, value):
        if type(value.get("policy_verified")) is not bool:
            raise ValueError("invalid capability")
        return value


class LeaseInput(Closed):
    runner_id: UUID
    lease_token: UUID
    profile_fingerprint: Fingerprint


class CompleteInput(LeaseInput):
    outcome: Literal["succeeded", "failed", "cancelled"]
    result: BridgeResult | None
    error_code: ErrorCode | None

    @model_validator(mode="after")
    def outcome_shape(self):
        if self.outcome == "succeeded":
            valid = self.result is not None and self.error_code is None
        elif self.outcome == "failed":
            valid = self.result is None and self.error_code is not None
        else:
            valid = self.result is None and self.error_code is None
        if not valid:
            raise ValueError("invalid outcome")
        return self


def slack_url(value: str, hosts: list[str]) -> str:
    # Byte-exact ASCII grammar: no normalization, ports, escapes, query or fetch.
    match = re.fullmatch(
        r"https://([a-z0-9-]+\.slack\.com)/archives/([A-Za-z0-9]+)/p([0-9]+)", value
    )
    if not match or len(value) > 2048 or match[1] not in hosts:
        raise ValueError("invalid permalink")
    return value
