#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 招聘数据.xlsx 导入招聘信息到数据库
支持字段映射和数据转换
"""

import os
import sys

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")

import django

django.setup()

import pandas as pd
from myApp.models import JobInfo


def parse_salary(min_salary, max_salary):
    """
    将最低薪资和最高薪资合并为薪资范围字符串
    例如: 15, 25 -> "15K-25K"
    """
    try:
        min_val = float(min_salary) if pd.notna(min_salary) else 0
        max_val = float(max_salary) if pd.notna(max_salary) else 0

        if min_val > 0 and max_val > 0:
            return f"{int(min_val)}K-{int(max_val)}K"
        elif min_val > 0:
            return f"{int(min_val)}K以上"
        elif max_val > 0:
            return f"{int(max_val)}K以下"
        else:
            return "薪资面议"
    except (ValueError, TypeError):
        return "薪资面议"


def parse_company_tags(row):
    """
    从各项福利字段提取公司福利标签
    """
    tags = []

    # 检查各项福利
    welfare_fields = {
        "是否缴纳五险": "五险",
        "是否有公积金": "公积金",
        "十三薪": "十三薪",
        "带薪年假": "带薪年假",
        "绩效奖金": "绩效奖金",
        "六险一金": "六险一金",
        "七险一金": "七险一金",
    }

    for field, tag in welfare_fields.items():
        if field in row and pd.notna(row[field]):
            value = str(row[field]).strip()
            # 如果值为"是"、"有"、"有公积金"等肯定回答
            if value in ["是", "有", "有公积金", "有五险"]:
                tags.append(tag)

    # 添加其他福利
    if "其他工作福利" in row and pd.notna(row["其他工作福利"]):
        other = str(row["其他工作福利"]).strip()
        if other and other != "无":
            # 按逗号分隔多个福利
            other_tags = [t.strip() for t in other.split(",") if t.strip()]
            tags.extend(other_tags)

    return ",".join(tags) if tags else None


def import_from_excel(excel_path):
    """
    从Excel文件导入招聘数据
    """
    if not os.path.exists(excel_path):
        print(f"❌ 错误: 找不到Excel文件: {excel_path}")
        return 0

    print(f"📖 读取Excel文件: {excel_path}")

    try:
        # 读取Excel文件
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"❌ 读取Excel失败: {e}")
        return 0

    print(f"📊 共有 {len(df)} 条记录")
    print(f"📋 Excel字段: {list(df.columns)}")

    # 字段映射关系
    field_mapping = {
        "company_name": "companyTitle",
        "job_name": "title",
        "area": "address",
        "job_exp": "workExperience",
        "job_deu": "educational",
    }

    # 统计
    new_count = 0
    error_count = 0

    print("\n🚀 开始导入数据...(不检查重复)\n")

    for index, row in df.iterrows():
        try:
            # 提取字段值
            company = (
                str(row.get("company_name", "")).strip()
                if pd.notna(row.get("company_name"))
                else ""
            )
            title = (
                str(row.get("job_name", "")).strip()
                if pd.notna(row.get("job_name"))
                else ""
            )
            area = str(row.get("area", "")).strip() if pd.notna(row.get("area")) else ""

            if not company or not title:
                print(f"  ⚠️  跳过第 {index + 1} 行: 缺少公司名或职位名")
                continue

            # 准备数据
            job_data = {
                "title": title,
                "companyTitle": company,
                "address": area,
                "workExperience": str(row.get("job_exp", "")).strip()
                if pd.notna(row.get("job_exp"))
                else "经验不限",
                "educational": str(row.get("job_deu", "")).strip()
                if pd.notna(row.get("job_deu"))
                else "学历不限",
                "type": "大数据",  # 默认值
                "salary": parse_salary(row.get("最低薪资"), row.get("最高薪资")),
                "companyTags": parse_company_tags(row),
                "companyNature": None,
                "companyStatus": None,
                "companyPeople": None,
                "pratice": False,
            }

            # 创建记录
            JobInfo.objects.create(**job_data)
            new_count += 1

            if (index + 1) % 100 == 0:
                print(f"  ✅ 已导入 {new_count} 条...")

        except Exception as e:
            error_count += 1
            print(f"  ❌ 第 {index + 1} 行导入失败: {e}")

    # 打印统计
    print("\n" + "=" * 50)
    print("📈 导入完成!")
    print("=" * 50)
    print(f"  ✅ 成功导入: {new_count} 条")
    print(f"  ❌ 错误: {error_count} 条")
    print(f"  📊 数据库总计: {JobInfo.objects.count()} 条")

    return new_count


def main():
    """主函数"""
    print("=" * 50)
    print("招聘数据导入工具 (Excel版)")
    print("=" * 50)

    # 默认路径
    default_path = os.path.join(os.path.dirname(__file__), "招聘数据.xlsx")

    # 支持命令行参数指定路径
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    elif os.path.exists(default_path):
        excel_path = default_path
    else:
        # 尝试archive目录
        archive_path = os.path.join(
            os.path.dirname(__file__), "archive", "招聘信息.xlsx"
        )
        if os.path.exists(archive_path):
            excel_path = archive_path
        else:
            print(f"❌ 错误: 找不到Excel文件")
            print(f"请确保以下路径之一存在:")
            print(f"  1. {default_path}")
            print(f"  2. {archive_path}")
            print(f"\n或者通过命令行指定路径:")
            print(f"  python import_excel.py /path/to/your/file.xlsx")
            sys.exit(1)

    # 执行导入
    import_from_excel(excel_path)

    print("\n✨ 导入完成！")


if __name__ == "__main__":
    main()
