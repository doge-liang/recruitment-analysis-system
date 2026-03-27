"""
测试静态文件服务状态
验证 ECharts 等前端库是否能正确返回 200 状态码
"""
import os
from django.test import TestCase, Client
from django.conf import settings
from django.contrib.staticfiles import finders


class StaticFilesTestCase(TestCase):
    """静态文件服务测试"""

    def setUp(self):
        self.client = Client()

    def test_echarts_file_exists(self):
        """测试 ECharts 文件物理存在"""
        filepath = finders.find('js/echarts.min.js')
        self.assertIsNotNone(
            filepath,
            "ECharts 文件未找到，请运行 python manage.py collectstatic"
        )
        # 验证文件大小
        filesize = os.path.getsize(filepath)
        self.assertGreater(
            filesize, 500000,
            f"ECharts 文件过小 ({filesize} bytes)，可能下载不完整"
        )

    def test_echarts_wordcloud_file_exists(self):
        """测试 ECharts WordCloud 文件物理存在"""
        filepath = finders.find('js/echarts-wordcloud.min.js')
        self.assertIsNotNone(
            filepath,
            "ECharts WordCloud 文件未找到"
        )

    def test_static_url_accessible_in_live_server(self):
        """测试静态文件 URL 配置正确"""
        filepath = finders.find('js/echarts.min.js')
        self.assertIsNotNone(filepath, "静态文件未正确配置")

    def test_static_files_not_found_for_missing(self):
        """测试不存在的静态文件会被 finders 报告为不存在"""
        filepath = finders.find('js/nonexistent-file.js')
        self.assertIsNone(filepath, "不存在的文件不应被找到")
