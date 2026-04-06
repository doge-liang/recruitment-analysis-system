#!/usr/bin/env python3
"""
测试多页爬取（Element UI 点击翻页方案）

使用方法：
    python test_multi_page.py --pages 5 --show-browser

参数：
    --pages: 要爬取的总页数（默认5）
    --keyword: 搜索关键词（默认"大数据"）
    --show-browser: 显示浏览器窗口
"""

import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置 Django 环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")

import django

django.setup()

from crawler.job51_crawler import Job51Crawler


def test_multi_page_crawler(
    pages: int = 5, keyword: str = "大数据", show_browser: bool = True
):
    """
    测试多页爬取

    Args:
        pages: 要爬取的总页数
        keyword: 搜索关键词
        show_browser: 是否显示浏览器窗口
    """
    print("=" * 70)
    print("测试多页爬取（Element UI 点击翻页方案）")
    print("=" * 70)
    print(f"\n配置:")
    print(f"  - 搜索关键词: {keyword}")
    print(f"  - 爬取页数: {pages}")
    print(f"  - 显示浏览器: {'是' if show_browser else '否'}")
    print()

    try:
        # 创建爬虫实例
        crawler = Job51Crawler(headless=not show_browser)

        print("[1/2] 开始多页爬取...\n")

        # 使用点击翻页方案爬取多页
        stats = crawler.run_crawler_with_click_pagination(
            keyword=keyword,
            pages=pages,
            resume=False,  # 测试时禁用断点续传
        )

        print("\n[2/2] 爬取完成！")
        print("\n统计信息:")
        print(f"  - 处理页面: {stats['pages_processed']} 页")
        print(f"  - 采集记录: {stats['records_collected']} 条")
        print(f"  - 保存记录: {stats['records_saved']} 条")
        print(f"  - 运行时间: {stats['elapsed_seconds'] / 60:.1f} 分钟")
        print(f"  - 错误次数: {stats['errors']} 次")

        # 验证结果
        print("\n验证:")
        if stats["pages_processed"] >= pages * 0.8:  # 允许20%的失败率
            print(f"  ✅ 成功处理 {stats['pages_processed']}/{pages} 页")
        else:
            print(
                f"  ⚠️  仅处理 {stats['pages_processed']}/{pages} 页，可能存在翻页问题"
            )

        if stats["records_collected"] > 0:
            avg_per_page = stats["records_collected"] / max(stats["pages_processed"], 1)
            print(f"  ✅ 平均每页 {avg_per_page:.1f} 条数据")

            if avg_per_page >= 15:  # 正常每页应该有15-20条
                print(f"  ✅ 数据量正常（每页{avg_per_page:.0f}条）")
            else:
                print(f"  ⚠️  数据量偏低（每页{avg_per_page:.0f}条），可能存在数据重复")
        else:
            print(f"  ❌ 未获取到任何数据")

        print("\n" + "=" * 70)

        return stats["records_collected"] > 0

    except Exception as e:
        print(f"\n[错误] 测试过程中出错: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试多页爬取")
    parser.add_argument("--pages", type=int, default=5, help="要爬取的总页数（默认5）")
    parser.add_argument(
        "--keyword", default="大数据", help='搜索关键词（默认"大数据"）'
    )
    parser.add_argument(
        "--show-browser", action="store_true", default=True, help="显示浏览器窗口"
    )
    parser.add_argument("--headless", action="store_true", help="使用无头模式")

    args = parser.parse_args()

    show_browser = not args.headless
    success = test_multi_page_crawler(
        pages=args.pages, keyword=args.keyword, show_browser=show_browser
    )

    sys.exit(0 if success else 1)
