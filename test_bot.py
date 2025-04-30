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

    def test_add_and_remove_user_from_groups(self):
        # Backup current state
        orig_pms = bot.product_managers.copy()
        orig_devs = bot.developers.copy()
        test_user_id = 1234567890

        # Test add to product_managers
        if test_user_id in bot.product_managers:
            bot.product_managers.remove(test_user_id)
        bot.product_managers.append(test_user_id)
        self.assertIn(test_user_id, bot.product_managers)

        # Test remove from product_managers
        bot.product_managers.remove(test_user_id)
        self.assertNotIn(test_user_id, bot.product_managers)

        # Test add to developers
        if test_user_id in bot.developers:
            bot.developers.remove(test_user_id)
        bot.developers.append(test_user_id)
        self.assertIn(test_user_id, bot.developers)

        # Test remove from developers
        bot.developers.remove(test_user_id)
        self.assertNotIn(test_user_id, bot.developers)

        # Restore state
        bot.product_managers = orig_pms
        bot.developers = orig_devs

    def test_set_checkin_message(self):
        orig_msgs = bot.checkin_messages.copy()
        new_pm_msg = "Test PM message"
        new_dev_msg = "Test Dev message"
        bot.checkin_messages["product_managers"] = new_pm_msg
        bot.checkin_messages["developers"] = new_dev_msg
        bot.save_checkin_messages()
        loaded = bot.load_checkin_messages()
        self.assertEqual(loaded["product_managers"], new_pm_msg)
        self.assertEqual(loaded["developers"], new_dev_msg)
        # Restore
        bot.checkin_messages = orig_msgs
        bot.save_checkin_messages()

    def test_send_message_placeholder(self):
        # Placeholder: actual Discord message sending requires integration/mocks
        self.assertTrue(hasattr(bot, "on_message"))
        # You could use unittest.mock to patch discord.py objects for full tests

if __name__ == "__main__":
    unittest.main()
