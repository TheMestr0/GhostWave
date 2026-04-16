import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .command_policy import SUPPORTED_COMMANDS
from .crypto_session import generate_x25519_keypair
from .errors import SettingsError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SettingsPaths:
    config_dir: Path
    sender_path: Path
    receiver_path: Path
    legacy_sender_path: Path
    legacy_receiver_path: Path


def get_settings_paths(root_dir: Path | None = None) -> SettingsPaths:
    base_dir = root_dir or PROJECT_ROOT
    config_dir = base_dir / "config"
    return SettingsPaths(
        config_dir=config_dir,
        sender_path=config_dir / "sender.json",
        receiver_path=config_dir / "receiver.json",
        legacy_sender_path=base_dir / "sender_config.json",
        legacy_receiver_path=base_dir / "receiver_config.json",
    )


DEFAULT_SETTINGS_PATHS = get_settings_paths()


@dataclass
class SenderSettings:
    device_name: str = "Windows Sender"
    receiver_public_key: str = ""
    protocol_id: int = 4
    output_volume: int = 100


@dataclass
class ReceiverSettings:
    device_name: str = "Windows Receiver"
    input_device_index: int | None = None
    protocol_id: int = 4
    command_execution_enabled: bool = False
    allowed_commands: list[str] = field(default_factory=lambda: list(SUPPORTED_COMMANDS))
    receiver_private_key: str = ""
    receiver_public_key: str = ""


def _ensure_config_dir(paths: SettingsPaths) -> None:
    paths.config_dir.mkdir(parents=True, exist_ok=True)


def migrate_legacy_settings(paths: SettingsPaths = DEFAULT_SETTINGS_PATHS) -> None:
    _ensure_config_dir(paths)

    if paths.legacy_sender_path.exists() and not paths.sender_path.exists():
        paths.sender_path.write_text(paths.legacy_sender_path.read_text(encoding="utf-8"), encoding="utf-8")

    if paths.legacy_receiver_path.exists() and not paths.receiver_path.exists():
        paths.receiver_path.write_text(paths.legacy_receiver_path.read_text(encoding="utf-8"), encoding="utf-8")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SettingsError(f"Invalid JSON settings file: {path.name}") from exc


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_sender_settings(paths: SettingsPaths = DEFAULT_SETTINGS_PATHS) -> SenderSettings:
    migrate_legacy_settings(paths)
    data = _read_json(paths.sender_path)
    return SenderSettings(
        device_name=data.get("device_name", "Windows Sender"),
        receiver_public_key=data.get("receiver_public_key", ""),
        protocol_id=int(data.get("protocol_id", 4)),
        output_volume=int(data.get("output_volume", 100)),
    )


def save_sender_settings(settings: SenderSettings, paths: SettingsPaths = DEFAULT_SETTINGS_PATHS) -> None:
    _write_json(paths.sender_path, asdict(settings))


def load_receiver_settings(paths: SettingsPaths = DEFAULT_SETTINGS_PATHS) -> ReceiverSettings:
    migrate_legacy_settings(paths)
    data = _read_json(paths.receiver_path)
    return ReceiverSettings(
        device_name=data.get("device_name", "Windows Receiver"),
        input_device_index=data.get("input_device_index"),
        protocol_id=int(data.get("protocol_id", 4)),
        command_execution_enabled=bool(data.get("command_execution_enabled", False)),
        allowed_commands=list(data.get("allowed_commands", SUPPORTED_COMMANDS)),
        receiver_private_key=data.get("receiver_private_key", ""),
        receiver_public_key=data.get("receiver_public_key", ""),
    )


def save_receiver_settings(settings: ReceiverSettings, paths: SettingsPaths = DEFAULT_SETTINGS_PATHS) -> None:
    _write_json(paths.receiver_path, asdict(settings))


def ensure_local_settings(paths: SettingsPaths = DEFAULT_SETTINGS_PATHS) -> tuple[SenderSettings, ReceiverSettings]:
    receiver = load_receiver_settings(paths)
    sender = load_sender_settings(paths)

    if not receiver.receiver_private_key or not receiver.receiver_public_key:
        private_key, public_key = generate_x25519_keypair()
        receiver.receiver_private_key = private_key
        receiver.receiver_public_key = public_key
        save_receiver_settings(receiver, paths)

    if not sender.receiver_public_key:
        sender.receiver_public_key = receiver.receiver_public_key
        save_sender_settings(sender, paths)

    return sender, receiver

