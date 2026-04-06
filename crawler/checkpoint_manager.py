#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
爬虫检查点管理模块
提供断点续传功能，支持长时间运行的爬虫任务
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class CrawlCheckpoint:
    """爬虫检查点数据类"""

    keyword: str
    city: str
    current_page: int
    total_pages: int
    completed_pages: List[int]
    records_collected: int
    timestamp: float
    session_data: Dict
    error_count: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典（用于JSON序列化）"""
        return {
            "keyword": self.keyword,
            "city": self.city,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "completed_pages": self.completed_pages,
            "records_collected": self.records_collected,
            "timestamp": self.timestamp,
            "session_data": self.session_data,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CrawlCheckpoint":
        """从字典创建实例"""
        return cls(
            keyword=data.get("keyword", ""),
            city=data.get("city", ""),
            current_page=data.get("current_page", 0),
            total_pages=data.get("total_pages", 0),
            completed_pages=data.get("completed_pages", []),
            records_collected=data.get("records_collected", 0),
            timestamp=data.get("timestamp", time.time()),
            session_data=data.get("session_data", {}),
            error_count=data.get("error_count", 0),
            last_error=data.get("last_error"),
        )


class CheckpointManager:
    """
    检查点管理器

    功能:
    - 保存爬取进度到JSON文件
    - 从检查点恢复爬取
    - 跟踪已完成页面
    - 管理错误统计

    使用示例:
        manager = CheckpointManager("checkpoint.json")

        # 保存检查点
        manager.save_checkpoint(
            keyword="大数据",
            city="上海",
            current_page=50,
            total_pages=1000,
            records_collected=1000
        )

        # 恢复检查点
        checkpoint = manager.load_checkpoint()
        if checkpoint:
            remaining_pages = manager.get_remaining_pages(1, 1000)
    """

    def __init__(self, filepath: str = "crawler_checkpoint.json"):
        self.filepath = Path(filepath)
        self._checkpoint: Optional[CrawlCheckpoint] = None
        self._completed_pages: Set[int] = set()

    def save_checkpoint(
        self,
        keyword: str,
        city: str,
        current_page: int,
        total_pages: int,
        records_collected: int = 0,
        session_data: Optional[Dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        保存检查点

        Args:
            keyword: 搜索关键词
            city: 城市
            current_page: 当前页码
            total_pages: 总页数
            records_collected: 已收集记录数
            session_data: 会话数据（如cookies等）
            error: 错误信息（如果有）
        """
        # 更新已完成页面集合
        if current_page > 0:
            self._completed_pages.add(current_page)

        # 创建检查点
        checkpoint = CrawlCheckpoint(
            keyword=keyword,
            city=city,
            current_page=current_page,
            total_pages=total_pages,
            completed_pages=sorted(list(self._completed_pages)),
            records_collected=records_collected,
            timestamp=time.time(),
            session_data=session_data or {},
            error_count=self._checkpoint.error_count + 1
            if error and self._checkpoint
            else (1 if error else 0),
            last_error=error,
        )

        self._checkpoint = checkpoint

        # 写入文件
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CheckpointManager] 保存检查点失败: {e}")

    def load_checkpoint(self) -> Optional[CrawlCheckpoint]:
        """
        从文件加载检查点

        Returns:
            CrawlCheckpoint对象或None（如果文件不存在或解析失败）
        """
        if not self.filepath.exists():
            return None

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            checkpoint = CrawlCheckpoint.from_dict(data)
            self._checkpoint = checkpoint
            self._completed_pages = set(checkpoint.completed_pages)

            return checkpoint
        except Exception as e:
            print(f"[CheckpointManager] 加载检查点失败: {e}")
            return None

    def get_remaining_pages(self, start_page: int, end_page: int) -> List[int]:
        """
        获取剩余需要爬取的页面列表

        Args:
            start_page: 起始页码
            end_page: 结束页码

        Returns:
            未完成的页面列表
        """
        all_pages = set(range(start_page, end_page + 1))
        remaining = sorted(list(all_pages - self._completed_pages))
        return remaining

    def is_page_completed(self, page: int) -> bool:
        """检查页面是否已完成"""
        return page in self._completed_pages

    def get_progress_percentage(self) -> float:
        """获取进度百分比"""
        if not self._checkpoint or self._checkpoint.total_pages == 0:
            return 0.0
        return (len(self._completed_pages) / self._checkpoint.total_pages) * 100

    def clear_checkpoint(self) -> None:
        """清除检查点（完成后调用）"""
        if self.filepath.exists():
            try:
                os.remove(self.filepath)
            except Exception as e:
                print(f"[CheckpointManager] 清除检查点失败: {e}")

        self._checkpoint = None
        self._completed_pages = set()

    def get_checkpoint_info(self) -> Optional[Dict]:
        """获取检查点信息摘要"""
        if not self._checkpoint:
            return None

        return {
            "keyword": self._checkpoint.keyword,
            "city": self._checkpoint.city,
            "current_page": self._checkpoint.current_page,
            "total_pages": self._checkpoint.total_pages,
            "completed_count": len(self._completed_pages),
            "remaining_count": self._checkpoint.total_pages
            - len(self._completed_pages),
            "progress": f"{self.get_progress_percentage():.1f}%",
            "records_collected": self._checkpoint.records_collected,
            "last_updated": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(self._checkpoint.timestamp)
            ),
            "error_count": self._checkpoint.error_count,
        }


