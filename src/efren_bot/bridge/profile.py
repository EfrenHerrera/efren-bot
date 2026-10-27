"""Non-secret operator profile, conservative schema support, safe own-file reads."""

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, model_validator

from efren_bot.bridge.contracts import Closed, Digest, canonical, slack_url, strict_json


class ProfileError(ValueError):
    def __init__(self, reason="profile_invalid"):
        self.reason = reason
        super().__init__(reason)


def own_file(path: Path, *, host: bool, maximum: int) -> bytes:
    """O_NOFOLLOW + fstat (not check-then-open); API allows bind-mount UID mismatch."""
    if not path.is_absolute():
        raise ValueError("unsafe file")
    # No symlink in any path component, including a symlinked parent.
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError("unsafe file")
    if host:
        parent = path.parent.stat()
        if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700:
            raise ValueError("unsafe directory")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or host
            and info.st_uid != os.getuid()
            or info.st_size > maximum
        ):
            raise ValueError("unsafe file")
        raw = os.read(fd, maximum + 1)
        if len(raw) > maximum:
            raise ValueError("unsafe file")
        return raw
    finally:
        os.close(fd)


def load_token(path: Path, *, host: bool) -> str:
    raw = own_file(path, host=host, maximum=65)
    if not re.fullmatch(rb"[0-9a-f]{64}\n", raw):
        raise ValueError("invalid token")
    return raw[:-1].decode("ascii")


def version(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("invalid version")
    return tuple(int(x) for x in value.split("."))


class CLIProfile(Closed):
    path: str
    minimum_version: Literal["2.1.295"]
    verified_version: str
    verified_sha256: Digest

    @model_validator(mode="after")
    def valid(self):
        if not Path(self.path).is_absolute() or any(ord(c) < 32 for c in self.path):
            raise ValueError("invalid path")
        if version(self.verified_version) < version(self.minimum_version):
            raise ValueError("unsupported version")
        return self


def schema_shape(schema):
    if type(schema) is not dict:
        raise ValueError("unsupported schema")
    common = {"type", "const", "enum", "description", "title"}
    kind = schema.get("type")
    specific = {
        "object": {"properties", "required", "additionalProperties"},
        "array": {"items", "minItems", "maxItems"},
        "string": {"minLength", "maxLength"},
        "integer": {"minimum", "maximum"},
        "boolean": set(),
        "null": set(),
    }
    if kind not in specific or set(schema) - (common | specific[kind]):
        raise ValueError("unsupported schema")
    if kind == "object":
        props, required = schema.get("properties"), schema.get("required")
        if (
            type(props) is not dict
            or type(required) is not list
            or any(type(k) is not str for k in required)
            or len(required) != len(set(required))
            or set(props) != set(required)
            or schema.get("additionalProperties") is not False
        ):
            raise ValueError("unsupported open schema")
        for child in props.values():
            schema_shape(child)
    if kind == "array":
        schema_shape(schema.get("items"))
    for key in {"minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum"} & set(
        schema
    ):
        if type(schema[key]) is not int:
            raise ValueError("invalid schema bound")
    if "enum" in schema and (type(schema["enum"]) is not list or not schema["enum"]):
        raise ValueError("invalid enum")


def validate_schema(schema, value):
    """Deliberately small, closed JSON Schema subset. Unsupported => fail closed.

    No resolver/evaluator/$ref. Equality of complete arguments is enforced separately.
    Const/enum values are compared using canonical JSON (True is not integer 1).
    """
    schema_shape(schema)
    kind = schema.get("type")
    expected = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "boolean": bool,
        "null": type(None),
    }
    if kind not in expected or type(value) is not expected[kind]:
        raise ValueError("schema mismatch")
    if "const" in schema and canonical(value) != canonical(schema["const"]):
        raise ValueError("schema mismatch")
    if "enum" in schema:
        if type(schema["enum"]) is not list or not any(
            canonical(value) == canonical(v) for v in schema["enum"]
        ):
            raise ValueError("schema mismatch")
    if kind == "object":
        props, required = schema.get("properties"), schema.get("required")
        if (
            type(props) is not dict
            or type(required) is not list
            or any(type(k) is not str for k in required)
            or len(required) != len(set(required))
            or set(required) != set(props)
            or schema.get("additionalProperties") is not False
            or set(value) != set(props)
        ):
            raise ValueError("unsupported open schema")
        for key, item in value.items():
            validate_schema(props[key], item)
    elif kind == "array":
        if "items" not in schema:
            raise ValueError("unsupported schema")
        for item in value:
            validate_schema(schema["items"], item)
    bounds = {
        "string": ("minLength", "maxLength", len(value) if kind == "string" else 0),
        "array": ("minItems", "maxItems", len(value) if kind == "array" else 0),
        "integer": ("minimum", "maximum", value),
    }
    if kind in bounds:
        lo, hi, size = bounds[kind]
        for name in (lo, hi):
            if name in schema and type(schema[name]) is not int:
                raise ValueError("invalid schema bound")
        if lo in schema and size < schema[lo] or hi in schema and size > schema[hi]:
            raise ValueError("schema mismatch")


