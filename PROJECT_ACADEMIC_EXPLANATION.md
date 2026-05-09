# Academic Explanation of the InfoSec Ultrasonic Project

## 1. General Introduction

**InfoSec Ultrasonic Secure Message Transfer** is an educational desktop application that demonstrates how encrypted text messages or restricted local commands can be transferred between two devices using ultrasonic audio. The project is not intended to be a production-grade secure messenger. Instead, it is a practical proof of concept that combines several important topics in information security and software engineering:

- Communication over a non-traditional channel, specifically audio.
- Asymmetric cryptography for session-key agreement.
- Symmetric authenticated encryption for protecting message contents.
- A small typed packet protocol.
- Error handling for unreliable transport conditions, such as packet loss or packet reordering.
- A local command policy that prevents arbitrary remote command execution.

The core idea is that one device acts as the **Sender**. It creates an encrypted message, converts it into ultrasonic audio using `ggwave`, and plays that audio through the speaker. Another device acts as the **Receiver**. It listens through the microphone, decodes the audio back into bytes, parses the protocol frame, derives the session key, and decrypts the message.

## 2. The Problem the Project Demonstrates

Most device-to-device communication happens through conventional networks such as Wi-Fi, Ethernet, Bluetooth, or cellular links. This project explores an alternative communication channel often described as **out-of-band communication**. In this case, the out-of-band channel is air, and the carrier medium is sound.

From an academic point of view, the project asks an important question:

> Can two devices exchange protected data over a simple audio channel while reducing the security risks caused by the weakness of that channel?

The project's answer is yes, at least as a controlled demonstration. However, the limitations must be understood. Audio transport is noisy, low-bandwidth, and vulnerable to packet loss, distortion, and environmental interference. The project therefore does not rely on audio alone. It adds:

- Reed-Solomon error correction.
- Fragmentation for packets larger than `ggwave` can safely carry.
- A temporary encrypted session for each transmission.
- Versioned and typed protocol frames.
- A strict command allowlist.
- Explicit local approval before executing received commands.

## 3. High-Level Architecture

The project is divided into two major layers:

1. The graphical user interface layer, located under `ui`.
2. The application core layer, located under `core`.

This separation is important because the user interface should not own the security or transport logic. The UI is responsible for buttons, input fields, device selection, status display, and activity logs. The core layer is responsible for cryptography, protocol framing, audio transport, settings, and command policy.

The project structure is:

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

## 4. Official Startup Path

The official startup command is:

```bash
python -m infosec_ultra
```

This command executes:

```text
infosec_ultra/__main__.py
```

The entrypoint does not directly send or receive messages. It opens a launcher window. From that launcher, the user can open either:

- Sender
- Receiver

This design gives the project one clear startup path instead of requiring the user to run individual UI files manually.

## 5. Sender Responsibilities

The Sender is the component that creates and transmits protected content. Its job is not simply to play a sound. A complete send operation includes the following steps:

1. Read sender settings from `config/sender.json`.
2. Load the Receiver public key.
3. Generate an ephemeral X25519 key pair for the Sender.
4. Generate a random nonce.
5. Derive a session key.
6. Build a `hello` frame.
7. Encrypt the payload and build a `data` frame.
8. Pass the frames to the audio transport layer.
9. Convert the frames into ultrasonic waveforms.
10. Play the audio through the selected output device.

The Sender never transmits plaintext message content directly. The text or command is encrypted first, and only the resulting ciphertext is sent.

## 6. Receiver Responsibilities

The Receiver listens for audio and reconstructs the original secure message. Its workflow includes:

1. Read receiver settings from `config/receiver.json`.
2. Load the Receiver private and public keys.
3. Open the microphone using `pyaudio`.
4. Pass audio samples to `ggwave.decode`.
5. Reassemble fragmented transport packets when needed.
6. Decode the protocol frame.
7. Process the `hello` frame to derive the session key.
8. Process the `data` frame and decrypt the payload.
9. Display a text message or render a pending command approval card.

The Receiver does not assume packets always arrive in the ideal order. If a `data` frame arrives before its matching `hello` frame, the Receiver temporarily stores the `data` frame and waits for the `hello` frame for a short time.

## 7. Why the Sender Produces More Than One Sound

It is normal for the Sender to produce more than one audible or near-audible burst.

The transmission is not a single logical packet. The protocol has different frame types:

1. `hello`
2. `data`

The `hello` frame carries session setup information, including the Sender ephemeral public key, nonce, and session id. The `data` frame carries the encrypted payload.

