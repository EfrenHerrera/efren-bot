"""Bridge-only ASGI boundary. Guards run before parsing routes or touching SQL."""

import hmac
import re
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from efren_bot.bridge.contracts import (
    ClaimInput,
    CompleteInput,
    CreateRun,
    Empty,
    LeaseInput,
    strict_json,
)
from efren_bot.bridge.service import BridgeError, BridgeService

HOSTS = {"127.0.0.1:5173", "localhost:5173", "127.0.0.1:8000", "localhost:8000"}
ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


def error_response(code, status):
    # The closed code is also the message: no arbitrary input/exception ever echoed.
    return JSONResponse(
        {"error": {"code": code, "message": code}},
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


class BridgeBoundary:
    def __init__(self, app, service):
        self.app, self.service = app, service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not (
            scope["path"] == "/api/bridge" or scope["path"].startswith("/api/bridge/")
        ):
            return await self.app(scope, receive, send)

        async def no_cache(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    (k, v) for k, v in message["headers"] if k.lower() != b"cache-control"
                ] + [(b"cache-control", b"no-store")]
            await send(message)

        try:
            headers = {}
            for name, value in scope["headers"]:
                headers.setdefault(name.lower(), []).append(value.decode("latin-1"))

            def one(name, status=403):
                values = headers.get(name, [])
                if len(values) > 1:
                    raise BridgeError("forbidden" if status == 403 else "unauthorized", status)
                return values[0] if values else None

            host, origin, site = one(b"host"), one(b"origin"), one(b"sec-fetch-site")
            runner = scope["path"].startswith("/api/bridge/runner/")
            if host not in HOSTS or site and site.lower() == "cross-site":
                raise BridgeError("forbidden", 403)
            is_status = scope["path"] == "/api/bridge/status" and scope["method"] == "GET"
            implicit_origin = False
            if runner:
                if host != "127.0.0.1:8000" or origin is not None:
                    raise BridgeError("forbidden", 403)
            elif origin not in ORIGINS:
                implicit_origin = (
                    origin is None
                    and scope["method"] == "GET"
                    and site is not None
                    and site.lower() == "same-origin"
                    and host in {"127.0.0.1:5173", "localhost:5173"}
                )
                if not implicit_origin:
                    raise BridgeError("forbidden", 403)
            # Public status uses the same Host/Origin guards, including the web GET fallback.
            if not is_status:
                auth, token = one(b"authorization", 401), self.service.token()
                supplied = auth[7:] if auth and auth.startswith("Bearer ") else ""
                if (
                    token is None
                    or re.fullmatch(r"[0-9a-f]{64}", supplied) is None
                    or not hmac.compare_digest(supplied, token)
                ):
                    raise BridgeError("unauthorized", 401)
            if scope["query_string"]:
                raise BridgeError("invalid_request", 422)
            if scope["method"] == "POST":
                media = one(b"content-type", 415)
                if (
                    media is None
                    or re.fullmatch(
                        r"application/json(?:\s*;\s*charset=utf-8)?", media, re.IGNORECASE
                    )
                    is None
                ):
                    raise BridgeError("unsupported_media_type", 415)
                maximum = 4096 if scope["path"] == "/api/bridge/runs" else 65536
                length = one(b"content-length", 413)
                if length and (
                    len(length) > 8
                    or not length.isascii()
                    or not length.isdigit()
                    or int(length) > maximum
                ):
                    raise BridgeError("body_too_large", 413)
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] != "http.request":
                        raise BridgeError("invalid_request", 422)
                    body.extend(message.get("body", b""))
                    if len(body) > maximum:
                        raise BridgeError("body_too_large", 413)
                    if not message.get("more_body", False):
                        break
                try:
                    data = strict_json(bytes(body))
                except (ValueError, RecursionError) as exc:
                    raise BridgeError("invalid_request", 422) from exc
                scope.setdefault("state", {})["bridge_json"] = data
            await self.app(scope, receive, no_cache)
        except BridgeError as exc:
            await error_response(exc.code, exc.status)(scope, receive, no_cache)


def install_bridge(app, settings, sessions):
    service = BridgeService(settings, sessions)
    app.add_middleware(BridgeBoundary, service=service)
    router = APIRouter(prefix="/api/bridge")

    def parsed(request, cls):
        try:
            return cls.from_json(request.state.bridge_json)
        except (ValueError, ValidationError) as exc:
            raise BridgeError("invalid_request", 422) from exc

    def identifier(value):
        try:
            return UUID(value)
        except ValueError as exc:
            raise BridgeError("invalid_request", 422) from exc

    def response(call, status=200):
        try:
            result = call()
            from fastapi.encoders import jsonable_encoder

            return JSONResponse(jsonable_encoder(result), status_code=status)
        except BridgeError as exc:
            return error_response(exc.code, exc.status)
        except SQLAlchemyError:
            return error_response("database_unavailable", 503)

    @router.get("/status")
    def status():
        return response(service.status)

    @router.post("/runs")
    def create(request: Request):
        def call():
            run, new = service.create(parsed(request, CreateRun))
            return {"run": run}, new

        try:
            payload, new = call()
            return response(lambda: payload, 202 if new else 200)
        except BridgeError as exc:
            return error_response(exc.code, exc.status)
        except SQLAlchemyError:
            return error_response("database_unavailable", 503)

    @router.get("/runs/{run_id}")
    def read(run_id: str):
        return response(lambda: {"run": service.read(identifier(run_id))})

    @router.post("/runs/{run_id}/cancel")
    def cancel(run_id: str, request: Request):
        def call():
            parsed(request, Empty)
            return {"run": service.read(identifier(run_id), cancel=True)}

        return response(call)

    @router.post("/runner/claim")
    def claim(request: Request):
        return response(lambda: {"claim": service.claim(parsed(request, ClaimInput))})

    @router.post("/runner/runs/{run_id}/heartbeat")
    def heartbeat(run_id: str, request: Request):
        return response(lambda: service.lease(identifier(run_id), parsed(request, LeaseInput)))

    @router.post("/runner/runs/{run_id}/complete")
    def complete(run_id: str, request: Request):
        return response(
            lambda: service.lease(identifier(run_id), parsed(request, CompleteInput), complete=True)
        )

    app.include_router(router)
