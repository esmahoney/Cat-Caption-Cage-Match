"""
Background tasks for Cat Caption Cage Match.

These tasks run periodically to maintain system health.
"""
import asyncio
from typing import Optional

from .dependencies import get_storage
from .config import get_settings


class CleanupTask:
    """
    Periodic task to clean up expired sessions.
    
    Runs every hour by default.
    """
    
    def __init__(self, interval_seconds: int = 3600):
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def _run_cleanup(self) -> None:
        """Run the cleanup loop."""
        storage = get_storage()
        
        while self._running:
            try:
                count = await storage.cleanup_expired_sessions()
                if count > 0:
                    print(f"Cleaned up {count} expired session(s)")
            except Exception as e:
                print(f"Error during session cleanup: {e}")
            
            await asyncio.sleep(self.interval_seconds)
    
    def start(self) -> None:
        """Start the cleanup task."""
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._run_cleanup())
            print(f"Session cleanup task started (interval: {self.interval_seconds}s)")
    
    def stop(self) -> None:
        """Stop the cleanup task."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            print("Session cleanup task stopped")


# Global cleanup task instance
cleanup_task = CleanupTask()

