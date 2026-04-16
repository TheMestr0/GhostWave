import time
from collections.abc import Callable

from .audio_transport import AudioTransmitter
from .command_policy import CommandPolicy
from .crypto_session import (
    decrypt_payload,
    derive_receiver_session_key,
    derive_sender_session_key,
    encrypt_payload,
    generate_nonce,
    generate_session_id,
    generate_x25519_keypair,
    key_fingerprint,
)
from .errors import CommandBlockedError, CommandNotFoundError, CryptoError, ProtocolError, SettingsError
from .protocol_codec import PROTOCOL_VERSION, ProtocolCodec
from .settings import ReceiverSettings, SenderSettings

ProgressCallback = Callable[[str, str], None]


def _event(event_type: str, **payload: object) -> dict:
    payload["type"] = event_type
    return payload


class SenderService:
    def __init__(self, settings: SenderSettings, transmitter: AudioTransmitter | None = None):
        self.settings = settings
        self.codec = ProtocolCodec()
        self.transmitter = transmitter or AudioTransmitter(
            protocol_id=settings.protocol_id,
            volume=settings.output_volume,
        )

    def send(
        self,
        kind: str,
        body: str,
        receiver_public_key: str,
        progress: ProgressCallback | None = None,
    ) -> str:
        normalized_kind = kind.strip().lower()
        if normalized_kind not in {"text", "command"}:
            raise SettingsError("Payload kind must be text or command.")
        if not body.strip():
            raise SettingsError("Message body is empty.")
        if not receiver_public_key.strip():
            raise SettingsError("Receiver public key is required.")

        session_id = generate_session_id()
        sender_private_key, sender_public_key = generate_x25519_keypair()
        nonce = generate_nonce()
        session_key = derive_sender_session_key(receiver_public_key, sender_private_key, nonce)

        hello_frame = self.codec.encode_frame(
            {"v": PROTOCOL_VERSION, "t": "hello", "sid": session_id, "spk": sender_public_key, "nonce": nonce}
        )
        data_frame = self.codec.encode_frame(
            {
                "v": PROTOCOL_VERSION,
                "t": "data",
                "sid": session_id,
                "ct": encrypt_payload({"kind": normalized_kind, "body": body.strip()}, session_key),
            }
        )

        self._emit(progress, "encoding", "Encoding hello frame.")
        self.transmitter.send_bytes(hello_frame)
        self._emit(progress, "encrypting", "Encrypting payload.")
        time.sleep(0.35)
        self._emit(progress, "transmitting", "Transmitting data frame.")
        self.transmitter.send_bytes(data_frame)
        self._emit(progress, "done", f"Transmission finished for session {session_id}.")
        return session_id

    @staticmethod
    def _emit(progress: ProgressCallback | None, code: str, message: str) -> None:
        if progress:
            progress(code, message)


class ReceiverService:
    def __init__(self, settings: ReceiverSettings):
        self.settings = settings
        self.codec = ProtocolCodec()
        self.command_policy = CommandPolicy(
            enabled=settings.command_execution_enabled,
            allowed_commands=settings.allowed_commands,
        )
        self.sessions: dict[str, dict] = {}

    def update_command_policy(self, enabled: bool, allowed_commands: list[str]) -> None:
        self.settings.command_execution_enabled = enabled
        self.settings.allowed_commands = allowed_commands
        self.command_policy.set_enabled(enabled)
        self.command_policy.set_allowed_commands(allowed_commands)

    def process_packet(self, packet: bytes) -> list[dict]:
        try:
            frame = self.codec.decode_frame(packet)
        except ProtocolError as exc:
            return [_event("error", code="invalid_packet", message=str(exc))]

        if frame["t"] == "hello":
            return [self._handle_hello(frame)]
        if frame["t"] == "data":
            return [self._handle_data(frame)]
        return [_event("error", code="unsupported_packet", message="Unsupported packet type.")]

    def _handle_hello(self, frame: dict) -> dict:
        try:
            session_key = derive_receiver_session_key(
                self.settings.receiver_private_key,
                frame["spk"],
                frame["nonce"],
            )
        except (SettingsError, CryptoError) as exc:
            return _event("error", code="invalid_handshake", message=str(exc))

        sender_fingerprint = key_fingerprint(frame["spk"])
        self.sessions[frame["sid"]] = {
            "session_key": session_key,
            "sender_public_key": frame["spk"],
            "sender_fingerprint": sender_fingerprint,
            "created_at": time.time(),
        }
        return _event(
            "session_ready",
            session_id=frame["sid"],
            sender_fingerprint=sender_fingerprint,
            message="Secure session established.",
        )

    def _handle_data(self, frame: dict) -> dict:
        session = self.sessions.get(frame["sid"])
        if not session:
            return _event("error", code="invalid_handshake", message="Unknown session id.")

        try:
            payload = decrypt_payload(frame["ct"], session["session_key"])
        except CryptoError as exc:
            return _event("error", code="decrypt_failed", message=str(exc), session_id=frame["sid"])

        kind = payload.get("kind")
        body = payload.get("body")
        if kind not in {"text", "command"} or not isinstance(body, str) or not body.strip():
            return _event("error", code="invalid_payload", message="Payload must contain kind and body.")

        normalized_body = body.strip()
        if kind == "text":
            return _event(
                "message_received",
                session_id=frame["sid"],
                body=normalized_body,
                sender_fingerprint=session["sender_fingerprint"],
            )

        try:
            pending = self.command_policy.submit(normalized_body, frame["sid"])
        except CommandBlockedError as exc:
            return _event(
                "command_blocked",
                session_id=frame["sid"],
                body=normalized_body.upper(),
                message=str(exc),
            )
        except CommandNotFoundError as exc:
            return _event("error", code="unsupported_packet", session_id=frame["sid"], message=str(exc))

        return _event(
            "command_pending",
            session_id=frame["sid"],
            command_id=pending.command_id,
            body=pending.command_name,
            created_at=pending.created_at,
        )

    def approve_command(self, command_id: str) -> dict:
        try:
            pending = self.command_policy.approve(command_id)
        except (CommandBlockedError, CommandNotFoundError) as exc:
            return _event("error", code="command_blocked", message=str(exc))
        return _event(
            "command_executed",
            command_id=pending.command_id,
            session_id=pending.session_id,
            body=pending.command_name,
            message="Command executed locally.",
        )

    def reject_command(self, command_id: str) -> dict:
        try:
            pending = self.command_policy.reject(command_id)
        except CommandBlockedError as exc:
            return _event("error", code="command_blocked", message=str(exc))
        return _event(
            "command_rejected",
            command_id=pending.command_id,
            session_id=pending.session_id,
            body=pending.command_name,
            message="Command rejected by local user.",
        )
