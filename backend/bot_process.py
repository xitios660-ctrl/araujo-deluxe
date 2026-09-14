"""Manage only the local WhatsApp child process, with logs on stdout/stderr."""
import asyncio
import logging
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BotProcess:
    def __init__(self, bot_url):
        self.url = urlparse(bot_url)
        self.process = None
        self.task = None

    async def start(self):
        # A separately hosted bot must never spawn a competing local session.
        if self.url.hostname not in ("localhost", "127.0.0.1", "::1"):
            return
        node = shutil.which("node")
        directory = Path(__file__).resolve().parent.parent / "whatsapp-bot"
        if not node or not (directory / "node_modules" / "baileys").exists():
            logger.error("Bot indisponível: execute backend/build.sh com Node.js e a pasta whatsapp-bot presentes")
            return
        self.task = asyncio.create_task(self._supervise(node, directory))

    async def _supervise(self, node, directory):
        env = {
            **os.environ,
            "BOT_PORT": str(self.url.port or 3002),
            "BOT_HOST": self.url.hostname,
            "BACKEND_URL": f"http://127.0.0.1:{os.environ.get('PORT', '8001')}",
        }
        while True:
            try:
                self.process = await asyncio.create_subprocess_exec(
                    node, "index.js", cwd=directory, env=env,
                )
                code = await self.process.wait()
                logger.error("Bot encerrou com código %s; nova tentativa em 10 segundos", code)
            except OSError:
                logger.exception("Falha ao iniciar processo do bot")
            await asyncio.sleep(10)

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except ProcessLookupError:
                pass
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
