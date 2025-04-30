import unittest
import os
from dotenv import load_dotenv
import bot

class TestBotFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()

    def test_get_gsheet(self):
        # Just test that it does not raise an error for a valid tab name (sheet may not exist)
        try:
            bot.get_gsheet(bot.SHEET_PM_TAB)
        except Exception as e:
            self.assertNotIsInstance(e, Exception, f"get_gsheet raised an error: {e}")

    def test_load_groups(self):
        pms, devs = bot.load_groups()
        self.assertIsInstance(pms, list)
        self.assertIsInstance(devs, list)

    def test_load_checkin_messages(self):
        msgs = bot.load_checkin_messages()
        self.assertIn("product_managers", msgs)
        self.assertIn("developers", msgs)

    def test_save_checkin_messages(self):
        # Should not raise error
        try:
            bot.save_checkin_messages()
        except Exception as e:
            self.fail(f"save_checkin_messages raised an error: {e}")

if __name__ == "__main__":
    unittest.main()
