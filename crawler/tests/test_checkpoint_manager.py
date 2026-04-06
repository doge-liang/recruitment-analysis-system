#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CheckpointManager 单元测试
测试断点续传功能的正确性
"""

import os
import json
import time
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.checkpoint_manager import (
    CheckpointManager,
    BatchCalculator,
    BatchStateManager,
    CrawlCheckpoint,
)


class TestCheckpointManager(unittest.TestCase):
    """测试CheckpointManager类"""

    def setUp(self):
        """每个测试前创建临时文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_file = os.path.join(self.temp_dir, "test_checkpoint.json")
        self.manager = CheckpointManager(self.checkpoint_file)

    def tearDown(self):
        """每个测试后清理"""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
        os.rmdir(self.temp_dir)

    def test_save_and_load_checkpoint(self):
        """测试保存和加载检查点"""
        # 保存检查点
        self.manager.save_checkpoint(
            keyword="大数据",
            city="上海",
            current_page=50,
            total_pages=100,
            records_collected=1000,
        )

        # 加载检查点
        checkpoint = self.manager.load_checkpoint()

        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.keyword, "大数据")
        self.assertEqual(checkpoint.city, "上海")
        self.assertEqual(checkpoint.current_page, 50)
        self.assertEqual(checkpoint.total_pages, 100)
        self.assertEqual(checkpoint.records_collected, 1000)

    def test_load_nonexistent_checkpoint(self):
        """测试加载不存在的检查点"""
        checkpoint = self.manager.load_checkpoint()
        self.assertIsNone(checkpoint)

    def test_get_remaining_pages(self):
        """测试获取剩余页面"""
        # 模拟已完成页面 1, 2, 3, 5
        self.manager._completed_pages = {1, 2, 3, 5}

        remaining = self.manager.get_remaining_pages(1, 10)

        # 应该返回 [4, 6, 7, 8, 9, 10]
        expected = [4, 6, 7, 8, 9, 10]
        self.assertEqual(remaining, expected)

    def test_is_page_completed(self):
        """测试检查页面是否完成"""
        self.manager._completed_pages = {1, 2, 3}

        self.assertTrue(self.manager.is_page_completed(1))
        self.assertTrue(self.manager.is_page_completed(2))
        self.assertFalse(self.manager.is_page_completed(4))

    def test_get_progress_percentage(self):
        """测试获取进度百分比"""
        # 保存一个检查点
        self.manager.save_checkpoint(
            keyword="测试",
            city="",
            current_page=50,
            total_pages=100,
            records_collected=500,
        )

        # 模拟已完成50页
        self.manager._completed_pages = set(range(1, 51))

        progress = self.manager.get_progress_percentage()
        self.assertEqual(progress, 50.0)

    def test_clear_checkpoint(self):
        """测试清除检查点"""
        # 先保存一个检查点
        self.manager.save_checkpoint(
            keyword="测试",
            city="",
            current_page=10,
            total_pages=100,
            records_collected=100,
        )

        # 确认文件存在
        self.assertTrue(os.path.exists(self.checkpoint_file))

        # 清除检查点
        self.manager.clear_checkpoint()

        # 确认文件已删除
        self.assertFalse(os.path.exists(self.checkpoint_file))
        self.assertIsNone(self.manager._checkpoint)
        self.assertEqual(len(self.manager._completed_pages), 0)

    def test_get_checkpoint_info(self):
        """测试获取检查点信息摘要"""
        self.manager.save_checkpoint(
            keyword="大数据",
            city="北京",
            current_page=75,
            total_pages=100,
            records_collected=1500,
        )

        # 模拟完成75页
        self.manager._completed_pages = set(range(1, 76))

        info = self.manager.get_checkpoint_info()

        self.assertIsNotNone(info)
        self.assertEqual(info["keyword"], "大数据")
        self.assertEqual(info["city"], "北京")
        self.assertEqual(info["completed_count"], 75)
        self.assertEqual(info["remaining_count"], 25)
        self.assertEqual(info["progress"], "75.0%")
        self.assertEqual(info["records_collected"], 1500)