class BatchStateManager:
    """
    批次状态管理器

    用于管理大批量爬取任务的批次状态
    将大任务分割为多个小批次，每批完成后保存状态
    """

    def __init__(self, filepath: str = "batch_state.json"):
        self.filepath = Path(filepath)

    def save_batch_state(
        self,
        current_batch: int,
        completed_batches: List[int],
        total_pages: int,
        batch_size: int,
    ) -> None:
        """保存批次状态"""
        state = {
            "current_batch": current_batch,
            "completed_batches": completed_batches,
            "total_pages": total_pages,
            "batch_size": batch_size,
            "timestamp": time.time(),
        }

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BatchStateManager] 保存批次状态失败: {e}")

    def load_batch_state(self) -> Optional[Dict]:
        """加载批次状态"""
        if not self.filepath.exists():
            return None

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[BatchStateManager] 加载批次状态失败: {e}")
            return None

    def clear_batch_state(self) -> None:
        """清除批次状态"""
        if self.filepath.exists():
            try:
                os.remove(self.filepath)
            except Exception as e:
                print(f"[BatchStateManager] 清除批次状态失败: {e}")


class BatchCalculator:
    """
    批次计算器

    将大量页面分割为可管理的批次
    """

    def __init__(self, total_pages: int, batch_size: int = 50):
        """
        Args:
            total_pages: 总页数
            batch_size: 每批页数（默认50页）
        """
        self.total_pages = total_pages
        self.batch_size = batch_size
        self.total_batches = (total_pages + batch_size - 1) // batch_size

    def get_batch_range(self, batch_number: int) -> tuple:
        """
        获取指定批次的页面范围

        Args:
            batch_number: 批次号（从1开始）

        Returns:
            (start_page, end_page) 元组
        """
        start = (batch_number - 1) * self.batch_size + 1
        end = min(batch_number * self.batch_size, self.total_pages)
        return start, end

    def get_progress(self, current_batch: int) -> float:
        """获取进度百分比"""
        return (current_batch / self.total_batches) * 100

    def get_all_batches(self) -> List[tuple]:
        """获取所有批次的页面范围列表"""
        return [self.get_batch_range(i) for i in range(1, self.total_batches + 1)]


# 便捷函数
def create_checkpoint_manager(
    filepath: str = "crawler_checkpoint.json",
) -> CheckpointManager:
    """创建检查点管理器"""
    return CheckpointManager(filepath)


def create_batch_calculator(total_pages: int, batch_size: int = 50) -> BatchCalculator:
    """创建批次计算器"""
    return BatchCalculator(total_pages, batch_size)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("CheckpointManager 测试")
    print("=" * 60)

    # 测试检查点管理
    manager = CheckpointManager("test_checkpoint.json")

    # 保存检查点
    manager.save_checkpoint(
        keyword="大数据",
        city="上海",
        current_page=50,
        total_pages=1000,
        records_collected=1000,
    )
    print("检查点已保存")

    # 加载检查点
    checkpoint = manager.load_checkpoint()
    if checkpoint:
        print(
            f"检查点加载成功: 第{checkpoint.current_page}页, 共{checkpoint.total_pages}页"
        )

    # 获取进度
    info = manager.get_checkpoint_info()
    if info:
        print(f"进度: {info['progress']}")
        print(f"剩余页面数: {info['remaining_count']}")

    # 测试批次计算器
    print("\n" + "=" * 60)
    print("BatchCalculator 测试")
    print("=" * 60)

    calculator = BatchCalculator(total_pages=1000, batch_size=50)
    print(f"总批次数: {calculator.total_batches}")

    # 获取第3批范围
    start, end = calculator.get_batch_range(3)
    print(f"第3批页面范围: {start}-{end}")

    # 获取进度
    progress = calculator.get_progress(5)
    print(f"完成5批后的进度: {progress:.1f}%")

    # 清理
    manager.clear_checkpoint()
    print("\n测试检查点已清理")
