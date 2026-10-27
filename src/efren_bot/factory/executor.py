"""The execution-unit boundary: JobSpec in, RunRecord out, nothing else crosses it."""

import json
import subprocess
from collections.abc import Callable
from typing import Protocol

from pydantic import ValidationError

from efren_bot.factory.contracts import JobSpec, RunRecord


class ExecutorError(Exception):
    """The execution unit could not produce a valid RunRecord."""


class Executor(Protocol):
    def run(self, spec: JobSpec) -> RunRecord: ...


class ScraftOpsExecutor:
    """Calls ``scraft-ops factory run``; it parses stdout even on a non-zero exit.

    ``scraft-ops`` exits non-zero when a run did not succeed but still prints the record,
    so a failed run is data, while a missing/garbled record is an ``ExecutorError``.
    """

    def __init__(
        self,
        binary: str = "scraft-ops",
        *,
        state_dir: str | None = None,
        profile_dir: str | None = None,
        executor: str | None = None,
        timeout_seconds: int = 3600,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ):
        self.binary = binary
        self.state_dir = state_dir
        self.profile_dir = profile_dir
        self.executor = executor
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def command(self) -> list[str]:
        cmd = [self.binary, "factory", "run", "--job", "-"]
        if self.state_dir:
            cmd += ["--state-dir", self.state_dir]
        if self.profile_dir:
            cmd += ["--profile-dir", self.profile_dir]
        if self.executor:
            cmd += ["--executor", self.executor]
        return cmd

    def run(self, spec: JobSpec) -> RunRecord:
        try:
            result = self._runner(
                self.command(),
                input=json.dumps(spec.wire()).encode(),
                capture_output=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExecutorError(f"execution unit unavailable: {type(exc).__name__}") from exc
        try:
            record = RunRecord.model_validate(json.loads(result.stdout))
        except (ValueError, ValidationError) as exc:
            raise ExecutorError("execution unit returned no valid RunRecord") from exc
        if not record.valid_schema():
            raise ExecutorError(f"unsupported run schema {record.schema_!r}")
        if record.job_id != spec.job_id:
            raise ExecutorError("RunRecord belongs to a different job")
        return record


class ScriptedExecutor:
    """Test double: returns a canned record per call without any process."""

    def __init__(self, respond: Callable[[JobSpec], RunRecord]):
        self.respond = respond
        self.calls: list[JobSpec] = []

    def run(self, spec: JobSpec) -> RunRecord:
        self.calls.append(spec)
        return self.respond(spec)
