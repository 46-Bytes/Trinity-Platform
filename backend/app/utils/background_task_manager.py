"""
Background task manager for tracking and gracefully terminating background tasks.
Handles shutdown signals to ensure tasks are cancelled when the application is redeployed.
"""
import asyncio
import logging
from typing import Set, Optional
from uuid import UUID
import signal
import sys

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """
    Manages background tasks and handles graceful shutdown.
    Tracks running tasks and cancels them when the application shuts down.
    """
    _instance: Optional['BackgroundTaskManager'] = None
    _shutdown_flag: bool = False
    _running_tasks: Set[asyncio.Task] = set()
    _diagnostic_tasks: dict[UUID, asyncio.Task] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_signal_handlers()
        return cls._instance
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        # Note: We don't intercept signals here to avoid blocking uvicorn's shutdown
        # Instead, we rely on FastAPI's shutdown event handler
        # Signal handlers can interfere with uvicorn's reload mechanism
        pass
    
    def is_shutting_down(self) -> bool:
        """Check if the application is shutting down."""
        return self._shutdown_flag
    
    def initiate_shutdown(self):
        """Mark the application as shutting down."""
        if not self._shutdown_flag:
            logger.info("🛑 Shutdown initiated - cancelling all background tasks...")
            self._shutdown_flag = True
            
            # Cancel all running tasks
            for task in list(self._running_tasks):
                if not task.done():
                    logger.info(f"🛑 Cancelling background task: {task.get_name()}")
                    task.cancel()
            
            # Cancel diagnostic tasks
            for diagnostic_id, task in list(self._diagnostic_tasks.items()):
                if not task.done():
                    logger.info(f"🛑 Cancelling diagnostic processing task for diagnostic {diagnostic_id}")
                    task.cancel()
    
    def register_task(self, task: asyncio.Task, diagnostic_id: Optional[UUID] = None):
        """Register a background task for tracking."""
        self._running_tasks.add(task)
        
        if diagnostic_id:
            self._diagnostic_tasks[diagnostic_id] = task
        
        # Remove task when it completes
        task.add_done_callback(lambda t: self._running_tasks.discard(t))
        if diagnostic_id:
            task.add_done_callback(lambda t: self._diagnostic_tasks.pop(diagnostic_id, None))
        
        logger.info(f"✅ Registered background task: {task.get_name()}")
    
    def get_diagnostic_task(self, diagnostic_id: UUID) -> Optional[asyncio.Task]:
        """Get the task for a specific diagnostic."""
        return self._diagnostic_tasks.get(diagnostic_id)
    
    async def wait_for_shutdown(self, timeout: float = 10.0):
        """Wait for all tasks to complete or timeout during shutdown."""
        if not self.is_shutting_down():
            return
        
        logger.info(f"⏳ Waiting for {len(self._running_tasks)} background task(s) to complete...")
        
        # Wait for all tasks with a timeout
        if self._running_tasks:
            # Filter out already completed tasks
            active_tasks = [t for t in self._running_tasks if not t.done()]
            
            if active_tasks:
                logger.info(f"⏳ Waiting for {len(active_tasks)} active task(s)...")
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*active_tasks, return_exceptions=True),
                        timeout=timeout
                    )
                    logger.info("✅ All background tasks completed")
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Some background tasks did not complete within {timeout}s timeout - forcing shutdown")
                    # Force cancel remaining tasks
                    for task in active_tasks:
                        if not task.done():
                            task.cancel()
            else:
                logger.info("✅ All background tasks already completed")
        else:
            logger.info("✅ No background tasks to wait for")


# Global instance
background_task_manager = BackgroundTaskManager()

