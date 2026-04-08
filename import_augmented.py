#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导入增强后的数据到数据库
支持清空导入或追加导入模式
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
django.setup()

import pandas as pd
from myApp.models import JobInfo


def clear_database():
    """清空JobInfo表"""
    count = JobInfo.objects.count()
    print(f"清空数据库，现有 {count} 条记录...")
    JobInfo.objects.all().delete()
    print("数据库已清空")


def import_augmented_data(csv_path, append=False):
    """导入增强后的数据"""
    print(f"\n读取增强后的数据: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"共 {len(df)} 条记录")

    # 替换NaN为None
    df = df.where(pd.notnull(df), None)

    # 批量创建
    jobs_to_create = []
    for _, row in df.iterrows():
        job_data = row.to_dict()

        # 移除id字段（如果存在）
        job_data.pop("id", None)
        job_data.pop("Unnamed: 0", None)

        # 处理日期字段
        if "createTime" in job_data and pd.notna(job_data["createTime"]):
            try:
                job_data["createTime"] = pd.to_datetime(job_data["createTime"])
            except:
                job_data["createTime"] = None

        jobs_to_create.append(JobInfo(**job_data))

    # 批量插入
    print(f"\n开始导入 {len(jobs_to_create)} 条记录...")
    JobInfo.objects.bulk_create(jobs_to_create, batch_size=1000)

    total = JobInfo.objects.count()
    if append:
        print(f"追加完成！数据库现有 {total} 条记录")
    else:
        print(f"导入完成！数据库现有 {total} 条记录")

    return len(jobs_to_create)


def verify_data():
    """验证数据质量"""
    print("\n" + "=" * 60)
    print("数据质量验证")
    print("=" * 60)

    total = JobInfo.objects.count()
    print(f"总记录数: {total}")

    # 检查各字段的NULL值情况
    fields_to_check = [
        "companyNature",
        "companyStatus",
        "companyPeople",
        "type",
        "workExperience",
        "workTag",
        "salaryMonth",
    ]

    for field in fields_to_check:
        null_count = JobInfo.objects.filter(**{f"{field}__isnull": True}).count()
        empty_count = JobInfo.objects.filter(**{field: ""}).count()
        total_missing = null_count + empty_count
        print(
            f"  {field}: {total - total_missing}/{total} 有值 ({(total - total_missing) / total * 100:.1f}%)"
        )


def main():
    print("=" * 60)
    print("增强数据导入工具")
    print("=" * 60)

    csv_path = os.path.join(os.path.dirname(__file__), "sample_jobs_augmented.csv")

    if not os.path.exists(csv_path):
        print(f"错误: 找不到增强后的数据文件 {csv_path}")
        print("请先运行 process_and_augment.py 生成增强数据")
        sys.exit(1)

    # 解析参数
    append_mode = "--append" in sys.argv
    force_mode = "--force" in sys.argv

    if append_mode:
        print("\n模式: 追加导入（不清空数据库）")
        current_count = JobInfo.objects.count()
        print(f"当前数据库有 {current_count} 条记录")

        # 追加导入
        imported = import_augmented_data(csv_path, append=True)
        verify_data()

        print("\n" + "=" * 60)
        print(f"追加导入完成！新增 {imported} 条记录")
        print("=" * 60)
    else:
        print("\n模式: 全新导入（先清空数据库）")

        # 确认清空
        if not force_mode:
            print("\n警告: 这将清空数据库中的所有招聘信息！")
            print("使用 --force 参数跳过确认，或使用 --append 参数追加导入")
            response = input("是否继续? (yes/no): ")
            if response.lower() != "yes":
                print("已取消")
                sys.exit(0)

        # 执行导入
        clear_database()
        import_augmented_data(csv_path, append=False)
        verify_data()

        print("\n" + "=" * 60)
        print("导入完成！")
        print("提示: 如需增加数据量，请使用 --append 参数再次运行此脚本")
        print("=" * 60)


if __name__ == "__main__":
    main()
