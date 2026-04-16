import threading
from collections.abc import Callable

import ggwave
import numpy as np
import pyaudio
from scipy.signal import butter, lfilter

from .errors import AudioDeviceError


def list_input_devices() -> list[dict]:
    audio = pyaudio.PyAudio()
    devices = []
    try:
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            if int(info.get("maxInputChannels", 0)) > 0:
                devices.append({"index": index, "name": info.get("name", f"Input {index}")})
    finally:
        audio.terminate()
    return devices


class AudioTransmitter:
    def __init__(self, protocol_id: int = 4, volume: int = 100, rate: int = 48000):
        self.protocol_id = protocol_id
        self.volume = volume
        self.rate = rate

    def send_bytes(self, payload: bytes) -> None:
        instance = ggwave.init()
        audio = pyaudio.PyAudio()
        stream = None

        try:
            waveform = ggwave.encode(
                payload,
                protocolId=self.protocol_id,
                volume=self.volume,
                instance=instance,
            )
            stream = audio.open(format=pyaudio.paFloat32, channels=1, rate=self.rate, output=True)
            stream.write(np.zeros(self.rate // 2, dtype=np.float32).tobytes())
            stream.write(waveform)
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
        highpass_hz: int = 16000,
    ):
        self.protocol_id = protocol_id
        self.input_device_index = input_device_index
        self.rate = rate
        self.frames_per_buffer = frames_per_buffer
        self.highpass_hz = highpass_hz

    def listen(
        self,
        stop_event: threading.Event,
        on_packet: Callable[[bytes], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        instance = ggwave.init()
        audio = pyaudio.PyAudio()
        stream = None

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
            nyquist = 0.5 * self.rate
            b_coeff, a_coeff = butter(5, self.highpass_hz / nyquist, btype="high")

            while not stop_event.is_set():
                try:
                    chunk = stream.read(self.frames_per_buffer, exception_on_overflow=False)
                    samples = np.frombuffer(chunk, dtype=np.float32)
                    filtered = lfilter(b_coeff, a_coeff, samples).astype(np.float32)
                    decoded = ggwave.decode(instance, filtered.tobytes())
                    if decoded:
                        on_packet(bytes(decoded))
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
