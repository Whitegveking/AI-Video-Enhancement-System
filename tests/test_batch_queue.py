"""批处理队列基础回归测试（脚本版）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.batch_queue import BatchQueueManager


def main():
    q = BatchQueueManager()

    params = {
        "model_key": "RealESRGAN_x4",
        "scale": 4,
        "denoise": 0.0,
        "use_tiling": True,
        "tile_size": 512,
        "tile_pad": 32,
        "half": True,
    }

    tasks = q.add_tasks([
        "a.mp4",
        "b.mp4",
        "a.mp4",  # 重复，应被去重
    ], mode="sr", params=params, multiplier=2)

    assert len(tasks) == 2, "重复文件去重失败"
    assert q.stats()["total"] == 2, "队列总数错误"

    t1 = q.next_pending_task()
    assert t1 is not None and t1.input_path == "a.mp4", "next_pending_task 顺序错误"

    q.mark_running(t1.task_id)
    q.update_progress(t1.task_id, 30, 100)
    assert q.get_task(t1.task_id).status == "running", "任务状态未进入 running"
    assert q.get_task(t1.task_id).progress == 30, "任务进度更新错误"

    q.mark_done(t1.task_id, "a_out.mp4")
    assert q.get_task(t1.task_id).status == "done", "任务完成状态错误"
    assert q.get_task(t1.task_id).output_path == "a_out.mp4", "任务输出路径未记录"

    # 已完成任务不允许再修改配置
    updated_done = q.update_task_config(
        t1.task_id,
        mode="interp",
        params={"model_key": "GFPGAN_v1.4"},
        multiplier=4,
    )
    assert not updated_done, "已完成任务不应允许修改配置"

    t2 = q.next_pending_task()
    assert t2 is not None and t2.input_path == "b.mp4", "下一任务选择错误"

    # 待处理任务允许独立配置
    updated = q.update_task_config(
        t2.task_id,
        mode="combined",
        params={**params, "denoise": 0.3, "model_key": "GFPGAN_v1.4"},
        multiplier=4,
    )
    assert updated, "待处理任务应允许独立配置"
    t2_after = q.get_task(t2.task_id)
    assert t2_after.mode == "combined", "任务模式更新失败"
    assert t2_after.multiplier == 4, "补帧倍率更新失败"
    assert abs(t2_after.params["denoise"] - 0.3) < 1e-8, "参数更新失败"

    q.mark_failed(t2.task_id, "mock error")
    assert q.get_task(t2.task_id).status == "failed", "失败状态记录错误"

    ok = q.retry_failed(t2.task_id)
    assert ok, "重试失败任务应成功"
    assert q.get_task(t2.task_id).status == "pending", "重试后状态应为 pending"

    q.remove_task(t2.task_id)
    assert q.stats()["total"] == 1, "移除任务失败"

    print("batch_queue tests passed")


if __name__ == "__main__":
    main()
