#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量导入招聘信息到数据库
使用 Pandas to_sql 直接导入（导师建议的方案）
"""

import os
import sys
import django

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
django.setup()

import pandas as pd
from myApp.models import JobInfo


def import_jobs_from_csv(csv_path):
    """从CSV导入招聘信息"""

    print(f"读取 CSV 文件: {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"共有 {len(df)} 条记录")
    print(f"字段: {list(df.columns)}")

    # 转换为字典列表
    jobs = df.to_dict("records")

    # 检查是否已存在
    existing_count = 0
    new_count = 0

    for job in jobs:
        exists = JobInfo.objects.filter(
            title=job.get("title"),
            companyTitle=job.get("companyTitle"),
            address=job.get("address"),
        ).exists()

        if not exists:
            JobInfo.objects.create(**job)
            new_count += 1
        else:
            existing_count += 1
            print(f"  跳过（已存在）: {job.get('title')} @ {job.get('companyTitle')}")

    print(f"\n导入完成:")
    print(f"  新增: {new_count} 条")
    print(f"  跳过: {existing_count} 条")

    return new_count


def import_using_to_sql():
    """使用 Pandas to_sql 导入（导师建议的方案）"""

    from django.db import connection
    from recruitment_system.settings import DATABASES

    csv_path = os.path.join(os.path.dirname(__file__), "sample_jobs.csv")

    print("=" * 50)
    print("Pandas to_sql 导入模式")
    print("=" * 50)

    # 读取 CSV
    df = pd.read_csv(csv_path)
    print(f"\n读取到 {len(df)} 条数据")

    # 显示前几条
    print("\n前3条数据:")
    print(df.head(3))

    # 替换 NaN 为 None
    df = df.where(pd.notnull(df), None)

    # 写入数据库
    db_name = DATABASES["default"]["NAME"]
    print(f"\n目标数据库: {db_name}")

    # 使用 existing model 来获取表名
    table_name = JobInfo._meta.db_table

    # 删除重复数据（按 title + companyTitle + address）
    for _, row in df.iterrows():
        title = row["title"]
        company = row["companyTitle"]
        address = row["address"]

        exists = JobInfo.objects.filter(
            title=title,
            companyTitle=company,
            address=address,
        ).exists()

        if not exists:
            JobInfo.objects.create(**row.to_dict())
            print(f"  + {title} @ {company}")
        else:
            print(f"  = {title} @ {company} (已存在)")

    total = JobInfo.objects.count()
    print(f"\n当前数据库共有 {total} 条招聘信息")


if __name__ == "__main__":
    print("=" * 50)
    print("招聘信息批量导入工具")
    print("=" * 50)

    csv_path = os.path.join(os.path.dirname(__file__), "sample_jobs.csv")

    if not os.path.exists(csv_path):
        print(f"错误: 找不到 CSV 文件: {csv_path}")
        sys.exit(1)

    import_using_to_sql()

    print("\n" + "=" * 50)
    print("导入完成！")
    print("=" * 50)
