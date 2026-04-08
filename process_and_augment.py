#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整的数据处理流程：
1. 从 Excel 读取原始数据
2. 映射字段到数据库模型
3. 生成增强字段（使用统一的薪资工具）
4. 保存为可直接导入的 CSV
"""

import os
import sys
import random
import pandas as pd
from datetime import datetime
from collections import Counter

# 添加项目路径以导入 Django 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
import django

django.setup()

from myApp.salary_utils import convert_excel_salary_to_k, format_salary_range

# 路径配置
INPUT_EXCEL = "archive/招聘信息.xlsx"
OUTPUT_CSV = "sample_jobs_augmented.csv"


def infer_job_type(title):
    """根据职位标题推断职位类型"""
    title_lower = str(title).lower()

    keywords = {
        "大数据": [
            "大数据",
            "hadoop",
            "spark",
            "hive",
            "flink",
            "kafka",
            "etl",
            "数据仓库",
        ],
        "数据分析": ["数据分析", "数据分析师", "bi", "商业分析", "tableau", "powerbi"],
        "数据挖掘": ["数据挖掘", "机器学习", "推荐", "风控", "数据建模"],
        "算法工程师": ["算法", "深度学习", "nlp", "cv", "图像识别", "自然语言"],
        "开发工程师": ["开发", "后端", "前端", "全栈", "java", "python", "go", "架构"],
    }

    for job_type, words in keywords.items():
        for word in words:
            if word in title_lower:
                return job_type

    return "大数据"


def generate_company_nature():
    """生成公司性质"""
    distribution = {
        "民营公司": 0.45,
        "上市公司": 0.20,
        "外资(欧美)": 0.10,
        "合资": 0.08,
        "国企": 0.07,
        "外资(非欧美)": 0.05,
        "事业单位": 0.03,
        "创业公司": 0.02,
    }
    values = list(distribution.keys())
    weights = list(distribution.values())
    return random.choices(values, weights=weights, k=1)[0]


def generate_company_status():
    """生成融资状态"""
    distribution = {
        "已上市": 0.25,
        "不需要融资": 0.20,
        "A轮": 0.15,
        "B轮": 0.12,
        "C轮": 0.10,
        "D轮及以上": 0.08,
        "天使轮": 0.06,
        "未融资": 0.04,
    }
    values = list(distribution.keys())
    weights = list(distribution.values())
    return random.choices(values, weights=weights, k=1)[0]


def generate_company_people():
    """生成公司规模"""
    ranges = [
        "少于50人",
        "50-150人",
        "150-500人",
        "500-1000人",
        "1000-5000人",
        "5000-10000人",
        "10000人以上",
    ]
    weights = [0.10, 0.15, 0.25, 0.20, 0.15, 0.10, 0.05]
    return random.choices(ranges, weights=weights, k=1)[0]


def generate_work_tag(row):
    """根据福利字段生成工作标签"""
    tags = []

    # 从福利字段提取
    if row.get("是否缴纳五险") == "有":
        tags.append("五险")
    if row.get("是否有公积金") == "有":
        tags.append("公积金")
    if row.get("十三薪") == "有":
        tags.append("年底双薪")
    if row.get("带薪年假") == "有":
        tags.append("带薪年假")
    if row.get("绩效奖金") == "有":
        tags.append("绩效奖金")
    if row.get("六险一金") == "有":
        tags.append("六险一金")
    if row.get("七险一金") == "有":
        tags.append("七险一金")

    # 添加一些通用标签
    common_tags = ["弹性工作", "定期体检", "员工旅游", "股票期权", "餐补"]
    if len(tags) < 3:
        tags.extend(random.sample(common_tags, min(3 - len(tags), len(common_tags))))

    return "、".join(tags[:5]) if tags else "五险一金、带薪年假"


def generate_salary_month():
    """生成薪资月数"""
    options = ["12薪", "13薪", "14薪", "15薪", "16薪"]
    weights = [0.30, 0.35, 0.20, 0.10, 0.05]
    return random.choices(options, weights=weights, k=1)[0]


def process_and_augment_data():
    """处理并增强数据"""
    print(f"读取 Excel 文件: {INPUT_EXCEL}")
    df = pd.read_excel(INPUT_EXCEL)
    print(f"共 {len(df)} 条原始记录")
    print("注意：保留所有记录（不去重），仅增加缺失列")

    # 准备输出数据
    processed_data = []

    for idx, row in df.iterrows():
        # 转换薪资（Excel中的元 -> K）
        min_salary_k = convert_excel_salary_to_k(row.get("最低薪资", 10))
        max_salary_k = convert_excel_salary_to_k(row.get("最高薪资", 20))

        # 映射字段
        job_data = {
            # 基础字段（从Excel映射）
            "title": row.get("job_name", ""),
            "address": row.get("area", ""),
            "companyTitle": row.get("company_name", ""),
            "educational": row.get("job_deu", "本科"),
            "workExperience": row.get("job_exp", "经验不限"),
            # 薪资字段（使用统一工具格式化）
            "salary": format_salary_range(min_salary_k, max_salary_k),
            # 增强字段 - 公司信息
            "companyNature": generate_company_nature(),
            "companyStatus": generate_company_status(),
            "companyPeople": generate_company_people(),
            # 增强字段 - 职位信息
            "type": infer_job_type(row.get("job_name", "")),
            "workTag": generate_work_tag(row),
            "salaryMonth": generate_salary_month(),
            # 默认字段
            "companyTags": "",
            "hrWork": "",
            "hrName": "",
            "companyAvatar": "",
            "detailUrl": "",
            "companyUrl": "",
            "dist": "",
            # 时间戳
            "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        processed_data.append(job_data)

        if (idx + 1) % 1000 == 0:
            print(f"  已处理 {idx + 1}/{len(df)} 条...")

    # 创建DataFrame并保存
    df_output = pd.DataFrame(processed_data)

    # 显示增强统计
    print("\n数据增强统计:")
    print(f"  总记录数: {len(df_output)}")
    print(f"  companyNature: 100% 已填充")
    print(f"  companyStatus: 100% 已填充")
    print(f"  companyPeople: 100% 已填充")
    print(f"  type: 100% 已填充（基于职位标题推断）")
    print(f"  workTag: 100% 已填充（基于福利字段）")
    print(f"  salaryMonth: 100% 已填充")

    # 保存CSV
    df_output.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"\n已保存到: {OUTPUT_CSV}")

    return df_output


def main():
    print("=" * 60)
    print("数据增强与处理工具")
    print("=" * 60)

    if not os.path.exists(INPUT_EXCEL):
        print(f"错误: 找不到输入文件 {INPUT_EXCEL}")
        sys.exit(1)

    process_and_augment_data()

    print("\n" + "=" * 60)
    print("数据处理完成！")
    print("下一步: 运行 import_augmented.py 导入数据库")
    print("=" * 60)


if __name__ == "__main__":
    main()