To improve reliability, the Sender currently repeats the `hello` frame before sending the `data` frame. Therefore, a typical logical transmission may look like this:

```text
hello
hello
data
```

In addition, because `ggwave` has a practical payload limit, a single logical frame may be split into smaller transport fragments. In that case, the user may hear even more audio bursts. That is expected behavior, not a bug.

## 8. Audio Transport Layer

The audio transport layer is implemented in:

```text
infosec_ultra/core/audio_transport.py
```

It uses:

- `ggwave` to convert bytes into audio waveforms and decode audio back into bytes.
- `pyaudio` to interact with speakers and microphones.
- `numpy` to generate short silence buffers between packets.

The conceptual pipeline is:

```text
bytes -> ggwave.encode -> waveform -> speaker -> air -> microphone -> ggwave.decode -> bytes
```

However, audio is an unreliable channel. One of the most important practical limitations is the payload size supported by `ggwave`. In this project, the effective maximum payload size is treated as:

```text
140 bytes
```

If a packet is larger than that, `ggwave` may truncate it. Truncation destroys the packet and makes decryption impossible. The project therefore implements fragmentation before encoding packets as audio.

## 9. Transport Fragmentation

Some real protocol frames are larger than 140 bytes, especially `data` frames because Fernet ciphertext is relatively long.

The `fragment_payload` function splits oversized payloads into fragments that fit within the audio transport limit.

Each fragment contains a small transport header:

```text
magic + message_id + total + index + chunk_length + chunk
```

The fields are:

- `magic`: a fixed marker indicating that the packet is a transport fragment.
- `message_id`: a random identifier shared by all fragments of the same original payload.
- `total`: the total number of fragments.
- `index`: the index of the current fragment.
- `chunk_length`: the number of payload bytes in this fragment.
- `chunk`: the actual fragment data.

On the receiving side, `FragmentReassembler` groups fragments by `message_id`. Once all fragments are present, it reconstructs the original payload and passes it to the protocol layer.

This design keeps transport concerns separate from protocol concerns. The protocol layer receives complete frames and does not need to know whether they were sent as one audio packet or several audio fragments.

## 10. Message Protocol

The protocol is implemented in:

```text
infosec_ultra/core/protocol_codec.py
```

The project uses two frame types:

### 10.1 Hello Frame

Example:

```json
{
  "v": 1,
  "t": "hello",
  "sid": "...",
  "spk": "...",
  "nonce": "..."
}
```

Field meanings:

- `v`: protocol version.
- `t`: frame type, here `hello`.
- `sid`: session identifier.
- `spk`: Sender ephemeral public key.
- `nonce`: random value used during session-key derivation.

### 10.2 Data Frame

Example:

```json
{
  "v": 1,
  "t": "data",
  "sid": "...",
  "ct": "..."
}
```

Field meanings:

- `v`: protocol version.
- `t`: frame type, here `data`.
- `sid`: session identifier. It must match the session id from the `hello` frame.
- `ct`: ciphertext.

## 11. Why Session IDs Are Needed

The session id links a `hello` frame and its corresponding `data` frame.

When the Receiver processes a `hello` frame, it stores the derived session information:

```text
sessions[session_id] = session_info
```

When a `data` frame arrives, the Receiver looks up its session id. If the session exists, the Receiver uses the corresponding session key to decrypt the ciphertext. If the session is missing, the `data` frame may have arrived before the `hello` frame, or the `hello` frame may have been lost.

Earlier behavior produced:

```text
invalid_handshake: Unknown session id
```

The improved behavior stores early `data` frames temporarily and waits for the matching `hello`.

## 12. Reed-Solomon Error Correction

Before transmission, the protocol codec serializes a JSON frame into bytes and applies Reed-Solomon encoding.

Reed-Solomon adds parity bytes that allow the receiver to correct a limited amount of corruption. This is useful because audio transport may introduce noise, clipping, or decoding errors.

However, Reed-Solomon cannot recover from every failure. If the corruption is too large, or if the packet is truncated or completely missing, recovery is impossible. That is why Reed-Solomon is combined with:

- Transport fragmentation.
- Repeated `hello` frames.
- Temporary buffering of early `data` frames.

## 13. Frame Length Prefix

In some cases, `ggwave.decode` may return a buffer that contains trailing garbage or padding. To make frame parsing deterministic, the project prefixes each encoded Reed-Solomon block with a two-byte length.

The structure is:

```text
2-byte length + Reed-Solomon block
```

During decoding:

1. The Receiver reads the first two bytes.
2. It determines the expected Reed-Solomon block length.
3. It extracts exactly that many bytes.
4. It ignores any extra bytes after the expected block.

