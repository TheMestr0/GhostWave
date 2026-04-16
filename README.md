# InfoSec - Ultrasonic Secure Message Transfer

InfoSec is a Windows-first desktop demo for sending encrypted text messages or allowlisted commands between devices using ultrasonic audio. The project uses `customtkinter` for the desktop UI and a shared application core for audio transport, protocol framing, cryptography, settings management, and command approval.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application with the only official startup command:

```bash
python -m infosec_ultra
```

That command opens the launcher window. From the launcher you can choose:

- `Open Sender`
- `Open Receiver`

## How Startup Works

- `python -m infosec_ultra` opens the launcher UI
- the launcher starts either the Sender window or the Receiver window
- Sender and Receiver remain separate desktop apps, but startup now begins from one clean entrypoint

## Project Structure

```text
InfoSec/
|-- config/
|   |-- receiver.json
|   `-- sender.json
|-- infosec_ultra/
|   |-- __init__.py
|   |-- __main__.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- app_services.py
|   |   |-- audio_transport.py
|   |   |-- command_policy.py
|   |   |-- crypto_session.py
|   |   |-- errors.py
|   |   |-- protocol_codec.py
|   |   `-- settings.py
|   `-- ui/
|       |-- __init__.py
|       |-- launcher_window.py
|       |-- receiver_window.py
|       `-- sender_window.py
|-- tests/
|   |-- test_command_policy.py
|   |-- test_crypto_session.py
|   |-- test_message_flow.py
|   |-- test_protocol_codec.py
|   |-- test_settings.py
|   `-- test_startup_entrypoint.py
|-- requirements.txt
`-- README.md
```

## Architecture

### Core

- `audio_transport.py`: speaker output, microphone input, and input device enumeration
- `protocol_codec.py`: typed packet framing, validation, and Reed-Solomon error correction
- `crypto_session.py`: X25519 key generation, HKDF session derivation, payload encryption, and key fingerprinting
- `command_policy.py`: allowlisted local command handling and explicit approval flow
- `settings.py`: config file paths, bootstrap generation, and legacy settings migration
- `app_services.py`: sender and receiver orchestration logic

### UI

- `launcher_window.py`: single official startup window
- `sender_window.py`: sender desktop window
- `receiver_window.py`: receiver desktop window

## Configuration

The application now stores settings in:

- `config/sender.json`
- `config/receiver.json`

On first run:

- the receiver static keypair is generated automatically if missing
- the sender settings are populated with the receiver public key when needed

For compatibility with older layouts:

- if `sender_config.json` or `receiver_config.json` exist at the repository root
- and the new `config/` files do not exist yet
- the app copies the legacy settings into `config/sender.json` and `config/receiver.json`

## Protocol

The application uses two packet types:

```json
{"v":1,"t":"hello","sid":"...","spk":"<base64>","nonce":"<base64>"}
```

```json
{"v":1,"t":"data","sid":"...","ct":"<base64>"}
```

The decrypted payload is JSON:

```json
{"kind":"text","body":"Hello"}
```

or:

```json
{"kind":"command","body":"CALC"}
```

Supported commands:

- `CALC`
- `LOCK`
- `NOTEPAD`

No arbitrary shell command execution is supported.

## UI Overview

### Sender

- choose `text` or `command`
- enter text or choose an allowlisted command
- review or edit the receiver public key
- monitor sending status and the recent activity log

### Receiver

- monitor listening, session, and error states
- review the receiver key fingerprint
- choose the microphone input device
- enable or disable local command execution
- approve or reject pending commands

## Testing

Run the automated test suite with:

```bash
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The test suite covers:

- protocol frame validation and round-trip behavior
- session key derivation and decryption failure cases
- command allowlist and explicit approval behavior
- sender/receiver message flow without real audio transport
- settings migration and bootstrap behavior
- package startup import safety

## Security Notes

This project is still a demo-oriented system, not a production-grade secure messenger.

What is improved:

- session keys are no longer derived from public bytes alone
- packets are typed and versioned
- command execution is gated by local approval
- errors are explicit instead of being silently ignored

What remains out of scope for this version:

- full mutual endpoint authentication
- replay protection
- production hardening
- large payload transfer
