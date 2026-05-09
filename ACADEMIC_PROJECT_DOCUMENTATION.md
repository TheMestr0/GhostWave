# GhostWave: Secure Ultrasonic Message Transfer - Academic Project Documentation

## Document Metadata

**Project Title:** GhostWave: Secure Ultrasonic Message Transfer  
**Document Type:** Academic technical documentation  
**Primary Domain:** Information security, applied cryptography, acoustic data transfer  
**Implementation Language:** Python  
**Primary Interface:** Desktop graphical user interface  
**Repository Module:** `infosec_ultra`  
**Date:** May 2026

## Abstract

This document presents an academic documentation of GhostWave: Secure Ultrasonic Message Transfer. The project demonstrates how two nearby devices can exchange encrypted text messages or restricted commands over an acoustic channel using ultrasonic audio. The system combines audio-based data transfer, typed protocol framing, Reed-Solomon error correction, X25519 key agreement, HKDF-based key derivation, and authenticated symmetric encryption. The work is intended as an educational proof of concept rather than a production secure messenger. It highlights the engineering and security challenges involved in building a secure protocol over an unreliable, low-bandwidth, and noisy communication channel.

## Keywords

Ultrasonic communication, acoustic data transfer, secure messaging, X25519, HKDF, Fernet, Reed-Solomon, authenticated encryption, out-of-band communication, Python desktop application.

## 1. Introduction

Conventional secure messaging systems usually depend on network transports such as Wi-Fi, Ethernet, cellular networks, or Bluetooth. GhostWave explores a different communication model: transferring data through sound. In this model, the speaker of one device acts as the transmitter and the microphone of another device acts as the receiver.

The project is built around a simple but meaningful security question: how can a system protect message confidentiality and integrity when the underlying communication medium is weak, noisy, and not designed for reliable digital transport?

To answer this question, the application layers cryptographic protection and protocol-level reliability mechanisms over an acoustic channel. The Sender encrypts the payload before converting it into sound. The Receiver reconstructs the digital packet from microphone input and decrypts it only after establishing the correct session key. This design demonstrates an important principle in secure system design: the transport layer should not be trusted to provide confidentiality, authenticity, ordering, or reliability by itself.

## 2. Problem Statement

The project addresses the problem of secure short-message transfer over an unreliable non-network channel.

An audio channel introduces several technical and security challenges:

1. **Low bandwidth:** Acoustic data transfer can only carry small amounts of data per transmission.
2. **Noise sensitivity:** Background noise, speaker quality, microphone quality, distance, and room acoustics can corrupt signals.
3. **Packet loss:** The Receiver may miss one or more acoustic packets.
4. **Packet reordering:** A later packet may be decoded before an earlier session-establishment packet is available.
5. **Payload-size limits:** The selected audio modem library has practical limits on the amount of data that can be encoded in one acoustic packet.
6. **Key mismatch risk:** If the Sender encrypts to an outdated Receiver public key, decryption fails.
7. **Command-execution risk:** A system that accepts remote commands must prevent arbitrary code execution.

Therefore, the problem is not merely to send bytes through sound. The real problem is to build a controlled, understandable, and safer communication workflow that can tolerate some transport unreliability while preserving message confidentiality.

## 3. Proposed Solution

The project implements a two-application model:

- **Sender:** prepares a message or allowlisted command, encrypts it, frames it, fragments it if necessary, and transmits it as ultrasonic audio.
- **Receiver:** listens through the microphone, decodes acoustic packets, reassembles fragments, validates protocol frames, derives session keys, decrypts payloads, and displays received messages or pending commands.

The solution combines the following mechanisms:

