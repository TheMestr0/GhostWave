import unittest

from infosec_ultra.core.crypto_session import (
    decrypt_payload,
    derive_receiver_session_key,
    derive_sender_session_key,
    encrypt_payload,
    generate_nonce,
    generate_x25519_keypair,
)
from infosec_ultra.core.errors import CryptoError


class CryptoSessionTests(unittest.TestCase):
    def test_sender_and_receiver_derive_same_key(self) -> None:
        receiver_private, receiver_public = generate_x25519_keypair()
        sender_private, sender_public = generate_x25519_keypair()
        nonce = generate_nonce()

        sender_key = derive_sender_session_key(receiver_public, sender_private, nonce)
        receiver_key = derive_receiver_session_key(receiver_private, sender_public, nonce)

        self.assertEqual(sender_key, receiver_key)

    def test_keys_do_not_match_with_wrong_receiver_private_key(self) -> None:
        _, receiver_public = generate_x25519_keypair()
        wrong_receiver_private, _ = generate_x25519_keypair()
        sender_private, sender_public = generate_x25519_keypair()
        nonce = generate_nonce()

        sender_key = derive_sender_session_key(receiver_public, sender_private, nonce)
        wrong_key = derive_receiver_session_key(wrong_receiver_private, sender_public, nonce)

        self.assertNotEqual(sender_key, wrong_key)

    def test_decrypt_fails_for_wrong_session_key(self) -> None:
        receiver_private, receiver_public = generate_x25519_keypair()
        sender_private, sender_public = generate_x25519_keypair()
        nonce = generate_nonce()

        correct_key = derive_sender_session_key(receiver_public, sender_private, nonce)
        wrong_key = derive_receiver_session_key(receiver_private, sender_public, generate_nonce())
        token = encrypt_payload({"kind": "text", "body": "hello"}, correct_key)

        with self.assertRaises(CryptoError):
            decrypt_payload(token, wrong_key)


if __name__ == "__main__":
    unittest.main()

