import hmac
import secrets

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from efren_bot.bridge.contracts import strict_json
from efren_bot.collection.conversations import (
    ConversationDetail,
    ConversationList,
    ConversationSeen,
    ConversationService,
    GroupDelete,
    GroupSave,
)
from efren_bot.collection.inbox import AnnotationInput, DetailInput, InboxService, ListInput
from efren_bot.collection.service import CollectionError, CollectionService
from efren_bot.collection.sources import SourceInput, SourceService
from efren_bot.human.contracts import Decision as HumanDecision
from efren_bot.human.contracts import Selection as HumanSelection
from efren_bot.human.service import HumanService
from efren_bot.review.contracts import Action as ReviewAction
from efren_bot.review.contracts import DemoInput
from efren_bot.review.service import ReviewService
from efren_bot.support.contracts import CaseAction, Selection
from efren_bot.support.service import SupportService

HOSTS = {"127.0.0.1:5173", "localhost:5173", "127.0.0.1:8000", "localhost:8000"}
ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


def reply(data, status=200):
    return JSONResponse(
        jsonable_encoder(data), status_code=status, headers={"Cache-Control": "no-store"}
    )


class CollectionBoundary:
    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not (
            scope["path"] == "/api/collection" or scope["path"].startswith("/api/collection/")
        ):
            return await self.app(scope, receive, send)
        try:
            headers = {}
            for name, value in scope["headers"]:
                key = name.lower()
                if key in headers:
                    raise CollectionError("duplicate_header", 403)
                headers[key] = value.decode("latin-1")
            host, origin, site = (headers.get(k) for k in (b"host", b"origin", b"sec-fetch-site"))
            if host not in HOSTS or site == "cross-site" or headers.get(b"x-efren-local") != "1":
                raise CollectionError("forbidden", 403)
            if origin not in ORIGINS and not (
                origin is None
                and site == "same-origin"
                and host in {"127.0.0.1:5173", "localhost:5173"}
            ):
                raise CollectionError("forbidden", 403)
            if scope["query_string"]:
                raise CollectionError("invalid_request", 422)
            is_session = scope["path"] == "/api/collection/session" and scope["method"] == "GET"
            supplied = headers.get(b"x-collection-token", "")
            if not is_session and (
                not supplied.isascii() or not hmac.compare_digest(supplied, self.token)
            ):
                raise CollectionError("unauthorized", 401)
            if scope["method"] == "POST":
                if headers.get(b"content-type") != "application/json":
                    raise CollectionError("invalid_media_type", 415)
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] != "http.request":
                        raise CollectionError("invalid_request", 422)
                    body.extend(message.get("body", b""))
                    structured = scope["path"] in {
                        "/api/collection/inbox/list",
                        "/api/collection/inbox/annotate",
                        "/api/collection/inbox/thread",
                        "/api/collection/inbox/variants",
                        "/api/collection/sources/list",
                        "/api/collection/sources/save",
                        "/api/collection/conversations/list",
                        "/api/collection/conversations/detail",
                        "/api/collection/conversations/seen",
                        "/api/collection/conversations/group-save",
                        "/api/collection/conversations/group-delete",
                        "/api/collection/support/list",
                        "/api/collection/support/detail",
                        "/api/collection/support/act",
                        "/api/collection/reviews/list",
                        "/api/collection/reviews/detail",
                        "/api/collection/reviews/act",
                        "/api/collection/reviews/demo",
                        "/api/collection/human/list",
                        "/api/collection/human/detail",
                        "/api/collection/human/act",
                    }
                    if len(body) > (16384 if structured else 128):
                        raise CollectionError("body_too_large", 413)
                    if not message.get("more_body"):
                        break
                try:
                    parsed = strict_json(bytes(body))
                    valid = structured or parsed == {}
                    scope["collection_input"] = parsed
                except (ValueError, RecursionError):
                    valid = False
                if not valid:
                    raise CollectionError("invalid_request", 422)
            await self.app(scope, receive, send)
        except CollectionError as error:
            await reply({"error": error.code}, error.status)(scope, receive, send)


