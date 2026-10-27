import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

CLI = "/Applications/OpenChamber.app/Contents/Resources/opencode-cli/opencode"
READER_IDS = (
    "slack_slack_list_user_channels",
    "slack_slack_read_channel",
    "slack_slack_search_public_and_private",
    "slack_slack_read_thread",
)
USER_ID = "U0B6T31KXSN"


class TransportError(Exception):
    pass


class NativeSlack:
    def __init__(self, runtime: Path):
        self.runtime = runtime.resolve()
        self.query = "?" + urlencode({"location[directory]": str(self.runtime)})
        self.session_id = None
        self.last_read_at = 0.0

    def api(self, method, path, data=None, *, timeout=65):
        args = [CLI, "--log-level", "none", "api", method, path]
        if data is not None:
            args += ["--data", json.dumps(data, separators=(",", ":"))]
        try:
            result = subprocess.run(args, capture_output=True, timeout=timeout)
            body = json.loads(result.stdout) if result.stdout.strip() else {}
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise TransportError("native_api_unavailable") from error
        if result.returncode:
            raise TransportError("native_api_failed")
        return body

    def rpc(self, method, data):
        body = self.api(
            "post", f"/api/rpc/efrenbot-collection/{method}{self.query}", {"input": data}
        )
        output = body.get("output")
        if not isinstance(output, dict):
            raise TransportError("native_rpc_invalid")
        return output

    def __enter__(self):
        for attempt in range(20):
            try:
                if self.rpc("capabilities", {}).get("ready") is True:
                    break
            except TransportError:
                pass
            if attempt == 19:
                raise TransportError("native_reader_not_ready")
            time.sleep(1)
        created = self.api(
            "post",
            "/api/session",
            {
                "agent": "build",
                "title": f"Efren Bot collection {uuid4()}",
                "location": {"directory": str(self.runtime)},
                "metadata": {"efrenbot_collection": True},
                "permissions": [{"action": "*", "resource": "*", "effect": "deny"}]
                + [{"action": action, "resource": "*", "effect": "allow"} for action in READER_IDS],
            },
        )
        session = created.get("data", created)
        self.session_id = session["id"]
        if session.get("agent") != "build":
            self.close()
            raise TransportError("native_agent_missing")
        return self

    def read(self, operation, arguments):
        time.sleep(max(0, 1.5 - (time.monotonic() - self.last_read_at)))
        self.last_read_at = time.monotonic()
        output = self.rpc(
            "read", {"session_id": self.session_id, "operation": operation, "arguments": arguments}
        )
        if output.get("error_code"):
            raise TransportError(output["error_code"])
        response = output.get("response")
        if not isinstance(response, dict):
            raise TransportError("source_format_unknown")
        return response

    def close(self):
        if self.session_id:
            path = f"/api/session/{self.session_id}"
            try:
                self.api(
                    "patch",
                    path,
                    {"permissions": [{"action": "*", "resource": "*", "effect": "deny"}]},
                )
            finally:
                self.api("patch", path, {"archived": True})
            page = self.api(
                "get", "/api/session?" + urlencode({"directory": str(self.runtime), "limit": 100})
            )
            found = [s for s in page.get("data", []) if s.get("id") == self.session_id]
            if len(found) != 1 or found[0].get("time", {}).get("archived") is None:
                raise TransportError("native_cleanup_unconfirmed")
            self.session_id = None

    def __exit__(self, *args):
        self.close()
