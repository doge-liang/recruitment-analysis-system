#!/usr/bin/env python3
"""
测试 Element UI 分页点击方案

使用方法：
    python test_element_ui_pagination.py --page 3 --show-browser

参数：
    --page: 要爬取的页码（默认3）
    --show-browser: 显示浏览器窗口（建议开启以便观察）
"""

import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置 Django 环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")

# 在导入 Django 模型前先设置
import django

django.setup()

from crawler.job51_crawler import Job51Crawler


def test_element_ui_pagination(target_page: int = 3, show_browser: bool = True):
    """
    测试 Element UI 分页点击方案

    Args:
        target_page: 目标页码
        show_browser: 是否显示浏览器窗口
    """
    print("=" * 70)
    print("测试 Element UI 分页点击方案")
    print("=" * 70)
    print(f"\n目标页码: {target_page}")
    print(f"显示浏览器: {'是' if show_browser else '否'}")
    print()

    try:
        # 创建爬虫实例
        crawler = Job51Crawler(headless=not show_browser)

        print(f"[1/3] 开始爬取第 {target_page} 页...")

        # 使用点击翻页方法爬取
        jobs = crawler.crawl_page_with_click_pagination(
            keyword="大数据", target_page=target_page, headless=not show_browser
        )

        print(f"\n[2/3] 爬取完成！")
        print(f"  - 获取职位数: {len(jobs)}")

        if jobs:
            print(f"\n[3/3] 前3条职位信息:")
            for i, job in enumerate(jobs[:3], 1):
                print(f"\n  {i}. {job['title']}")
                print(f"     公司: {job['companyTitle']}")
                print(f"     薪资: {job['salary']}")
                print(f"     地点: {job['address']}")
        else:
            print("\n[3/3] 未获取到职位数据")
            print("  可能原因:")
            print("  1. 分页按钮未找到（网站结构变化）")
            print("  2. 翻页后数据未更新（AJAX加载失败）")
            print("  3. 遇到反爬验证")
            print("\n  建议:")
            print("  - 使用 --show-browser 参数显示浏览器观察")
            print("  - 检查日志中的分页选择器匹配情况")
            print("  - 运行 diagnose_pagination.py 进行详细诊断")

        print("\n" + "=" * 70)
        print("测试完成！")
        print("=" * 70)

        return len(jobs) > 0

    except Exception as e:
        print(f"\n[错误] 测试过程中出错: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试 Element UI 分页点击方案")
    parser.add_argument("--page", type=int, default=3, help="要爬取的页码（默认3）")
    parser.add_argument(
        "--show-browser",
        action="store_true",
        default=True,
        help="显示浏览器窗口（建议开启以便观察）",
    )
    parser.add_argument(
        "--headless", action="store_true", help="使用无头模式（不显示浏览器窗口）"
    )

    args = parser.parse_args()

    show_browser = not args.headless
    success = test_element_ui_pagination(
        target_page=args.page, show_browser=show_browser
    )

    sys.exit(0 if success else 1)
