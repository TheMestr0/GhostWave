import unittest

from infosec_ultra.core.app_services import ReceiverService, SenderService
from infosec_ultra.core.crypto_session import generate_x25519_keypair
from infosec_ultra.core.protocol_codec import ProtocolCodec
from infosec_ultra.core.settings import ReceiverSettings, SenderSettings


class FakeTransmitter:
    def __init__(self):
        self.frames: list[bytes] = []

    def send_bytes(self, payload: bytes) -> None:
        self.frames.append(payload)


class MessageFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receiver_private, self.receiver_public = generate_x25519_keypair()
        self.sender_settings = SenderSettings(receiver_public_key=self.receiver_public)
        self.receiver_settings = ReceiverSettings(
            receiver_private_key=self.receiver_private,
            receiver_public_key=self.receiver_public,
            command_execution_enabled=True,
            allowed_commands=["CALC"],
        )
        self.fake_transmitter = FakeTransmitter()
        self.sender_service = SenderService(self.sender_settings, transmitter=self.fake_transmitter)
        self.receiver_service = ReceiverService(self.receiver_settings)
        self.codec = ProtocolCodec()

    def _process_transmission(self) -> list[dict]:
        events: list[dict] = []
        for packet in self.fake_transmitter.frames:
            events.extend(self.receiver_service.process_packet(packet))
        return events

    def test_text_message_round_trip_without_audio(self) -> None:
        self.sender_service.send("text", "hello secure world", self.receiver_public)

        events = self._process_transmission()

        message_events = [event for event in events if event["type"] == "message_received"]
        self.assertTrue(any(event["type"] == "session_ready" for event in events))
        self.assertEqual(1, len(message_events))
        self.assertEqual("hello secure world", message_events[0]["body"])

    def test_command_packet_becomes_pending_and_does_not_auto_run(self) -> None:
        self.sender_service.send("command", "CALC", self.receiver_public)

        events = self._process_transmission()

        command_events = [event for event in events if event["type"] == "command_pending"]
        self.assertEqual(1, len(command_events))
        self.assertEqual("CALC", command_events[0]["body"])
        self.assertEqual(1, len(self.receiver_service.command_policy.pending_commands()))

    def test_corrupted_payload_returns_decrypt_error(self) -> None:
        self.sender_service.send("text", "hello secure world", self.receiver_public)

        for packet in self.fake_transmitter.frames[:-1]:
            self.receiver_service.process_packet(packet)
        data_frame = self.codec.decode_frame(self.fake_transmitter.frames[-1])
        data_frame["ct"] = data_frame["ct"][:-2] + "ab"
        corrupted_packet = self.codec.encode_frame(data_frame)

        event = self.receiver_service.process_packet(corrupted_packet)[0]
        self.assertEqual("error", event["type"])
        self.assertEqual("decrypt_failed", event["code"])

    def test_data_packet_waits_for_late_handshake(self) -> None:
        self.sender_service.send("text", "hello secure world", self.receiver_public)

        waiting_events = self.receiver_service.process_packet(self.fake_transmitter.frames[-1])
        late_handshake_events = self.receiver_service.process_packet(self.fake_transmitter.frames[0])

        self.assertEqual("waiting_for_handshake", waiting_events[0]["type"])
        self.assertTrue(any(event["type"] == "session_ready" for event in late_handshake_events))
        message_events = [event for event in late_handshake_events if event["type"] == "message_received"]
        self.assertEqual(1, len(message_events))
        self.assertEqual("hello secure world", message_events[0]["body"])


if __name__ == "__main__":
    unittest.main()