1. **Typed protocol frames:** The system uses `hello` frames for session establishment and `data` frames for encrypted payloads.
2. **X25519 key agreement:** The Sender uses an ephemeral X25519 key pair and the Receiver uses a persistent X25519 key pair.
3. **HKDF session derivation:** The shared secret from X25519 is converted into a session key using HKDF.
4. **Authenticated encryption:** Payloads are encrypted using Fernet, which provides confidentiality and integrity protection.
5. **Reed-Solomon error correction:** Protocol frames are protected against limited corruption.
6. **Length-prefixed framing:** The encoded frame includes an explicit length prefix to prevent trailing decode artifacts from corrupting parsing.
7. **Transport fragmentation:** Large frames are split into smaller fragments that fit within the audio payload limit.
8. **Handshake repetition:** The Sender repeats the session-establishment frame to reduce the impact of packet loss.
9. **Pending data buffering:** The Receiver temporarily stores `data` frames that arrive before their matching `hello` frame.
10. **Command allowlisting:** The Receiver accepts only predefined commands and requires local approval.

## 4. System Architecture

The application is separated into two major layers: the user interface layer and the core logic layer.

```text
infosec_ultra/
|-- __main__.py
|-- core/
|   |-- app_services.py
|   |-- audio_transport.py
|   |-- command_policy.py
|   |-- crypto_session.py
|   |-- errors.py
|   |-- protocol_codec.py
|   `-- settings.py
`-- ui/
    |-- launcher_window.py
    |-- sender_window.py
    `-- receiver_window.py
