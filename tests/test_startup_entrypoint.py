import importlib
import unittest


class StartupEntrypointTests(unittest.TestCase):
    def test_importing_package_entrypoint_has_no_side_effects(self) -> None:
        module = importlib.import_module("infosec_ultra.__main__")
        self.assertTrue(callable(module.main))


if __name__ == "__main__":
    unittest.main()