This makes the protocol more tolerant of trailing data produced by the audio decode layer.

## 14. Cryptography Overview

Cryptographic logic is implemented in:

```text
infosec_ultra/core/crypto_session.py
```

The project uses:

- X25519 for key agreement.
- HKDF for deriving a session key.
- Fernet for authenticated symmetric encryption.
- SHA-256 to display short public-key fingerprints.

## 15. X25519

X25519 is an elliptic-curve Diffie-Hellman key agreement algorithm. It allows two parties to derive the same shared secret without transmitting that shared secret over the channel.

In this project:

- The Receiver owns a persistent key pair stored in `config/receiver.json`.
- The Sender generates a new ephemeral key pair for each transmission.

The Sender computes the shared secret using:

```text
receiver_public_key + sender_private_key
```

The Receiver computes the shared secret using:

```text
sender_public_key + receiver_private_key
```

If the keys are correct, both sides derive the same shared secret.

## 16. HKDF

The shared secret produced by X25519 is not used directly as an encryption key. Instead, the project passes it through HKDF.

HKDF derives a suitable encryption key using:

- `salt`: the nonce from the `hello` frame.
- `info`: the fixed context string `infosec-ultra/v1`.

This makes the derived key specific to the protocol and to the current session.

## 17. Fernet

Fernet provides authenticated symmetric encryption. This means the payload is both encrypted and integrity-protected. If the ciphertext is modified, corrupted, or decrypted with the wrong key, decryption fails.

When the Receiver logs:

```text
decrypt_failed: Decrypt failed.
```

the likely causes are:

- The Sender is using a Receiver public key that does not match the current Receiver private key.
- The `data` frame was corrupted.
- The `data` frame belongs to an older or different session.
- The `hello` and `data` frames did not come from the same transmission.

In practical use, the most common cause is a stale `receiver_public_key` in `config/sender.json`.

## 18. Public-Key Fingerprints

Public keys are long and inconvenient to compare manually. The project therefore displays a short fingerprint derived from SHA-256.

Example:

```text
f0bd:0e76:7957:8452
```

The fingerprint helps the user verify that the Sender is targeting the correct Receiver public key. If the Sender fingerprint does not match the Receiver fingerprint, decryption will fail.

## 19. Payload Format After Decryption

The decrypted payload is a JSON object. It has two supported forms.

### Text Payload

```json
{
  "kind": "text",
  "body": "Hello"
}
```

### Command Payload

```json
{
  "kind": "command",
  "body": "CALC"
}
```

This structure is more explicit than sending a raw string. It tells the Receiver how to interpret the payload.

## 20. Command Policy

Remote command execution is dangerous if unrestricted. The project therefore does not support arbitrary shell execution.

The only supported commands are:

- `CALC`
- `LOCK`
- `NOTEPAD`

Even these commands are not executed blindly. Command execution must be enabled locally, and pending commands require explicit approval by the Receiver user.

This is an important security decision. Receiving a message from another device must not automatically grant that device full local control.

## 21. Settings Management

Settings are stored in:

```text
config/sender.json
config/receiver.json
```

The Sender settings usually contain:

- Device name.
- Receiver public key.
- Protocol id.
- Output volume.
- Output device index.

The Receiver settings usually contain:

- Device name.
- Input device index.
- Protocol id.
- Whether command execution is enabled.
- Allowed command names.
- Receiver private key.
- Receiver public key.

On first run, if the Receiver key pair is missing, the project generates it automatically.

## 22. Why Decryption Can Fail

Decryption can fail for several reasons.

### 22.1 Mismatched Receiver Public Key

If the Sender uses an old or incorrect Receiver public key, it derives a different session key from the one derived by the Receiver.

Result:

```text
decrypt_failed
```

### 22.2 Corrupted Data Frame

If the `data` frame is corrupted beyond Reed-Solomon's correction capacity, decryption may fail.

### 22.3 Data From a Different Session

If the Receiver attempts to decrypt a `data` frame with the wrong session key, Fernet authentication fails.

### 22.4 Poor Audio Conditions

Low volume, the wrong microphone, poor speakers, background noise, or long distance between devices can all damage the received data.

## 23. Why `waiting_for_handshake` Can Appear

This message means the Receiver decoded a `data` frame but does not yet have the session key for it.

Possible causes:

- The `hello` frame has not arrived yet.
- The `hello` frame has not finished reassembling.
- The `hello` frame was lost.
- The `data` frame arrived before `hello`.

The current behavior is:

