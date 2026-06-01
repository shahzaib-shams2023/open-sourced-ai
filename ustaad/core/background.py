import threading
import uuid
import time
from dataclasses import dataclass
from typing import Dict, Any, Callable, List

@dataclass
class BackgroundTask:
    id: str
    name: str
    status: str  # "running", "completed", "failed"
    result: Any = None
    error: str = None
    start_time: float = 0.0
    end_time: float = 0.0

class BackgroundManager:
    def __init__(self):
        self.tasks: Dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()

    def submit(self, name: str, func: Callable, *args, **kwargs) -> str:
        """Submit a new background task."""
        task_id = str(uuid.uuid4())[:8]
        task = BackgroundTask(id=task_id, name=name, status="running", start_time=time.time())
        
        with self._lock:
            self.tasks[task_id] = task

        def _worker():
            try:
                res = func(*args, **kwargs)
                with self._lock:
                    task.result = res
                    task.status = "completed"
            except Exception as e:
                with self._lock:
                    task.error = str(e)
                    task.status = "failed"
            finally:
                with self._lock:
                    task.end_time = time.time()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return task_id

    def get_task(self, task_id: str) -> BackgroundTask:
        """Get a specific task by ID."""
        with self._lock:
            return self.tasks.get(task_id)

    def list_tasks(self) -> List[BackgroundTask]:
        """List all tasks."""
        with self._lock:
            return list(self.tasks.values())

_bg_manager = BackgroundManager()

def get_background_manager() -> BackgroundManager:
    """Get the global background task manager."""
    return _bg_manager