def install_collection(app, sessions):
    service = CollectionService(sessions)
    token = secrets.token_urlsafe(32)
    app.add_middleware(CollectionBoundary, token=token)
    router = APIRouter(prefix="/api/collection")

    @router.get("/session")
    def session():
        return reply({"token": token})

    @router.get("/status")
    def status():
        try:
            return reply(service.status())
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    @router.post("/inbox/{operation}")
    def inbox(operation: str, request: Request):
        try:
            data = request.scope["collection_input"]
            store = InboxService(sessions)
            if operation == "list":
                return reply(store.list(ListInput.model_validate(data)))
            if operation == "annotate":
                return reply(store.annotate(AnnotationInput.model_validate(data)))
            if operation in {"thread", "variants"}:
                selected = DetailInput.model_validate(data)
                return reply(getattr(store, operation)(selected.id, selected.offset))
            raise CollectionError("invalid_action", 404)
        except ValidationError:
            return reply({"error": "invalid_request"}, 422)
        except CollectionError as error:
            return reply({"error": error.code}, error.status)
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    @router.post("/conversations/{operation}")
    def conversations(operation: str, request: Request):
        try:
            data = request.scope["collection_input"]
            store = ConversationService(sessions)
            routes = {
                "list": (ConversationList, store.list),
                "detail": (ConversationDetail, store.detail),
                "seen": (ConversationSeen, store.seen),
                "group-save": (GroupSave, store.save_group),
                "group-delete": (GroupDelete, store.delete_group),
            }
            if operation not in routes:
                raise CollectionError("invalid_action", 404)
            schema, handler = routes[operation]
            return reply(handler(schema.model_validate(data)))
        except ValidationError:
            return reply({"error": "invalid_request"}, 422)
        except CollectionError as error:
            return reply({"error": error.code}, error.status)
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    @router.post("/sources/{operation}")
    def sources(operation: str, request: Request):
        try:
            store = SourceService(sessions)
            data = request.scope["collection_input"]
            if operation == "list" and data == {}:
                return reply(store.list())
            if operation == "save":
                return reply(store.save(SourceInput.model_validate(data)))
            raise CollectionError("invalid_request", 422)
        except ValidationError:
            return reply({"error": "invalid_request"}, 422)
        except CollectionError as error:
            return reply({"error": error.code}, error.status)
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    @router.post("/support/{operation}")
    def support(operation: str, request: Request):
        try:
            data = request.scope["collection_input"]
            store = SupportService(sessions)
            if operation == "list" and data == {}:
                return reply(store.list())
            if operation == "detail":
                return reply(store.detail(Selection.model_validate(data).id))
            if operation == "act":
                return reply(store.act(CaseAction.model_validate(data)))
            if operation in {"activate", "pause", "resume"} and data == {}:
                return reply(store.command(operation))
            raise CollectionError("invalid_action", 422)
        except ValidationError:
            return reply({"error": "invalid_request"}, 422)
        except CollectionError as error:
            return reply({"error": error.code}, error.status)
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    @router.post("/reviews/{operation}")
    def reviews(operation: str, request: Request):
        try:
            data = request.scope["collection_input"]
            store = ReviewService(sessions)
            if operation == "list" and data == {}:
                return reply(store.list())
            if operation == "detail":
                return reply(store.detail(Selection.model_validate(data).id))
            if operation == "act":
                return reply(store.act(ReviewAction.model_validate(data)))
            if operation == "demo":
                return reply(store.demo(DemoInput.model_validate(data)))
            if operation in {"activate", "pause", "resume"} and data == {}:
                return reply(store.command(operation))
            raise CollectionError("invalid_action", 422)
        except ValidationError:
            return reply({"error": "invalid_request"}, 422)
        except CollectionError as error:
            return reply({"error": error.code}, error.status)
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    @router.post("/human/{operation}")
    def human(operation: str, request: Request):
        try:
            data = request.scope["collection_input"]
            store = HumanService(sessions)
            if operation == "list" and data == {}:
                return reply(store.list())
            if operation == "detail":
                selected = HumanSelection.model_validate(data)
                return reply(store.detail(selected.domain, selected.id))
            if operation == "act":
                return reply(store.act(HumanDecision.model_validate(data)))
            raise CollectionError("invalid_action", 422)
        except ValidationError:
            return reply({"error": "invalid_request"}, 422)
        except CollectionError as error:
            return reply({"error": error.code}, error.status)
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    @router.post("/{action}")
    def command(action: str, request: Request):
        try:
            return reply(service.command(action))
        except CollectionError as error:
            return reply({"error": error.code}, error.status)
        except SQLAlchemyError:
            return reply({"error": "database_unavailable"}, 503)

    app.include_router(router)
