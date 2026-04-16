class InfoSecError(Exception):
    """Base application error."""


class SettingsError(InfoSecError):
    """Raised when settings data is missing or invalid."""


class ProtocolError(InfoSecError):
    """Raised when a packet is malformed or unsupported."""


class CryptoError(InfoSecError):
    """Raised when key exchange or decryption fails."""


class AudioDeviceError(InfoSecError):
    """Raised when audio input or output is unavailable."""


class CommandBlockedError(InfoSecError):
    """Raised when a command is not allowed to execute."""


class CommandNotFoundError(InfoSecError):
    """Raised when a command name is unsupported."""

