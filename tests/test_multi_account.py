import os
import unittest
from unittest.mock import patch

import checkin


class MultiAccountTests(unittest.TestCase):
    def config(self, **env):
        with patch.dict(os.environ, env, clear=True):
            return checkin.Config()

    def test_legacy_single_account(self):
        self.assertEqual(self.config(GLADOS_COOKIES="fake-one").cookies_list, ["fake-one"])

    def test_separate_accounts_and_deduplication(self):
        config = self.config(GLADOS_COOKIES=" fake-one & fake-two ",
                             GLADOS_COOKIES_2="fake-two & fake-three")
        self.assertEqual(config.cookies_list, ["fake-one", "fake-two", "fake-three"])

    def test_optional_and_second_only(self):
        self.assertEqual(self.config().cookies_list, [])
        self.assertEqual(self.config(GLADOS_COOKIES_2="fake-two").cookies_list, ["fake-two"])

    def run_main(self, statuses):
        config = self.config(GLADOS_COOKIES="fake-one", GLADOS_COOKIES_2="fake-two")
        calls = []

        def perform(checker, cookie, index, domain):
            calls.append((cookie, index))
            return checkin.CheckinResult(index, domain,
                status={checkin.CheckinStatus.SUCCESS: "签到成功",
                        checkin.CheckinStatus.REPEAT: "重复签到"}.get(statuses[index - 1], "签到失败"),
                code=statuses[index - 1])

        with patch.object(checkin, "Config", return_value=config), \
             patch.object(checkin.Checker, "_checkin_on_domain", perform), \
             patch.object(checkin.PushService, "send"):
            try:
                checkin.main()
                exit_code = 0
            except SystemExit as error:
                exit_code = error.code
        self.assertEqual(calls, [("fake-one", 1), ("fake-two", 2)])
        return exit_code

    def test_failure_does_not_skip_other_account(self):
        self.assertEqual(self.run_main([checkin.CheckinStatus.FAILURE,
                                        checkin.CheckinStatus.SUCCESS]), 1)

    def test_success_and_repeat_are_accepted(self):
        self.assertEqual(self.run_main([checkin.CheckinStatus.SUCCESS,
                                        checkin.CheckinStatus.REPEAT]), 0)


if __name__ == "__main__":
    unittest.main()
