import json

from reedsolo import RSCodec, ReedSolomonError

from .errors import ProtocolError

PROTOCOL_VERSION = 1
FRAME_TYPES = {"hello", "data"}


class ProtocolCodec:
    def __init__(self, parity_bytes: int = 8):
        self.rs = RSCodec(parity_bytes)

    def encode_frame(self, frame: dict) -> bytes:
        self._validate_frame(frame)
        raw = json.dumps(frame, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return bytes(self.rs.encode(raw))

    def decode_frame(self, packet: bytes) -> dict:
        try:
            raw = self.rs.decode(packet)[0]
        except ReedSolomonError as exc:
            raise ProtocolError("Frame failed error correction.") from exc

        try:
            frame = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ProtocolError("Frame is not valid JSON.") from exc

        self._validate_frame(frame)
        return frame

    def _validate_frame(self, frame: dict) -> None:
        if not isinstance(frame, dict):
            raise ProtocolError("Frame must be a JSON object.")

        version = frame.get("v")
        frame_type = frame.get("t")
        session_id = frame.get("sid")

        if version != PROTOCOL_VERSION:
            raise ProtocolError("Unsupported packet version.")
        if frame_type not in FRAME_TYPES:
            raise ProtocolError("Unsupported packet type.")
        if not isinstance(session_id, str) or not session_id:
            raise ProtocolError("Packet session id is missing.")

        if frame_type == "hello":
            for field in ("spk", "nonce"):
                if not isinstance(frame.get(field), str) or not frame[field]:
                    raise ProtocolError("Invalid hello packet.")

        if frame_type == "data":
            if not isinstance(frame.get("ct"), str) or not frame["ct"]:
                raise ProtocolError("Invalid data packet.")

