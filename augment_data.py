#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据增强脚本 - 为缺失字段生成合理值
修复可视化中显示"未知"的问题

策略：
1. 基于现有数据的分布进行加权随机采样
2. 根据职位标题关键词智能推断职位类型
3. 为公司性质、融资状态、公司规模等字段添加合理值
"""

import os
import sys
import random
import pandas as pd
from collections import Counter

# 增强后的数据保存路径
INPUT_CSV = "sample_jobs.csv"
OUTPUT_CSV = "sample_jobs_augmented.csv"


def analyze_existing_distribution(df, column):
    """分析现有数据的分布"""
    non_null_values = df[column].dropna()
    if len(non_null_values) == 0:
        return None

    value_counts = Counter(non_null_values)
    total = len(non_null_values)
    distribution = {k: v / total for k, v in value_counts.items()}
    return distribution


def weighted_random_choice(distribution):
    """根据权重分布进行随机选择"""
    if not distribution:
        return None

    values = list(distribution.keys())
    weights = list(distribution.values())

    return random.choices(values, weights=weights, k=1)[0]


def infer_job_type(title):
    """根据职位标题推断职位类型"""
    title_lower = str(title).lower()

    # 关键词映射
    keywords = {
        "大数据": ["大数据", "hadoop", "spark", "hive", "flink", "kafka"],
        "数据分析": ["数据分析", "数据分析师", "bi", "商业分析", "tableau"],
        "数据挖掘": ["数据挖掘", "机器学习", "算法", "推荐", "风控"],
        "算法工程师": ["算法", "深度学习", "nlp", "cv", "图像识别"],
        "开发工程师": ["开发", "后端", "前端", "全栈", "java", "python", "go"],
    }

    for job_type, words in keywords.items():
        for word in words:
            if word in title_lower:
                return job_type

    # 默认返回大数据
    return "大数据"


def generate_company_nature():
    """生成公司性质 - 基于常见分布"""
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
    return weighted_random_choice(distribution)


def generate_company_status():
    """生成融资状态 - 基于常见分布"""
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
    return weighted_random_choice(distribution)


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


def generate_work_experience():
    """生成工作经验要求"""
    options = [
        "经验不限",
        "1年经验",
        "2年经验",
        "3-4年经验",
        "5-7年经验",
        "8-9年经验",
        "10年以上经验",
    ]
    weights = [0.20, 0.15, 0.20, 0.25, 0.12, 0.05, 0.03]
    return random.choices(options, weights=weights, k=1)[0]


def generate_work_tag(job_type):
    """根据职位类型生成工作标签"""
    tag_mapping = {
        "大数据": ["五险一金", "年底双薪", "带薪年假", "弹性工作", "绩效奖金"],
        "数据分析": ["五险一金", "带薪年假", "员工旅游", "定期体检", "绩效奖金"],
        "数据挖掘": ["五险一金", "年底双薪", "股票期权", "带薪年假", "弹性工作"],
        "算法工程师": ["五险一金", "股票期权", "带薪年假", "弹性工作", "绩效奖金"],
        "开发工程师": ["五险一金", "年底双薪", "带薪年假", "定期体检", "绩效奖金"],
    }

    tags = tag_mapping.get(job_type, tag_mapping["大数据"])
    # 随机选择2-4个标签
    num_tags = random.randint(2, 4)
    selected_tags = random.sample(tags, min(num_tags, len(tags)))
    return "、".join(selected_tags)


def generate_salary_month():
    """生成薪资月数"""
    options = ["12薪", "13薪", "14薪", "15薪", "16薪"]
    weights = [0.30, 0.35, 0.20, 0.10, 0.05]
    return random.choices(options, weights=weights, k=1)[0]


def augment_data(df):
    """对数据进行增强"""
    print(f"开始数据增强，共 {len(df)} 条记录...")

    # 记录增强统计
    stats = {
        "companyNature": 0,
        "companyStatus": 0,
        "companyPeople": 0,
        "type": 0,
        "workExperience": 0,
        "workTag": 0,
        "salaryMonth": 0,
    }

    # 分析现有分布（如果有）
    nature_dist = analyze_existing_distribution(df, "companyNature")
    status_dist = analyze_existing_distribution(df, "companyStatus")

    for idx, row in df.iterrows():
        # 1. 增强 type 字段（根据职位标题推断）
        if pd.isna(row.get("type")) or str(row.get("type")) == "大数据":
            df.at[idx, "type"] = infer_job_type(row.get("title", ""))
            stats["type"] += 1

        # 2. 增强 companyNature 字段
        if pd.isna(row.get("companyNature")) or row.get("companyNature") is None:
            if nature_dist:
                df.at[idx, "companyNature"] = weighted_random_choice(nature_dist)
            else:
                df.at[idx, "companyNature"] = generate_company_nature()
            stats["companyNature"] += 1

        # 3. 增强 companyStatus 字段
        if pd.isna(row.get("companyStatus")) or row.get("companyStatus") is None:
            if status_dist:
                df.at[idx, "companyStatus"] = weighted_random_choice(status_dist)
            else:
                df.at[idx, "companyStatus"] = generate_company_status()
            stats["companyStatus"] += 1

        # 4. 增强 companyPeople 字段
        if pd.isna(row.get("companyPeople")) or row.get("companyPeople") is None:
            df.at[idx, "companyPeople"] = generate_company_people()
            stats["companyPeople"] += 1

        # 5. 增强 workExperience 字段
        if pd.isna(row.get("workExperience")) or row.get("workExperience") is None:
            df.at[idx, "workExperience"] = generate_work_experience()
            stats["workExperience"] += 1

        # 6. 增强 workTag 字段
        if pd.isna(row.get("workTag")) or row.get("workTag") is None:
            job_type = df.at[idx, "type"]
            df.at[idx, "workTag"] = generate_work_tag(job_type)
            stats["workTag"] += 1

        # 7. 增强 salaryMonth 字段
        if pd.isna(row.get("salaryMonth")) or row.get("salaryMonth") is None:
            df.at[idx, "salaryMonth"] = generate_salary_month()
            stats["salaryMonth"] += 1

        # 每1000条打印进度
        if (idx + 1) % 1000 == 0:
            print(f"  已处理 {idx + 1}/{len(df)} 条...")

    print("\n增强统计:")
    for field, count in stats.items():
        print(f"  {field}: 填充了 {count} 条")

    return df


def main():
    """主函数"""
    print("=" * 60)
    print("数据增强工具")
    print("=" * 60)

    # 检查输入文件
    if not os.path.exists(INPUT_CSV):
        print(f"错误: 找不到输入文件 {INPUT_CSV}")
        print("请确保 CSV 文件在当前目录")
        sys.exit(1)

    # 读取数据
    print(f"\n读取数据: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    print(f"共 {len(df)} 条记录")
    print(f"字段: {list(df.columns)}")

    # 显示增强前的缺失情况
    print("\n增强前缺失统计:")
    for col in [
        "companyNature",
        "companyStatus",
        "companyPeople",
        "type",
        "workExperience",
        "workTag",
        "salaryMonth",
    ]:
        if col in df.columns:
            missing = df[col].isna().sum()
            print(f"  {col}: {missing} 条缺失 ({missing / len(df) * 100:.1f}%)")

    # 执行增强
    print("\n开始数据增强...")
    df_augmented = augment_data(df.copy())

    # 保存增强后的数据
    output_path = os.path.join(os.path.dirname(__file__), OUTPUT_CSV)
    df_augmented.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\n增强完成！")
    print(f"输出文件: {output_path}")
    print(f"总记录数: {len(df_augmented)}")

    # 显示增强后的缺失情况
    print("\n增强后缺失统计:")
    for col in [
        "companyNature",
        "companyStatus",
        "companyPeople",
        "type",
        "workExperience",
        "workTag",
        "salaryMonth",
    ]:
        if col in df_augmented.columns:
            missing = df_augmented[col].isna().sum()
            print(
                f"  {col}: {missing} 条缺失 ({missing / len(df_augmented) * 100:.1f}%)"
            )

    print("\n" + "=" * 60)
    print("数据增强完成！可以使用 import_jobs_augmented.py 导入")
    print("=" * 60)


if __name__ == "__main__":
    main()
