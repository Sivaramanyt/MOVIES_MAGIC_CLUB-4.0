import asyncio
from dataclasses import dataclass


@dataclass
class IndexProgress:
    running: bool = False
    paused: bool = False
    stop_requested: bool = False
    channel_id: int | None = None
    limit: int = 0
    scanned: int = 0
    files: int = 0
    created: int = 0
    existing: int = 0
    matched: int = 0
    unmatched: int = 0
    failed: int = 0
    last_error: str | None = None


class IndexController:
    def __init__(self) -> None:
        self.progress = IndexProgress()
        self._lock = asyncio.Lock()
        self._resume = asyncio.Event()
        self._resume.set()

    async def start(self, channel_id: int, limit: int) -> bool:
        async with self._lock:
            if self.progress.running:
                return False
            self.progress = IndexProgress(running=True, channel_id=channel_id, limit=limit)
            self._resume.set()
            return True

    async def pause(self) -> bool:
        async with self._lock:
            if not self.progress.running or self.progress.paused:
                return False
            self.progress.paused = True
            self._resume.clear()
            return True

    async def resume(self) -> bool:
        async with self._lock:
            if not self.progress.running or not self.progress.paused:
                return False
            self.progress.paused = False
            self._resume.set()
            return True

    async def stop(self) -> bool:
        async with self._lock:
            if not self.progress.running:
                return False
            self.progress.stop_requested = True
            self.progress.paused = False
            self._resume.set()
            return True

    async def wait_if_paused(self) -> bool:
        await self._resume.wait()
        return self.progress.stop_requested

    async def finish(self, error: str | None = None) -> None:
        async with self._lock:
            self.progress.running = False
            self.progress.paused = False
            self.progress.last_error = error
            self._resume.set()

    def snapshot(self) -> IndexProgress:
        return IndexProgress(**self.progress.__dict__)


index_controller = IndexController()
