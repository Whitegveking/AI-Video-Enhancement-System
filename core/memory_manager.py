"""
流式内存管理
配合 Python 生成器实现"读取一帧、处理一帧、释放一帧"的管道模式
防止长时间运行导致内存泄漏
"""
import gc
import torch


class MemoryManager:
    """
    内存与显存管理器
    在视频处理循环中定期清理缓存
    """

    def __init__(self, gc_interval: int = 50):
        """
        Args:
            gc_interval: 每处理多少帧执行一次垃圾回收
        """
        self.gc_interval = gc_interval
        self._frame_counter = 0

    def step(self):
        """每处理一帧调用一次，达到间隔时触发清理"""
        self._frame_counter += 1
        if self._frame_counter % self.gc_interval == 0:
            self.force_cleanup()

    def force_cleanup(self):
        """强制执行垃圾回收和显存清理"""
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def reset(self):
        """重置计数器"""
        self._frame_counter = 0

    @staticmethod
    def get_gpu_memory_info() -> dict:
        """获取当前 GPU 显存使用情况"""
        if not torch.cuda.is_available():
            # 向后兼容：即使无 GPU 也返回完整键，避免调用方 KeyError
            return {
                "available": False,
                "device_name": "CPU/No CUDA",
                "total_mb": 0.0,
                "allocated_mb": 0.0,
                "cached_mb": 0.0,
                "free_mb": 0.0,
            }

        return {
            "available": True,
            "device_name": torch.cuda.get_device_name(0),
            "total_mb": torch.cuda.get_device_properties(0).total_memory / (1024 ** 2),
            "allocated_mb": torch.cuda.memory_allocated(0) / (1024 ** 2),
            "cached_mb": torch.cuda.memory_reserved(0) / (1024 ** 2),
            "free_mb": (
                torch.cuda.get_device_properties(0).total_memory
                - torch.cuda.memory_allocated(0)
            ) / (1024 ** 2),
        }