- Store the `data` frame temporarily.
- Wait for a matching `hello` frame.
- Process the stored `data` frame automatically once the session becomes available.

## 24. Current Project Limitations

Although the project uses real cryptography, it is still a demo system.

Current limitations include:

- No complete mutual endpoint authentication.
- No strong replay protection.
- No advanced session lifecycle management.
- Low bandwidth due to audio transport.
- Reliability depends heavily on the acoustic environment.
- No protocol negotiation.
- No production-grade hardening.

These limitations do not reduce the educational value of the project. They clarify the difference between a proof of concept and a production security system.

## 25. Full Message Flow

A complete text message follows this path:

1. The user types a message in the Sender window.
2. The Sender reads the Receiver public key.
3. The Sender generates an ephemeral X25519 key pair.
4. The Sender generates a nonce.
5. The Sender derives a session key.
6. The Sender builds a `hello` frame.
7. The Sender encrypts the payload using Fernet.
8. The Sender builds a `data` frame.
9. `ProtocolCodec` serializes frames and applies Reed-Solomon.
10. The audio transport layer fragments packets larger than 140 bytes.
11. `ggwave` converts each fragment into an audio waveform.
12. `pyaudio` plays the waveform through the speaker.
13. The Receiver captures audio through the microphone.
14. `ggwave` decodes audio back into bytes.
15. `FragmentReassembler` reconstructs fragmented payloads.
16. `ProtocolCodec` decodes the complete frame.
17. If the frame is `hello`, the Receiver derives the session key.
18. If the frame is `data`, the Receiver decrypts the ciphertext.
19. If the payload is text, it appears in the activity log.
20. If the payload is a command, it appears as a pending approval item.

## 26. Tests and Project Quality

The project includes tests under the `tests` directory.

The tests cover:

- Protocol round trips.
- Rejection of invalid JSON.
- Rejection of unsupported protocol versions.
- Key derivation.
- Decryption failure with the wrong key.
- Command allowlist behavior.
- Full message flow without real audio hardware.
- `data` arriving before `hello`.
- Fragmentation under the `ggwave` payload limit.
- Settings migration and key bootstrap.

These tests matter because the project combines several layers. A small change in audio transport or framing can break cryptography or message flow. Tests catch those regressions early.

## 27. Important Error Messages

### `invalid_packet`

The received bytes do not represent a valid protocol frame. The data may be corrupted or Reed-Solomon correction may have failed.

### `waiting_for_handshake`

A `data` frame arrived before the matching `hello` frame. The Receiver will wait temporarily.

### `invalid_handshake`

The `hello` frame was invalid, or the Receiver could not derive a session key from it.

### `decrypt_failed`

The ciphertext could not be decrypted with the current session key. The most common cause is a mismatched Receiver public key in the Sender settings.

### `audio_device_error`

There is a problem with the microphone, speaker, PortAudio, PyAudio, or selected audio device.

## 28. Security Considerations

The project uses several reasonable security practices:

- Plaintext is not transmitted.
- A key agreement protocol is used instead of a static shared password.
- A temporary session key is derived per transmission.
- Authenticated encryption is used.
- Arbitrary commands are not supported.
- Local approval is required for commands.

If the system were extended toward production, the following improvements would be important:

- Long-term mutual authentication.
- Replay protection using counters, timestamps, or signed nonces.
- Digital signatures for `hello` frames.
- Better session cleanup and lifecycle management.
- Rate limiting.
- Local protection for configuration files.
- Security audit logging.

## 29. Practical Operating Notes

For best results:

- Open the Receiver first.
- Wait until it shows `Listening`.
- Ensure the Sender uses the current Receiver public key.
- Use an appropriate output volume.
- Keep the devices close enough.
- Reduce background noise.
- Select the correct input and output devices.
- Avoid very long messages.

Hearing multiple audio bursts is normal. The Sender transmits `hello`, may repeat it, then transmits `data`. Each logical frame may also be split into smaller audio fragments.

## 30. Conclusion

This project is a useful educational demonstration that combines information security, acoustic communication, and practical software architecture. Its value is not that it replaces conventional networking, but that it shows how a secure protocol can be layered over an unreliable transport medium.

The central idea is:

```text
Do not trust the transport channel. Design the protocol to tolerate its weaknesses.
```

The project therefore combines:

- Encryption for confidentiality.
- Key agreement for session security.
- Error correction for noisy transport.
- Fragmentation for audio payload limits.
- Command policy for local safety.
- Tests for behavioral stability.

Together, these elements make the project a clear and extensible proof of concept for secure ultrasonic communication.
