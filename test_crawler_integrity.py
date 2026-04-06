#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
前程无忧爬虫测试脚本
测试数据完整性
"""

import os
import sys

# Django setup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
import django

django.setup()

from crawler.job51_crawler import Job51Crawler, save_to_database
from myApp.models import JobInfo


def test_crawler():
    """测试爬虫并验证数据完整性"""
    print("=" * 70)
    print("前程无忧爬虫数据完整性测试")
    print("=" * 70)

    # 记录测试前的数据量
    before_count = JobInfo.objects.count()
    print(f"\n测试前数据库记录数: {before_count}")

    # 运行爬虫（只爬1页）
    print("\n" + "=" * 70)
    print("开始爬取数据...")
    print("=" * 70)

    crawler = Job51Crawler()
    jobs = crawler.crawl_job_list(keyword="数据分析", page=1)

    print(f"\n获取到 {len(jobs)} 条职位数据")

    if not jobs:
        print("错误: 未获取到任何数据")
        return False

    # 检查数据完整性
    print("\n" + "=" * 70)
    print("数据完整性检查")
    print("=" * 70)

    required_fields = [
        "title",
        "salary",
        "companyTitle",
        "address",
        "educational",
        "workExperience",
        "type",
    ]

    completeness_report = {}
    for field in required_fields:
        filled_count = sum(1 for job in jobs if job.get(field))
        completeness_report[field] = {
            "filled": filled_count,
            "total": len(jobs),
            "percentage": (filled_count / len(jobs)) * 100,
        }
        print(
            f"  {field:20s}: {filled_count:2d}/{len(jobs)} ({(filled_count / len(jobs)) * 100:5.1f}%)"
        )

    # 显示样本数据
    print("\n" + "=" * 70)
    print("样本数据（前3条）")
    print("=" * 70)
    for i, job in enumerate(jobs[:3], 1):
        print(f"\n  [{i}] {job['title'][:30]}")
        print(f"      公司: {job['companyTitle'][:25]}")
        print(f"      薪资: {job['salary']}")
        print(f"      地点: {job['address']}")
        print(f"      学历: {job['educational']} | 经验: {job['workExperience']}")

    # 保存到数据库
    print("\n" + "=" * 70)
    print("保存到数据库...")
    print("=" * 70)

    saved, skipped = save_to_database(jobs)
    print(f"  成功保存: {saved} 条")
    print(f"  跳过重复: {skipped} 条")

    # 验证数据库数据
    after_count = JobInfo.objects.count()
    new_records = after_count - before_count

    print("\n" + "=" * 70)
    print("数据库验证结果")
    print("=" * 70)
    print(f"  测试前记录数: {before_count}")
    print(f"  测试后记录数: {after_count}")
    print(f"  新增记录数:   {new_records}")

    # 验证保存的数据
    if new_records == saved:
        print(f"  ✓ 数据库验证通过: 新增 {new_records} 条记录")
    else:
        print(f"  ✗ 数据库验证失败: 预期新增 {saved} 条，实际新增 {new_records} 条")
        return False

    # 查询最新记录验证字段完整性
    print("\n" + "=" * 70)
    print("数据库字段完整性验证（最新3条）")
    print("=" * 70)

    latest_jobs = JobInfo.objects.order_by("-createTime")[:3]
    for i, job in enumerate(latest_jobs, 1):
        print(f"\n  [{i}] ID:{job.id} {job.title[:30]}")
        print(f"      必填字段检查:")
        all_filled = True
        for field in required_fields:
            value = getattr(job, field, None)
            status = "✓" if value else "✗"
            if not value:
                all_filled = False
            print(
                f"        {status} {field:20s}: {str(value)[:30] if value else 'NULL'}"
            )
        print(f"      完整性: {'通过' if all_filled else '有缺失'}")

    # 最终测试报告
    print("\n" + "=" * 70)
    print("测试报告")
    print("=" * 70)

    success = True

    # 检查1: 数据获取
    if len(jobs) > 0:
        print(f"  [OK] 数据获取: 成功获取 {len(jobs)} 条数据")
    else:
        print(f"  [FAIL] 数据获取: 失败")
        success = False

    # 检查2: 必填字段完整性
    min_completeness = min(r["percentage"] for r in completeness_report.values())
    if min_completeness >= 80:
        print(f"  [OK] 字段完整性: 最低填充率 {min_completeness:.1f}% (>=80%)")
    else:
        print(f"  [FAIL] 字段完整性: 最低填充率 {min_completeness:.1f}% (<80%)")
        success = False

    # 检查3: 数据库保存
    if new_records == saved and saved > 0:
        print(f"  [OK] 数据库保存: 成功保存 {saved} 条记录")
    else:
        print(f"  [FAIL] 数据库保存: 失败")
        success = False

    print("\n" + "=" * 70)
    if success:
        print("测试通过 [PASS]")
    else:
        print("测试失败 [FAIL]")
    print("=" * 70)

    return success


if __name__ == "__main__":
    success = test_crawler()
    sys.exit(0 if success else 1)