class Connector(Closed):
    kind: Literal["claude_ai"]
    server_url: str
    tool_name: Annotated[str, StringConstraints(pattern=r"^mcp__[A-Za-z0-9_-]+$", max_length=256)]
    url_argument: Annotated[
        str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=128)
    ]
    fixed_arguments: dict
    input_schema: dict

    @model_validator(mode="after")
    def valid(self):
        url = urlsplit(self.server_url)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or "*" in self.server_url
            or any(c.isspace() for c in self.server_url)
            or "%" in url.netloc
        ):
            raise ValueError("invalid connector")
        if self.url_argument in self.fixed_arguments:
            raise ValueError("invalid arguments")
        return self


class Limits(Closed):
    run_timeout_seconds: int = Field(ge=10, le=120)
    max_turns: int = Field(ge=1, le=4)
    max_tool_calls: Literal[1]
    max_stdout_bytes: int = Field(ge=1024, le=1048576)
    max_stderr_bytes: int = Field(ge=1024, le=65536)
    max_result_bytes: int = Field(ge=1024, le=32768)


class SlackThreadConnector(Closed):
    """Reviewed native interface, not an arbitrary tool/argument mapping facility."""

    kind: Literal["claude_ai"]
    selector: Literal["slack_thread_v1"]
    server_url: Literal["https://mcp.slack.com/mcp"]
    tool_name: Literal["mcp__claude_ai_Slack__slack_read_thread"]
    fixed_arguments: dict
    input_schema: dict

    @model_validator(mode="after")
    def valid(self):
        if canonical(self.fixed_arguments) != canonical(
            {"limit": 100, "response_format": "concise"}
        ):
            raise ValueError("invalid thread arguments")
        return self


class Profile(Closed):
    schema_version: Literal[1, 2]
    profile_id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,64}$")]
    profile_version: int = Field(ge=1)
    approved: Literal[True]
    cli: CLIProfile
    model: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    allowed_slack_hosts: list[str] = Field(min_length=1, max_length=8)
    connector: Connector | SlackThreadConnector
    limits: Limits

    @model_validator(mode="before")
    @classmethod
    def exact_literals(cls, data):
        if (
            type(data.get("schema_version")) is not int
            or type(data.get("approved")) is not bool
            or type(data.get("limits")) is not dict
            or type(data["limits"].get("max_tool_calls")) is not int
        ):
            raise ValueError("invalid literal type")
        return data

    @model_validator(mode="after")
    def valid(self):
        if type(self.schema_version) is not int or type(self.limits.max_tool_calls) is not int:
            raise ValueError("invalid integer")
        if (self.schema_version == 2) != isinstance(self.connector, SlackThreadConnector):
            raise ValueError("invalid selector version")
        if not self.model.strip() or any(ord(c) < 32 or ord(c) == 127 for c in self.model):
            raise ValueError("invalid model")
        if len(set(self.allowed_slack_hosts)) != len(self.allowed_slack_hosts) or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.slack\.com", h)
            for h in self.allowed_slack_hosts
        ):
            raise ValueError("invalid hosts")
        suffix = "1234567890123456" if self.schema_version == 2 else "1"
        sample = f"https://{self.allowed_slack_hosts[0]}/archives/C1/p{suffix}"
        self.arguments(sample)
        return self

    @property
    def fingerprint(self):
        return "sha256:" + hashlib.sha256(canonical(self.model_dump(mode="json"))).hexdigest()

    def arguments(self, url: str):
        slack_url(url, self.allowed_slack_hosts)
        if isinstance(self.connector, SlackThreadConnector):
            # Grammar/host already checked by the shared permalink validator. Preserve
            # every digit (including leading zeros); never float/int/round or look up root.
            channel, stamp = url.rsplit("/", 2)[-2:]
            digits = stamp[1:]
            if len(digits) < 16:
                raise ValueError("invalid parent timestamp")
            args = {
                **self.connector.fixed_arguments,
                "channel_id": channel,
                "message_ts": digits[:-6] + "." + digits[-6:],
            }
        else:
            args = {**self.connector.fixed_arguments, self.connector.url_argument: url}
        validate_schema(self.connector.input_schema, args)
        return args


def load_profile(path: Path, *, host: bool) -> Profile:
    try:
        data = strict_json(own_file(path, host=host, maximum=65536))
        if data.get("approved") is not True:
            raise ProfileError("profile_unapproved")
        return Profile.from_json(data)
    except FileNotFoundError as exc:
        raise ProfileError("profile_missing") from exc
    except ProfileError:
        raise
    except (ValueError, OSError) as exc:
        raise ProfileError() from exc
