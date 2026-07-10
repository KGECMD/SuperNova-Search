"""
Scheduler for Atomic Search.

Provides background task scheduling.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional


@dataclass
class ScheduledTask:
    """Scheduled task definition."""
    name: str
    func: Callable
    interval: float  # seconds
    last_run: float
    next_run: float
    enabled: bool = True
    args: tuple = ()
    kwargs: dict = None


class Scheduler:
    """Background task scheduler."""

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread = None

    def add_task(
        self,
        name: str,
        func: Callable,
        interval: float,
        args: tuple = None,
        kwargs: dict = None,
        run_now: bool = False
    ):
        """Add a scheduled task."""
        with self._lock:
            now = time.time()
            self._tasks[name] = ScheduledTask(
                name=name,
                func=func,
                interval=interval,
                last_run=now if not run_now else 0,
                next_run=now + interval,
                args=args or (),
                kwargs=kwargs or {}
            )

    def remove_task(self, name: str) -> bool:
        """Remove a task."""
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]
                return True
            return False

    def enable_task(self, name: str) -> bool:
        """Enable a task."""
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = True
                return True
            return False

    def disable_task(self, name: str) -> bool:
        """Disable a task."""
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = False
                return True
            return False

    def run_task(self, name: str) -> bool:
        """Run a task immediately."""
        with self._lock:
            if name not in self._tasks:
                return False

            task = self._tasks[name]
            try:
                task.func(*task.args, **task.kwargs)
                task.last_run = time.time()
                task.next_run = time.time() + task.interval
                return True
            except Exception:
                return False

    def start(self):
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            now = time.time()

            with self._lock:
                for name, task in list(self._tasks.items()):
                    if task.enabled and now >= task.next_run:
                        # Run task
                        try:
                            task.func(*task.args, **task.kwargs)
                        except Exception:
                            pass

                        task.last_run = now
                        task.next_run = now + task.interval

            # Sleep for a short interval
            time.sleep(1)

    def get_task_info(self, name: str) -> Optional[Dict]:
        """Get task information."""
        with self._lock:
            if name not in self._tasks:
                return None

            task = self._tasks[name]
            return {
                "name": task.name,
                "interval": task.interval,
                "last_run": datetime.fromtimestamp(task.last_run).isoformat(),
                "next_run": datetime.fromtimestamp(task.next_run).isoformat(),
                "enabled": task.enabled,
                "overdue": time.time() > task.next_run if task.enabled else False,
            }

    def list_tasks(self) -> List[Dict]:
        """List all tasks."""
        return [
            self.get_task_info(name)
            for name in self._tasks
        ]


# Common task decorators
def every(seconds: float):
    """Decorator to schedule function to run every N seconds."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            scheduler.add_task(
                name=func.__name__,
                func=lambda: func(*args, **kwargs),
                interval=seconds
            )
        return wrapper
    return decorator


def on_startup(func: Callable) -> Callable:
    """Decorator to run function on startup."""
    def wrapper(*args, **kwargs):
        scheduler.add_task(
            name=f"startup_{func.__name__}",
            func=lambda: func(*args, **kwargs),
            interval=86400,  # Run once per day (re-runs but that's ok)
            run_now=True
        )
    return wrapper


# Global scheduler
scheduler = Scheduler()