```

### 4.1 User Interface Layer

The UI layer contains:

- `launcher_window.py`: opens Sender or Receiver from a single official entrypoint.
- `sender_window.py`: allows users to enter a text message or select an allowlisted command.
- `receiver_window.py`: displays listening status, received messages, pending commands, and local approval controls.

The UI is intentionally separated from cryptographic and transport operations. It invokes service classes but does not directly implement encryption, frame parsing, or audio decoding.

### 4.2 Core Logic Layer

The core layer contains:

- `app_services.py`: coordinates Sender and Receiver workflows.
- `audio_transport.py`: handles audio encoding, playback, recording, decoding, fragmentation, and reassembly.
- `protocol_codec.py`: serializes and validates typed protocol frames.
- `crypto_session.py`: implements key generation, key derivation, encryption, decryption, and key fingerprints.
- `command_policy.py`: restricts command handling to a local allowlist and approval flow.
- `settings.py`: manages configuration files and receiver key bootstrap.

## 5. Operational Workflow

### 5.1 Sender Workflow

The Sender performs the following steps:

1. Load `config/sender.json`.
2. Read the Receiver public key.
3. Generate a temporary X25519 key pair.
4. Generate a random nonce.
5. Derive a session key using X25519 and HKDF.
6. Build a `hello` frame containing session setup data.
7. Encrypt the payload and build a `data` frame.
8. Reed-Solomon encode and length-prefix the frames.
9. Fragment frames that exceed the acoustic payload limit.
10. Encode each fragment as audio using `ggwave`.
11. Play the generated waveform through the selected speaker.

### 5.2 Receiver Workflow

The Receiver performs the following steps:

1. Load `config/receiver.json`.
2. Start listening on the selected microphone input.
3. Decode audio into byte packets using `ggwave`.
4. Reassemble fragmented payloads.
5. Decode and validate protocol frames.
6. Process `hello` frames by deriving session keys.
7. Process `data` frames by decrypting payloads.
8. Display text messages or render command approval controls.

## 6. Protocol Design

The protocol uses two packet types.

### 6.1 Hello Frame

The `hello` frame establishes the cryptographic session:

```json
{
  "v": 1,
  "t": "hello",
  "sid": "...",
  "spk": "...",
  "nonce": "..."
}
```

Where:

- `v` is the protocol version.
- `t` is the frame type.
- `sid` is the session identifier.
- `spk` is the Sender ephemeral public key.
- `nonce` is a random value used by HKDF.

### 6.2 Data Frame

The `data` frame carries the encrypted payload:

```json
{
  "v": 1,
  "t": "data",
  "sid": "...",
  "ct": "..."
}
```

Where:

- `sid` links the data frame to a previously processed `hello` frame.
- `ct` is the encrypted ciphertext.

### 6.3 Frame Encoding

Each protocol frame is serialized as compact JSON, encoded using Reed-Solomon, and prefixed with a two-byte big-endian length. The length prefix allows the decoder to extract exactly the intended Reed-Solomon block even if the acoustic decoder returns trailing bytes.

## 7. Cryptographic Design

### 7.1 Key Agreement

The project uses X25519 for elliptic-curve Diffie-Hellman key agreement. X25519 is specified in RFC 7748 and is commonly used for efficient key agreement over Curve25519 [1].

The Receiver owns a persistent key pair stored in `config/receiver.json`. The Sender generates a new ephemeral key pair for each transmission. This produces forward-looking session separation: a new transmission does not reuse the same Sender private key.

### 7.2 Session-Key Derivation

The raw shared secret produced by X25519 is passed into HKDF. HKDF is specified in RFC 5869 and follows an extract-then-expand structure for deriving cryptographic keys from input keying material [2].

The project uses:

- The X25519 shared secret as input keying material.
- The `hello` nonce as HKDF salt.
- A protocol-specific context string as HKDF info.

### 7.3 Authenticated Encryption

The payload is encrypted using Fernet from the Python `cryptography` package. Fernet provides symmetric authenticated cryptography, meaning that a payload cannot be successfully decrypted if it was modified or encrypted under a different key [3].

This property is important because the audio channel can corrupt transmitted data. If a corrupted ciphertext reaches the decryption layer, Fernet authentication fails and the Receiver reports `decrypt_failed`.

## 8. Audio Transport Design

The project uses `ggwave` as the acoustic modem. `ggwave` is a data-over-sound library designed to transmit small amounts of data using audible or ultrasonic audio [4].

Audio input and output are handled through PyAudio, which provides Python bindings for PortAudio [5]. PortAudio is a cross-platform audio I/O library for real-time recording and playback [6].

The transport pipeline is:

```text
protocol frame -> transport fragments -> ggwave waveform -> speaker
speaker output -> microphone input -> ggwave decode -> fragments -> protocol frame
```

The implementation includes short silence intervals before and between acoustic packets. These intervals help separate consecutive packets during real playback and decoding.

## 9. Fragmentation and Reassembly

A practical issue emerged during implementation: real encrypted protocol frames can exceed the safe `ggwave` payload size. If a frame is passed to `ggwave` directly and exceeds the effective limit, it may be truncated before transmission.

The project solves this by fragmenting large byte payloads before audio encoding.

Each fragment contains:

```text
magic + message_id + total + index + chunk_length + chunk
```

The Receiver uses `message_id`, `total`, and `index` to reconstruct the original payload once all fragments arrive. This method is not a full reliable transport protocol, but it is sufficient for the project's controlled demonstration and avoids known truncation problems.

## 10. Error Handling

The system defines explicit error states instead of silently ignoring failures.

### 10.1 `invalid_packet`

The received bytes cannot be parsed as a valid protocol frame. Possible causes include excessive acoustic corruption or malformed input.

### 10.2 `waiting_for_handshake`

A `data` frame arrived before the matching `hello` frame. The Receiver stores the `data` frame temporarily and waits for the session setup frame.

### 10.3 `invalid_handshake`

The Receiver could not process the `hello` frame, usually because the frame is malformed or key derivation failed.

### 10.4 `decrypt_failed`

The ciphertext could not be decrypted with the derived session key. Common causes include key mismatch, corrupted ciphertext, or data from a different session.

### 10.5 `audio_device_error`

The audio input or output device failed, or PyAudio/PortAudio could not open the requested device.

## 11. Command Security Model

The project supports command payloads only as a controlled demonstration. It does not support arbitrary shell execution.

The allowed commands are:

- `CALC`
- `LOCK`
- `NOTEPAD`

The Receiver requires command execution to be enabled locally, and received commands must be approved by the local user. This reduces the risk of the Sender gaining uncontrolled authority over the Receiver machine.

## 12. Testing and Validation

The project includes automated tests under the `tests` directory. The tests validate:

- Protocol round trips.
- Rejection of malformed frames.
- Decryption failure under the wrong key.
- Sender and Receiver session-key agreement.
- Text-message flow without real audio hardware.
- Command policy behavior.
- Handling of `data` frames that arrive before `hello`.
- Audio transport fragmentation under the `ggwave` payload limit.
- Settings bootstrap and migration behavior.

The test suite is run with:

```bash
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Automated testing is important because the system crosses multiple domains: cryptography, protocol design, audio transport, configuration management, and UI orchestration.

