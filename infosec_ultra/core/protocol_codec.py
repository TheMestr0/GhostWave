import json

from reedsolo import RSCodec, ReedSolomonError

from .errors import ProtocolError

PROTOCOL_VERSION = 1
FRAME_TYPES = {"hello", "data"}

# 2-byte big-endian length prefix so the receiver knows exactly how many
# bytes belong to the RS block, regardless of ggwave's buffer padding.
_LENGTH_PREFIX_SIZE = 2


class ProtocolCodec:
    def __init__(self, parity_bytes: int = 20):
        self.rs = RSCodec(parity_bytes)

    def encode_frame(self, frame: dict) -> bytes:
        self._validate_frame(frame)
        raw = json.dumps(frame, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        rs_block = bytes(self.rs.encode(raw))
        # Prepend a 2-byte big-endian length so the receiver can slice off
        # any trailing garbage that ggwave appends to its decode buffer.
        return len(rs_block).to_bytes(_LENGTH_PREFIX_SIZE, "big") + rs_block

    def decode_frame(self, packet: bytes) -> dict:
        if len(packet) < _LENGTH_PREFIX_SIZE:
            raise ProtocolError("Packet too short.")

        expected_len = int.from_bytes(packet[:_LENGTH_PREFIX_SIZE], "big")
        rs_block = packet[_LENGTH_PREFIX_SIZE : _LENGTH_PREFIX_SIZE + expected_len]

        if len(rs_block) < expected_len:
            raise ProtocolError(
                f"Packet truncated: expected {expected_len} bytes, got {len(rs_block)}."
            )

        try:
            raw = self.rs.decode(rs_block)[0]
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
