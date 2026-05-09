import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from secrets import token_bytes

import ggwave
import numpy as np
import pyaudio

from .errors import AudioDeviceError

# Use MME on Windows — it's the most stable host API for PortAudio and lists
# each physical device exactly once.
_PREFERRED_HOST_API_NAME = "MME"
MAX_GGWAVE_PAYLOAD_BYTES = 140
_FRAGMENT_MAGIC = b"ISF"
_FRAGMENT_ID_SIZE = 4
_FRAGMENT_HEADER_SIZE = len(_FRAGMENT_MAGIC) + _FRAGMENT_ID_SIZE + 3
_MAX_FRAGMENT_BODY_BYTES = MAX_GGWAVE_PAYLOAD_BYTES - _FRAGMENT_HEADER_SIZE


def _get_mme_api_index(audio: pyaudio.PyAudio) -> int | None:
    for i in range(audio.get_host_api_count()):
        if audio.get_host_api_info_by_index(i)["name"] == _PREFERRED_HOST_API_NAME:
            return i
    return None


def list_input_devices() -> list[dict]:
    audio = pyaudio.PyAudio()
    devices = []
    try:
        api_index = _get_mme_api_index(audio)
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            if api_index is not None and int(info.get("hostApi", -1)) != api_index:
                continue
            if int(info.get("maxInputChannels", 0)) > 0:
                devices.append({"index": index, "name": info.get("name", f"Input {index}")})
    finally:
        audio.terminate()
    return devices


def list_output_devices() -> list[dict]:
    audio = pyaudio.PyAudio()
    devices = []
    try:
        api_index = _get_mme_api_index(audio)
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            if api_index is not None and int(info.get("hostApi", -1)) != api_index:
                continue
            if int(info.get("maxOutputChannels", 0)) > 0:
                devices.append({"index": index, "name": info.get("name", f"Output {index}")})
    finally:
        audio.terminate()
    return devices


def fragment_payload(payload: bytes) -> list[bytes]:
    if len(payload) <= MAX_GGWAVE_PAYLOAD_BYTES:
        return [payload]

    message_id = token_bytes(_FRAGMENT_ID_SIZE)
    chunks = [
        payload[index:index + _MAX_FRAGMENT_BODY_BYTES]
        for index in range(0, len(payload), _MAX_FRAGMENT_BODY_BYTES)
    ]
    if len(chunks) > 255:
        raise AudioDeviceError("Payload is too large for ultrasonic transport.")

    return [
        _FRAGMENT_MAGIC + message_id + bytes((len(chunks), index, len(chunk))) + chunk
        for index, chunk in enumerate(chunks)
    ]


@dataclass
class _FragmentBuffer:
    total: int
    chunks: list[bytes | None] = field(init=False)

    def __post_init__(self) -> None:
        self.chunks = [None] * self.total


class FragmentReassembler:
    def __init__(self):
        self._buffers: dict[bytes, _FragmentBuffer] = {}

    def feed(self, packet: bytes) -> bytes | None:
        if not packet.startswith(_FRAGMENT_MAGIC):
            return packet
        if len(packet) < _FRAGMENT_HEADER_SIZE:
            raise AudioDeviceError("Received truncated transport fragment.")

        offset = len(_FRAGMENT_MAGIC)
        message_id = packet[offset:offset + _FRAGMENT_ID_SIZE]
        total = packet[offset + _FRAGMENT_ID_SIZE]
        index = packet[offset + _FRAGMENT_ID_SIZE + 1]
        chunk_len = packet[offset + _FRAGMENT_ID_SIZE + 2]

        if total == 0 or index >= total:
            raise AudioDeviceError("Received invalid transport fragment.")

        chunk_start = _FRAGMENT_HEADER_SIZE
        chunk_end = chunk_start + chunk_len
        if chunk_end > len(packet):
            raise AudioDeviceError("Received truncated transport fragment body.")

        buffer = self._buffers.get(message_id)
        if buffer is None:
            buffer = _FragmentBuffer(total)
            self._buffers[message_id] = buffer
        elif buffer.total != total:
            raise AudioDeviceError("Received inconsistent transport fragments.")

        buffer.chunks[index] = packet[chunk_start:chunk_end]
        if any(chunk is None for chunk in buffer.chunks):
            return None

        del self._buffers[message_id]
        return b"".join(chunk for chunk in buffer.chunks if chunk is not None)


