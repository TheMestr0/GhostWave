import unittest

from infosec_ultra.core.audio_transport import (
    MAX_GGWAVE_PAYLOAD_BYTES,
    FragmentReassembler,
    fragment_payload,
)
from infosec_ultra.core.crypto_session import (
    derive_sender_session_key,
    encrypt_payload,
    generate_nonce,
    generate_session_id,
    generate_x25519_keypair,
)
from infosec_ultra.core.protocol_codec import PROTOCOL_VERSION, ProtocolCodec


class AudioTransportTests(unittest.TestCase):
    def test_fragmentation_keeps_real_frames_under_ggwave_limit(self) -> None:
        _receiver_private, receiver_public = generate_x25519_keypair()
        sender_private, sender_public = generate_x25519_keypair()
        nonce = generate_nonce()
        session_id = generate_session_id()
        session_key = derive_sender_session_key(receiver_public, sender_private, nonce)
        codec = ProtocolCodec()

        frames = [
            codec.encode_frame(
                {
                    "v": PROTOCOL_VERSION,
                    "t": "hello",
                    "sid": session_id,
                    "spk": sender_public,
                    "nonce": nonce,
                }
            ),
            codec.encode_frame(
                {
                    "v": PROTOCOL_VERSION,
                    "t": "data",
                    "sid": session_id,
                    "ct": encrypt_payload({"kind": "text", "body": "hello secure world"}, session_key),
                }
            ),
        ]

        for frame in frames:
            fragments = fragment_payload(frame)
            self.assertGreater(len(fragments), 1)
            self.assertTrue(all(len(fragment) <= MAX_GGWAVE_PAYLOAD_BYTES for fragment in fragments))

            reassembler = FragmentReassembler()
            reassembled = None
            for fragment in fragments:
                reassembled = reassembler.feed(fragment)
            self.assertEqual(frame, reassembled)


if __name__ == "__main__":
    unittest.main()