class TestBatchCalculator(unittest.TestCase):
    """测试BatchCalculator类"""

    def test_calculate_total_batches(self):
        """测试计算总批次数"""
        calc = BatchCalculator(total_pages=100, batch_size=20)
        self.assertEqual(calc.total_batches, 5)

        calc2 = BatchCalculator(total_pages=105, batch_size=20)
        self.assertEqual(calc2.total_batches, 6)  # 向上取整

    def test_get_batch_range(self):
        """测试获取批次页面范围"""
        calc = BatchCalculator(total_pages=100, batch_size=20)

        # 第1批: 1-20
        start, end = calc.get_batch_range(1)
        self.assertEqual(start, 1)
        self.assertEqual(end, 20)

        # 第3批: 41-60
        start, end = calc.get_batch_range(3)
        self.assertEqual(start, 41)
        self.assertEqual(end, 60)

        # 最后一批: 81-100
        start, end = calc.get_batch_range(5)
        self.assertEqual(start, 81)
        self.assertEqual(end, 100)

    def test_get_progress(self):
        """测试获取进度百分比"""
        calc = BatchCalculator(total_pages=100, batch_size=20)

        progress = calc.get_progress(3)
        self.assertEqual(progress, 60.0)  # 3/5 = 60%

    def test_get_all_batches(self):
        """测试获取所有批次"""
        calc = BatchCalculator(total_pages=50, batch_size=20)
        batches = calc.get_all_batches()

        # 应该分为3批: (1,20), (21,40), (41,50)
        self.assertEqual(len(batches), 3)
        self.assertEqual(batches[0], (1, 20))
        self.assertEqual(batches[1], (21, 40))
        self.assertEqual(batches[2], (41, 50))


class TestBatchStateManager(unittest.TestCase):
    """测试BatchStateManager类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, "test_batch_state.json")
        self.manager = BatchStateManager(self.state_file)

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        os.rmdir(self.temp_dir)

    def test_save_and_load_batch_state(self):
        """测试保存和加载批次状态"""
        self.manager.save_batch_state(
            current_batch=3,
            completed_batches=[1, 2],
            total_pages=100,
            batch_size=20,
        )

        state = self.manager.load_batch_state()

        self.assertIsNotNone(state)
        self.assertEqual(state["current_batch"], 3)
        self.assertEqual(state["completed_batches"], [1, 2])
        self.assertEqual(state["total_pages"], 100)
        self.assertEqual(state["batch_size"], 20)

    def test_load_nonexistent_state(self):
        """测试加载不存在的状态"""
        state = self.manager.load_batch_state()
        self.assertIsNone(state)

    def test_clear_batch_state(self):
        """测试清除批次状态"""
        self.manager.save_batch_state(
            current_batch=1,
            completed_batches=[],
            total_pages=50,
            batch_size=10,
        )

        self.assertTrue(os.path.exists(self.state_file))

        self.manager.clear_batch_state()

        self.assertFalse(os.path.exists(self.state_file))


class TestCrawlCheckpoint(unittest.TestCase):
    """测试CrawlCheckpoint数据类"""

    def test_to_dict(self):
        """测试转换为字典"""
        checkpoint = CrawlCheckpoint(
            keyword="测试",
            city="上海",
            current_page=10,
            total_pages=100,
            completed_pages=[1, 2, 3, 4, 5],
            records_collected=100,
            timestamp=1234567890.0,
            session_data={"cookie": "test"},
        )

        data = checkpoint.to_dict()

        self.assertEqual(data["keyword"], "测试")
        self.assertEqual(data["city"], "上海")
        self.assertEqual(data["current_page"], 10)
        self.assertEqual(data["completed_pages"], [1, 2, 3, 4, 5])

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "keyword": "大数据",
            "city": "北京",
            "current_page": 25,
            "total_pages": 50,
            "completed_pages": list(range(1, 26)),
            "records_collected": 500,
            "timestamp": time.time(),
            "session_data": {},
            "error_count": 0,
            "last_error": None,
        }

        checkpoint = CrawlCheckpoint.from_dict(data)

        self.assertEqual(checkpoint.keyword, "大数据")
        self.assertEqual(checkpoint.city, "北京")
        self.assertEqual(checkpoint.current_page, 25)
        self.assertEqual(len(checkpoint.completed_pages), 25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
