import unittest
from unittest import mock

from infosec_ultra.core.command_policy import CommandPolicy
from infosec_ultra.core.errors import CommandBlockedError


class CommandPolicyTests(unittest.TestCase):
    def test_allowlisted_command_is_queued(self) -> None:
        policy = CommandPolicy(enabled=True, allowed_commands=["CALC"])
        pending = policy.submit("calc", "session-1")
        self.assertEqual("CALC", pending.command_name)
        self.assertEqual(1, len(policy.pending_commands()))

    def test_command_rejected_when_disabled(self) -> None:
        policy = CommandPolicy(enabled=False, allowed_commands=["CALC"])
        with self.assertRaises(CommandBlockedError):
            policy.submit("CALC", "session-1")

    @mock.patch("infosec_ultra.core.command_policy.execute_command")
    def test_pending_command_requires_explicit_approval(self, mocked_execute) -> None:
        policy = CommandPolicy(enabled=True, allowed_commands=["CALC"])
        pending = policy.submit("CALC", "session-1")

        mocked_execute.assert_not_called()
        policy.approve(pending.command_id)
        mocked_execute.assert_called_once_with("CALC")


if __name__ == "__main__":
    unittest.main()

