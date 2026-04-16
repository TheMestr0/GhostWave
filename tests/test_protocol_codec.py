import unittest

from infosec_ultra.core.errors import ProtocolError
from infosec_ultra.core.protocol_codec import PROTOCOL_VERSION, ProtocolCodec


class ProtocolCodecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = ProtocolCodec()

    def test_round_trip_hello_frame(self) -> None:
        frame = {
            "v": PROTOCOL_VERSION,
            "t": "hello",
            "sid": "abc123",
            "spk": "sender-public-key",
            "nonce": "nonce-value",
        }
        encoded = self.codec.encode_frame(frame)
        decoded = self.codec.decode_frame(encoded)
        self.assertEqual(frame, decoded)

    def test_round_trip_data_frame(self) -> None:
        frame = {"v": PROTOCOL_VERSION, "t": "data", "sid": "abc123", "ct": "ciphertext"}
        encoded = self.codec.encode_frame(frame)
        decoded = self.codec.decode_frame(encoded)
        self.assertEqual(frame, decoded)

    def test_rejects_unsupported_version(self) -> None:
        with self.assertRaises(ProtocolError):
            self.codec.encode_frame({"v": 2, "t": "hello", "sid": "1", "spk": "a", "nonce": "b"})

    def test_rejects_malformed_json(self) -> None:
        malformed = bytes(self.codec.rs.encode(b"not-json"))
        with self.assertRaises(ProtocolError):
            self.codec.decode_frame(malformed)


if __name__ == "__main__":
    unittest.main()

