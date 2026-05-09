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
        rs_block = bytes(self.codec.rs.encode(b"not-json"))
        # Prepend length prefix so decode_frame can extract the RS block
        prefixed = len(rs_block).to_bytes(2, "big") + rs_block
        with self.assertRaises(ProtocolError):
            self.codec.decode_frame(prefixed)

    def test_decode_survives_trailing_garbage(self) -> None:
        """ggwave's decode buffer is often larger than the payload."""
        import os
        frame = {
            "v": PROTOCOL_VERSION,
            "t": "hello",
            "sid": "abc123",
            "spk": "sender-public-key",
            "nonce": "nonce-value",
        }
        encoded = self.codec.encode_frame(frame)
        padded = encoded + os.urandom(50)
        decoded = self.codec.decode_frame(padded)
        self.assertEqual(frame, decoded)


if __name__ == "__main__":
    unittest.main()