class AudioTransmitter:
    def __init__(
        self,
        protocol_id: int = 4,
        volume: int = 100,
        rate: int = 48000,
        output_device_index: int | None = None,
    ):
        self.protocol_id = protocol_id
        self.volume = volume
        self.rate = rate
        self.output_device_index = output_device_index

    def send_bytes(self, payload: bytes) -> None:
        instance = ggwave.init()
        audio = pyaudio.PyAudio()
        stream = None

        try:
            stream_kwargs: dict = {
                "format": pyaudio.paFloat32,
                "channels": 1,
                "rate": self.rate,
                "output": True,
            }
            if self.output_device_index is not None:
                stream_kwargs["output_device_index"] = self.output_device_index
            stream = audio.open(**stream_kwargs)

            startup_silence = np.zeros(self.rate // 2, dtype=np.float32).tobytes()
            inter_packet_silence = np.zeros(self.rate // 5, dtype=np.float32).tobytes()
            stream.write(startup_silence)

            for packet in fragment_payload(payload):
                if len(packet) > MAX_GGWAVE_PAYLOAD_BYTES:
                    raise AudioDeviceError("Transport fragment exceeds ggwave payload limit.")

                waveform = ggwave.encode(
                    packet,
                    protocolId=self.protocol_id,
                    volume=self.volume,
                    instance=instance,
                )
                stream.write(waveform)
                stream.write(inter_packet_silence)

            # stream.write is blocking here; the short pause leaves the final
            # silence in the hardware buffer before stop_stream() runs.
            time.sleep(0.2)

        except Exception as exc:
            raise AudioDeviceError(f"Audio output error: {exc}") from exc
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()
            if hasattr(ggwave, "free"):
                ggwave.free(instance)


class AudioReceiver:
    def __init__(
        self,
        protocol_id: int = 4,
        input_device_index: int | None = None,
        rate: int = 48000,
        frames_per_buffer: int = 4096,
    ):
        self.protocol_id = protocol_id
        self.input_device_index = input_device_index
        self.rate = rate
        self.frames_per_buffer = frames_per_buffer

    def listen(
        self,
        stop_event: threading.Event,
        on_packet: Callable[[bytes], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        instance = ggwave.init()
        audio = pyaudio.PyAudio()
        stream = None
        reassembler = FragmentReassembler()

        try:
            kwargs = {
                "format": pyaudio.paFloat32,
                "channels": 1,
                "rate": self.rate,
                "input": True,
                "frames_per_buffer": self.frames_per_buffer,
            }
            if self.input_device_index is not None:
                kwargs["input_device_index"] = self.input_device_index

            stream = audio.open(**kwargs)

            while not stop_event.is_set():
                try:
                    chunk = stream.read(self.frames_per_buffer, exception_on_overflow=False)
                    samples = np.frombuffer(chunk, dtype=np.float32)
                    # Pass raw audio directly to ggwave — it has its own internal
                    # signal processing tuned for ultrasonic frequencies.  Any
                    # external filter (e.g. highpass) introduces phase distortion
                    # that corrupts ggwave's correlation and causes RS failures.
                    decoded = ggwave.decode(instance, samples.tobytes())
                    if decoded:
                        # Use len(decoded) to slice only the true payload bytes;
                        # ggwave's internal buffer may be larger than the message.
                        packet = bytes(decoded)[: len(decoded)]
                        reassembled = reassembler.feed(packet)
                        if reassembled is not None:
                            on_packet(reassembled)
                except Exception as exc:
                    on_error(AudioDeviceError(f"Audio input error: {exc}"))
                    break
        except Exception as exc:
            on_error(AudioDeviceError(f"Audio input error: {exc}"))
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()
            if hasattr(ggwave, "free"):
                ggwave.free(instance)
