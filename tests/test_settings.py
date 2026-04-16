import tempfile
import unittest
from pathlib import Path

from infosec_ultra.core.settings import (
    ensure_local_settings,
    get_settings_paths,
    migrate_legacy_settings,
)


class SettingsTests(unittest.TestCase):
    def test_legacy_settings_migrate_into_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = get_settings_paths(root)

            paths.legacy_sender_path.write_text('{"device_name":"Legacy Sender"}', encoding="utf-8")
            paths.legacy_receiver_path.write_text('{"device_name":"Legacy Receiver"}', encoding="utf-8")

            migrate_legacy_settings(paths)

            self.assertTrue(paths.sender_path.exists())
            self.assertTrue(paths.receiver_path.exists())
            self.assertIn("Legacy Sender", paths.sender_path.read_text(encoding="utf-8"))
            self.assertIn("Legacy Receiver", paths.receiver_path.read_text(encoding="utf-8"))

    def test_ensure_local_settings_bootstraps_receiver_keypair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sender_settings, receiver_settings = ensure_local_settings(get_settings_paths(Path(temp_dir)))

            self.assertTrue(sender_settings.receiver_public_key)
            self.assertTrue(receiver_settings.receiver_private_key)
            self.assertTrue(receiver_settings.receiver_public_key)


if __name__ == "__main__":
    unittest.main()

