"""
批处理队列管理
负责批任务的数据结构、状态流转与调度辅助
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import itertools


@dataclass
class BatchTask:
    """单个批处理任务"""
    task_id: int
    input_path: str
    mode: str  # sr / interp / combined
    params: Dict
    multiplier: int = 2
    status: str = "pending"   # pending/running/done/failed/cancelled
    progress: int = 0
    output_path: str = ""
    error: str = ""


class BatchQueueManager:
    """批处理队列管理器（串行调度）"""

    def __init__(self):
        self._tasks: List[BatchTask] = []
        self._id_counter = itertools.count(1)

    @property
    def tasks(self) -> List[BatchTask]:
        return self._tasks

    def add_task(self, input_path: str, mode: str, params: Dict, multiplier: int = 2) -> BatchTask:
        task = BatchTask(
            task_id=next(self._id_counter),
            input_path=input_path,
            mode=mode,
            params=dict(params),
            multiplier=multiplier,
        )
        self._tasks.append(task)
        return task

    def add_tasks(self, input_paths: List[str], mode: str, params: Dict, multiplier: int = 2) -> List[BatchTask]:
        added: List[BatchTask] = []
        existing = {t.input_path for t in self._tasks}
        for p in input_paths:
            if p in existing:
                continue
            task = self.add_task(p, mode, params, multiplier)
            added.append(task)
            existing.add(p)
        return added

    def clear(self):
        self._tasks.clear()

    def get_task(self, task_id: int) -> Optional[BatchTask]:
        for t in self._tasks:
            if t.task_id == task_id:
                return t
        return None

    def remove_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task or task.status == "running":
            return False
        self._tasks = [t for t in self._tasks if t.task_id != task_id]
        return True

    def update_task_config(
        self,
        task_id: int,
        mode: Optional[str] = None,
        params: Optional[Dict] = None,
        multiplier: Optional[int] = None,
    ) -> bool:
        """更新单个任务配置（仅允许等待中/失败/取消状态）"""
        task = self.get_task(task_id)
        if not task:
            return False
        if task.status == "running" or task.status == "done":
            return False

        if mode is not None:
            task.mode = mode
        if params is not None:
            task.params = dict(params)
        if multiplier is not None:
            task.multiplier = int(multiplier)
        return True

    def retry_failed(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task or task.status != "failed":
            return False
        task.status = "pending"
        task.progress = 0
        task.output_path = ""
        task.error = ""
        return True

    def has_pending(self) -> bool:
        return any(t.status == "pending" for t in self._tasks)

    def next_pending_task(self) -> Optional[BatchTask]:
        for t in self._tasks:
            if t.status == "pending":
                return t
        return None

    def mark_running(self, task_id: int):
        task = self.get_task(task_id)
        if task:
            task.status = "running"
            task.progress = 0

    def update_progress(self, task_id: int, current: int, total: int):
        task = self.get_task(task_id)
        if task and total > 0:
            task.progress = int(current * 100 / total)

    def mark_done(self, task_id: int, output_path: str):
        task = self.get_task(task_id)
        if task:
            task.status = "done"
            task.progress = 100
            task.output_path = output_path
            task.error = ""

    def mark_failed(self, task_id: int, error: str):
        task = self.get_task(task_id)
        if task:
            task.status = "failed"
            task.error = error

    def mark_cancelled(self, task_id: int):
        task = self.get_task(task_id)
        if task:
            task.status = "cancelled"

    def stats(self) -> Dict[str, int]:
        done = sum(1 for t in self._tasks if t.status == "done")
        failed = sum(1 for t in self._tasks if t.status == "failed")
        pending = sum(1 for t in self._tasks if t.status == "pending")
        running = sum(1 for t in self._tasks if t.status == "running")
        cancelled = sum(1 for t in self._tasks if t.status == "cancelled")
        total = len(self._tasks)
        return {
            "total": total,
            "done": done,
            "failed": failed,
            "pending": pending,
            "running": running,
            "cancelled": cancelled,
        }
