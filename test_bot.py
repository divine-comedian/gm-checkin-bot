import unittest
import os
import tempfile
import asyncio
from unittest import mock

# ensure required env vars so bot imports without errors
os.environ.setdefault('DISCORD_BOT_TOKEN', 'dummy')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123:ABC')

import bot

class TestPingHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        bot.PING_HISTORY_FILE = self.tmp.name
        bot.ping_history = {}

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def test_load_and_save_ping_history(self):
        data = {'1': '2024-01-01T00:00:00'}
        bot.save_ping_history(data)
        loaded = bot.load_ping_history()
        self.assertEqual(data, loaded)

    def test_process_ping_history(self):
        class FakeCell:
            def __init__(self, row, col):
                self.row = row
                self.col = col
        class FakeSheet:
            def __init__(self, value):
                self.value = value
            def find(self, v):
                if v == 'tester#1234':
                    return FakeCell(2,1)
                if v == bot.get_week_str():
                    return FakeCell(1,2)
                return None
            def cell(self, r, c):
                class Obj:
                    def __init__(self, val):
                        self.value = val
                if r == 2 and c == 2:
                    return Obj(self.value)
                return Obj(None)
        async def run(value):
            bot.ping_history = {'1': '2000-01-01T00:00:00'}
            bot.groups['developers']['discord'] = [1]
            fake_user = mock.AsyncMock()
            fake_user.name = 'tester'
            fake_user.discriminator = '1234'
            with mock.patch.object(bot.bot, 'fetch_user', return_value=fake_user):
                await bot.process_ping_history(sheet=FakeSheet(value))
            return fake_user
        # case: entry exists -> removed
        fake_user = asyncio.run(run('done'))
        self.assertNotIn('1', bot.ping_history)
        # case: empty -> reminder sent
        bot.ping_history = {'1': '2000-01-01T00:00:00'}
        fake_user = asyncio.run(run(''))
        fake_user.send.assert_called()

if __name__ == '__main__':
    unittest.main()
