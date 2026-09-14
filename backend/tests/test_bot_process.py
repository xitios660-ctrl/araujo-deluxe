import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from bot_process import BotProcess


class BotProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_bot_does_not_spawn_local_process(self):
        bot = BotProcess("https://bot.example.com")
        with patch("bot_process.shutil.which") as which:
            await bot.start()
        which.assert_not_called()
        self.assertIsNone(bot.task)

    async def test_missing_dependencies_leave_api_running(self):
        bot = BotProcess("http://localhost:3002")
        with patch("bot_process.shutil.which", return_value=None):
            await bot.start()
        self.assertIsNone(bot.task)

    async def test_child_uses_render_port_and_stops_cleanly(self):
        bot = BotProcess("http://127.0.0.1:3002")
        child = AsyncMock()
        child.returncode = None
        running = asyncio.Event()
        child.wait.side_effect = lambda: None

        async def wait():
            running.set()
            await asyncio.Event().wait()

        child.wait.side_effect = wait
        from unittest.mock import Mock
        child.terminate = Mock()
        with patch("bot_process.shutil.which", return_value="/usr/bin/node"), \
             patch("bot_process.Path.exists", return_value=True), \
             patch.dict("os.environ", {"PORT": "10000"}), \
             patch("bot_process.asyncio.create_subprocess_exec", return_value=child) as spawn:
            await bot.start()
            await asyncio.wait_for(running.wait(), timeout=1)
            self.assertEqual(spawn.call_args.kwargs["env"]["BACKEND_URL"], "http://127.0.0.1:10000")
            self.assertEqual(spawn.call_args.kwargs["env"]["BOT_PORT"], "3002")
            self.assertTrue(str(spawn.call_args.kwargs["cwd"]).endswith("whatsapp-bot"))
            child.wait.side_effect = None
            child.wait.return_value = 0
            await bot.stop()
            child.terminate.assert_called_once()
