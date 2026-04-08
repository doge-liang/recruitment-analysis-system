#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
薪资处理工具模块 - 统一处理薪资数据的解析、格式化和转换
"""

import re
from typing import Tuple


def normalize_salary_value(value: int) -> int:
    """
    将元转换为K单位

    示例：
    - 13000 -> 13
    - 13 -> 13
    - 8000 -> 8
    """
    if value >= 1000:
        return value // 1000
    return value


def format_salary_range(min_val: int, max_val: int, suffix: str = "") -> str:
    """
    格式化薪资范围为标准字符串

    示例：
    - (13, 25) -> "13K-25K"
    - (8, 15, "·13薪") -> "8K-15K·13薪"
    """
    if suffix:
        return f"{min_val}K-{max_val}K{suffix}"
    return f"{min_val}K-{max_val}K"


def parse_salary_range(salary_str: str) -> Tuple[int, int]:
    """
    解析薪资字符串，返回 (最低薪资, 最高薪资) 单位为 K

    支持的格式：
    - "13K-25K" -> (13, 25)
    - "13K-25K·13薪" -> (13, 25)
    - "15K以上" -> (15, 999)
    - "15K以下" -> (0, 15)
    - "薪资面议" -> (0, 0)
    """
    if not salary_str or salary_str in ["薪资面议", "面议", "", None]:
        return 0, 0

    # 移除薪资月数后缀
    salary_str = re.sub(r"[·•]\d+薪", "", salary_str)
    salary_str_upper = salary_str.upper()

    # 处理 "15K以上" 格式
    match = re.search(r"(\d+)[K千]?以上", salary_str_upper)
    if match:
        return int(match.group(1)), 999

    # 处理 "15K以下" 格式
    match = re.search(r"(\d+)[K千]?以下", salary_str_upper)
    if match:
        return 0, int(match.group(1))

    # 处理 "15K起" 格式
    match = re.search(r"(\d+)[K千]?起", salary_str_upper)
    if match:
        return int(match.group(1)), 999

    # 标准格式："13K-25K"
    match = re.search(r"(\d+)[K千]?\s*-\s*(\d+)[K千]?", salary_str_upper)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 单个数值 "15K"
    match = re.search(r"(\d+)[K千]?", salary_str_upper)
    if match:
        val = int(match.group(1))
        return val, val

    return 0, 0


def get_salary_avg(salary_str: str) -> float:
    """获取薪资平均值"""
    low, high = parse_salary_range(salary_str)
    if low == 0 and high == 0:
        return 0.0
    return (low + high) / 2.0


def convert_excel_salary_to_k(excel_value) -> int:
    """
    将 Excel 中的薪资数值（元）转换为 K 单位

    示例：13000 -> 13
    """
    try:
        val = int(float(excel_value))
        return normalize_salary_value(val)
    except (ValueError, TypeError):
        return 0


def get_salary_category(avg_salary: float) -> str:
    """
    根据平均薪资返回分类

    - 低薪: < 5K
    - 中薪: 5K - 15K
    - 高薪: 15K - 30K
    - 超高薪: >= 30K
    """
    if avg_salary < 5:
        return "低薪(5K以下)"
    elif avg_salary < 15:
        return "中薪(5K-15K)"
    elif avg_salary < 30:
        return "高薪(15K-30K)"
    else:
        return "超高薪(30K以上)"


def get_salary_bar_category(low_salary: int) -> Tuple[str, int]:
    """
    根据最低薪资返回柱状图分类

    返回 (分类名称, 排序索引)
    """
    ranges = [
        ("5K以下", 0, 5, 0),
        ("5K-10K", 5, 10, 1),
        ("10K-15K", 10, 15, 2),
        ("15K-20K", 15, 20, 3),
        ("20K-30K", 20, 30, 4),
        ("30K以上", 30, 999, 5),
    ]

    for name, low, high, idx in ranges:
        if low <= low_salary < high:
            return name, idx

    return "30K以上", 5


parse_salary = parse_salary_range
