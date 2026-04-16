import platform
import secrets
import subprocess
import time
from dataclasses import dataclass

from .errors import CommandBlockedError, CommandNotFoundError

SUPPORTED_COMMANDS = ("CALC", "LOCK", "NOTEPAD")
WINDOWS_COMMANDS = {
    "CALC": ["calc"],
    "LOCK": ["rundll32.exe", "user32.dll,LockWorkStation"],
    "NOTEPAD": ["notepad"],
}


@dataclass
class PendingCommand:
    command_id: str
    session_id: str
    command_name: str
    created_at: float


class CommandPolicy:
    def __init__(self, enabled: bool = False, allowed_commands: list[str] | None = None):
        self.enabled = enabled
        self.allowed_commands = {command.upper() for command in (allowed_commands or SUPPORTED_COMMANDS)}
        self._pending: dict[str, PendingCommand] = {}

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_allowed_commands(self, commands: list[str]) -> None:
        self.allowed_commands = {command.upper() for command in commands}

    def submit(self, command_name: str, session_id: str) -> PendingCommand:
        normalized = command_name.strip().upper()
        if normalized not in WINDOWS_COMMANDS:
            raise CommandNotFoundError("Unsupported command.")
        if not self.enabled:
            raise CommandBlockedError("Command execution is disabled.")
        if normalized not in self.allowed_commands:
            raise CommandBlockedError("Command is not in the allowlist.")

        pending = PendingCommand(
            command_id=secrets.token_hex(4),
            session_id=session_id,
            command_name=normalized,
            created_at=time.time(),
        )
        self._pending[pending.command_id] = pending
        return pending

    def pending_commands(self) -> list[PendingCommand]:
        return sorted(self._pending.values(), key=lambda item: item.created_at, reverse=True)

    def approve(self, command_id: str) -> PendingCommand:
        pending = self._pending.pop(command_id, None)
        if not pending:
            raise CommandBlockedError("Pending command was not found.")
        execute_command(pending.command_name)
        return pending

    def reject(self, command_id: str) -> PendingCommand:
        pending = self._pending.pop(command_id, None)
        if not pending:
            raise CommandBlockedError("Pending command was not found.")
        return pending


def execute_command(command_name: str) -> None:
    normalized = command_name.strip().upper()
    command = WINDOWS_COMMANDS.get(normalized)
    if not command:
        raise CommandNotFoundError("Unsupported command.")
    if platform.system() != "Windows":
        raise CommandBlockedError("Local command execution is supported on Windows only.")

    subprocess.Popen(command)