## 13. Limitations

The system is intentionally scoped as a proof of concept. Its limitations include:

1. It does not provide full mutual authentication.
2. It does not implement robust replay protection.
3. It does not implement retransmission requests or acknowledgments.
4. It is limited to small messages.
5. It depends heavily on audio hardware and environmental conditions.
6. It stores local configuration keys in plain JSON files.
7. It does not attempt to hide that communication is occurring.
8. It is not designed for adversarial acoustic environments.

These limitations are acceptable for an educational demonstration, but they would need to be addressed for a production security system.

## 14. Future Work

Future improvements could include:

- Digitally signing `hello` frames to authenticate long-term identities.
- Adding replay protection using counters or timestamps.
- Implementing acknowledgments and retransmission.
- Adding session cleanup policies.
- Encrypting or protecting local configuration files.
- Improving acoustic calibration and device selection.
- Adding measurable performance metrics such as packet success rate and decode latency.
- Supporting a formal threat model and security analysis.

## 15. Conclusion

GhostWave: Secure Ultrasonic Message Transfer demonstrates how secure communication concepts can be applied over an unconventional and unreliable transport channel. By combining acoustic data transfer, protocol framing, error correction, key agreement, key derivation, and authenticated encryption, the project shows how layered security design can compensate for weaknesses in the underlying channel.

The project is academically useful because it makes several abstract security concepts visible in a working system. It shows that confidentiality does not come from the transport medium, but from cryptographic design. It also shows that real-world systems must handle packet loss, decoding artifacts, key mismatch, and unsafe command behavior explicitly.

The final result is a compact proof of concept for secure ultrasonic communication, suitable for demonstration, analysis, and further extension.

## References

[1] A. Langley, M. Hamburg, and S. Turner, "Elliptic Curves for Security," RFC 7748, Internet Research Task Force, Jan. 2016. Available: https://www.rfc-editor.org/rfc/rfc7748

[2] H. Krawczyk and P. Eronen, "HMAC-based Extract-and-Expand Key Derivation Function (HKDF)," RFC 5869, Internet Engineering Task Force, May 2010. Available: https://www.rfc-editor.org/rfc/rfc5869

[3] Python Cryptographic Authority, "Fernet (symmetric encryption)," cryptography documentation. Available: https://cryptography.io/en/latest/fernet/

[4] G. Gerganov, "ggwave: Tiny data-over-sound library," GitHub repository. Available: https://github.com/ggerganov/ggwave

[5] H. Pham, "PyAudio," Python Package Index. Available: https://pypi.org/project/PyAudio/

[6] PortAudio Project, "PortAudio Documentation." Available: https://www.portaudio.com/docs/v19-doxydocs/

[7] T. Manz, "reedsolo: Pure-Python Reed Solomon encoder/decoder," Python Package Index. Available: https://pypi.org/project/reedsolo/

[8] National Institute of Standards and Technology, "Recommendation for Pair-Wise Key-Establishment Schemes Using Discrete Logarithm Cryptography," NIST SP 800-56A Rev. 3, Apr. 2018. Available: https://csrc.nist.gov/pubs/sp/800/56/a/r3/final

[9] G. Blelloch, "Reed-Solomon Codes," Carnegie Mellon University technical note. Available: https://www.cs.cmu.edu/~guyb/realworld/reedsolomon/reed_solomon_codes.html
