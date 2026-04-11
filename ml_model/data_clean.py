#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据清洗脚本 - Django ORM 版
用途：从 Django 模型读取 JobInfo 数据，识别并修复脏数据，输出清洗报告和干净数据
运行方式：python data_clean.py
"""

import os
import re
import sys
import platform
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
from pathlib import Path

warnings.filterwarnings("ignore")

# ── Django 配置 ────────────────────────────────────────────────────────
import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
django.setup()

from myApp.models import JobInfo


# ══════════════════════════════════════════════════════════════════════
# 0. 配置区 —— 只需修改这里
# ══════════════════════════════════════════════════════════════════════
OUTPUT_DIR  = Path(__file__).parent / "cleaned_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# 薪资合理范围（单位：K/月）
SALARY_MIN_K = 1      # 低于此值视为异常（可能单位是元而非K）
SALARY_MAX_K = 200    # 高于此值视为离群点（200K/月约为顶级大厂高管）

# IQR 离群点检测倍数（越大保留越多数据，推荐 1.5~3.0）
IQR_FACTOR = 1.5

# ══════════════════════════════════════════════════════════════════════
# 1. 中文字体配置
# ══════════════════════════════════════════════════════════════════════
def _setup_font():
    matplotlib.rcParams["axes.unicode_minus"] = False
    candidates = (
        ["Microsoft YaHei", "SimHei", "SimSun"] if platform.system() == "Windows"
        else ["PingFang SC", "Heiti SC"] if platform.system() == "Darwin"
        else ["WenQuanYi Micro Hei", "Noto Sans CJK SC", "SimHei"]
    )
    available = {f.name for f in fm.fontManager.ttflist}
    chosen = next((f for f in candidates if f in available), None)
    if chosen:
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = [chosen] + matplotlib.rcParams["font.sans-serif"]

_setup_font()

# ══════════════════════════════════════════════════════════════════════
# 2. Django Model 数据读取
# ══════════════════════════════════════════════════════════════════════
def load_from_django() -> pd.DataFrame:
    print(f"[连接] 正在从 Django 模型读取 JobInfo 数据 ...")
    jobs = JobInfo.objects.all()

    data = []
    for job in jobs:
        # 解析薪资
        parsed = parse_salary(job.salary)
        avg_salary = parsed[2] if parsed else None

        data.append(
            {
                "id": job.id,
                "title": job.title,
                "salary": job.salary,
                "address": job.address,
                "educational": job.educational,
                "workExperience": job.workExperience,
                "companyPeople": job.companyPeople,
                "companyNature": job.companyNature,
                "companyTitle": job.companyTitle,
                "type": job.type,
                "avg_salary": avg_salary,
            }
        )

    df = pd.DataFrame(data)
    print(f"[读取] 原始数据：{len(df)} 条记录，{df.shape[1]} 列")
    return df

# ══════════════════════════════════════════════════════════════════════
# 3. 薪资解析
# ══════════════════════════════════════════════════════════════════════
def parse_salary(salary_str: str):
    """
    解析薪资字符串，返回 (low_k, high_k, avg_k, issue) 四元组。
    issue 为空字符串表示正常，否则描述问题原因。
    支持格式：
        15K-25K / 15k-25k / 15-25K / 1.5万-2万 / 面议 等
    """
    if not salary_str or pd.isna(salary_str):
        return None, None, None, "空值"

    s = str(salary_str).strip()

    # 面议 / 薪资面议 → 无法解析
    if re.search(r"面议|待遇|negotiable", s, re.I):
        return None, None, None, "面议"

    # 万元格式 → 转换为 K（1万=10K）
    wan_match = re.search(r"([\d.]+)\s*万?\s*[-~至到]\s*([\d.]+)\s*万", s)
    if wan_match:
        low  = float(wan_match.group(1)) * 10
        high = float(wan_match.group(2)) * 10
        return low, high, (low + high) / 2, ""

    # 标准 K 格式
    k_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]?\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*[kK]", s, re.I)
    if k_match:
        low  = float(k_match.group(1))
        high = float(k_match.group(2))

        # 判断单位是否是元而不是K（数值过大）
        if low > 5000 or high > 5000:
            low, high = low / 1000, high / 1000
            return low, high, (low + high) / 2, "单位疑似元（已自动转换）"

        return low, high, (low + high) / 2, ""

    # 纯数字（无区间），视为月薪单一数值
    num_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]", s, re.I)
    if num_match:
        val = float(num_match.group(1))
        return val, val, val, "单点值"

    return None, None, None, f"无法解析格式: {s}"

# ══════════════════════════════════════════════════════════════════════
# 4. 主清洗流程
# ══════════════════════════════════════════════════════════════════════
def clean(df: pd.DataFrame):
    report = {}   # 用于存储各步骤清洗统计

    # ── 4.1 基础字段规范化 ──────────────────────────────────────────
    text_cols = ["title", "address", "educational", "workExperience",
                 "companyPeople", "companyNature", "companyTitle", "type"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": np.nan, "": np.nan})

    # ── 4.2 薪资解析 ─────────────────────────────────────────────────
    parsed = df["salary"].apply(lambda x: parse_salary(x))
    df["salary_low"]   = parsed.apply(lambda x: x[0])
    df["salary_high"]  = parsed.apply(lambda x: x[1])
    df["avg_salary"]   = parsed.apply(lambda x: x[2])
    df["salary_issue"] = parsed.apply(lambda x: x[3])

    n_total   = len(df)
    n_unparsed = df["salary_issue"].ne("").sum()
    report["薪资无法解析"] = int(n_unparsed)
    report["薪资解析成功"] = int(n_total - n_unparsed)

    # 打印薪资问题分布
    issue_counts = df["salary_issue"].value_counts()
    print("\n── 薪资解析问题分布 ──────────────────────")
    print(issue_counts.to_string())

    # ── 4.3 薪资范围过滤（极端值）────────────────────────────────────
    df_valid = df[df["avg_salary"].notna()].copy()

    too_low  = df_valid["avg_salary"] < SALARY_MIN_K
    too_high = df_valid["avg_salary"] > SALARY_MAX_K
    report["薪资低于下限"] = int(too_low.sum())
    report["薪资高于上限"] = int(too_high.sum())

    if too_low.any():
        print(f"\n── 薪资低于 {SALARY_MIN_K}K 的记录（可能单位有误）──")
        print(df_valid[too_low][["title", "salary", "avg_salary"]].head(10).to_string(index=False))

    if too_high.any():
        print(f"\n── 薪资高于 {SALARY_MAX_K}K 的记录（离群点）──")
        print(df_valid[too_high][["title", "salary", "avg_salary"]].head(10).to_string(index=False))

    df_clean = df_valid[~too_low & ~too_high].copy()

    # ── 4.4 IQR 离群点检测 ───────────────────────────────────────────
    q1, q3 = df_clean["avg_salary"].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower_fence = max(SALARY_MIN_K, q1 - IQR_FACTOR * iqr)
    upper_fence = q3 + IQR_FACTOR * iqr

    outliers = (df_clean["avg_salary"] < lower_fence) | (df_clean["avg_salary"] > upper_fence)
    report["IQR离群点数量"] = int(outliers.sum())
    report["IQR下限(K)"]   = round(lower_fence, 1)
    report["IQR上限(K)"]   = round(upper_fence, 1)

    print(f"\n── IQR 离群点检测（fence: {lower_fence:.1f}K ~ {upper_fence:.1f}K）──")
    print(f"   检测到 {outliers.sum()} 条离群薪资记录")
    if outliers.any():
        print(df_clean[outliers][["title", "salary", "avg_salary"]].head(10).to_string(index=False))

    # 标记离群点但不删除，让用户决定
    df_clean["is_outlier"] = outliers

    # ── 4.5 学历标准化 ───────────────────────────────────────────────
    EDU_MAP = {
        # 常见异写 → 统一标准值
        "大专": "大专", "专科": "大专", "大专及以上": "大专",
        "本科": "本科", "本科及以上": "本科",
        "硕士": "硕士", "研究生": "硕士", "硕士及以上": "硕士",
        "博士": "博士", "博士及以上": "博士",
        "不限": "学历不限", "学历不限": "学历不限",
        "高中": "高中及以下", "中专": "高中及以下",
    }
    if "educational" in df_clean.columns:
        before = df_clean["educational"].value_counts()
        df_clean["educational"] = (
            df_clean["educational"]
            .fillna("学历不限")
            .apply(lambda x: next((v for k, v in EDU_MAP.items() if k in str(x)), x))
        )
        after = df_clean["educational"].value_counts()
        report["学历类别数_清洗前"] = int(len(before))
        report["学历类别数_清洗后"] = int(len(after))
        print(f"\n── 学历分布（清洗后）──")
        print(after.to_string())

    # ── 4.6 工作经验标准化 ───────────────────────────────────────────
    EXP_MAP = {
        "在校": "在校/应届", "应届": "在校/应届", "应届生": "在校/应届",
        "1年": "1年以内", "1年以下": "1年以内", "1年以内": "1年以内",
        "1-3年": "1-3年", "一到三年": "1-3年",
        "3-5年": "3-5年", "3年": "3-5年",
        "5-10年": "5-10年", "5年以上": "5-10年",
        "10年以上": "10年以上",
        "不限": "经验不限", "经验不限": "经验不限",
    }
    if "workExperience" in df_clean.columns:
        df_clean["workExperience"] = (
            df_clean["workExperience"]
            .fillna("经验不限")
            .apply(lambda x: next((v for k, v in EXP_MAP.items() if k in str(x)), x))
        )
        print(f"\n── 工作经验分布（清洗后）──")
        print(df_clean["workExperience"].value_counts().to_string())

    # ── 4.7 城市提取（address 中只保留城市名）────────────────────────
    if "address" in df_clean.columns:
        MAJOR_CITIES = [
            "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉",
            "南京", "西安", "重庆", "苏州", "天津", "郑州", "长沙",
            "东莞", "佛山", "合肥", "宁波", "青岛", "沈阳",
        ]
        def extract_city(addr):
            if pd.isna(addr):
                return "其他"
            for city in MAJOR_CITIES:
                if city in str(addr):
                    return city
            return "其他"

        df_clean["city"] = df_clean["address"].apply(extract_city)
        print(f"\n── 城市分布（Top 10）──")
        print(df_clean["city"].value_counts().head(10).to_string())

    # ── 4.8 缺失值统计 ───────────────────────────────────────────────
    print(f"\n── 关键字段缺失率 ──")
    key_cols = ["title", "salary", "avg_salary", "educational", "workExperience", "address", "companyPeople"]
    missing = df_clean[key_cols].isna().mean().mul(100).round(2)
    print(missing.to_string())
    report["清洗后记录数"] = len(df_clean)
    report["删除记录数"]   = n_total - len(df_clean)

    return df_clean, report

# ══════════════════════════════════════════════════════════════════════
# 5. 可视化诊断报告
# ══════════════════════════════════════════════════════════════════════
def plot_diagnostics(df_raw: pd.DataFrame, df_clean: pd.DataFrame):
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle("数据清洗诊断报告", fontsize=16, fontweight="bold")

    # ── 图1：薪资分布对比（清洗前 vs 后）──────────────────────────
    ax = axes[0, 0]
    raw_salary = df_raw["avg_salary"].dropna()
    clean_salary = df_clean.loc[~df_clean["is_outlier"], "avg_salary"].dropna()
    ax.hist(raw_salary.clip(0, 200), bins=40, alpha=0.5, label="清洗前", color="#4C72B0", density=True)
    ax.hist(clean_salary.clip(0, 200), bins=40, alpha=0.5, label="清洗后（去离群）", color="#55A868", density=True)
    ax.set_xlabel("平均薪资 (K)")
    ax.set_ylabel("概率密度")
    ax.set_title("薪资分布对比")
    ax.legend()

    # ── 图2：薪资箱线图（离群点高亮）──────────────────────────────
    ax = axes[0, 1]
    data_box = [
        df_raw["avg_salary"].dropna().clip(0, 400).values,
        df_clean["avg_salary"].dropna().clip(0, 400).values,
    ]
    bp = ax.boxplot(data_box, labels=["清洗前", "清洗后"], patch_artist=True)
    bp["boxes"][0].set_facecolor("#FA8072")
    bp["boxes"][1].set_facecolor("#87CEEB")
    ax.set_ylabel("平均薪资 (K)")
    ax.set_title("薪资箱线图")

    # ── 图3：学历分布 ────────────────────────────────────────────
    ax = axes[0, 2]
    edu_counts = df_clean["educational"].value_counts() if "educational" in df_clean.columns else pd.Series()
    if not edu_counts.empty:
        colors = plt.cm.Set2(np.linspace(0, 1, len(edu_counts)))
        ax.barh(edu_counts.index, edu_counts.values, color=colors)
        for i, v in enumerate(edu_counts.values):
            ax.text(v + 5, i, str(v), va="center", fontsize=9)
    ax.set_xlabel("记录数")
    ax.set_title("学历分布（清洗后）")

    # ── 图4：各学历薪资箱线图 ────────────────────────────────────
    ax = axes[1, 0]
    edu_order = ["大专", "本科", "硕士", "博士"]
    valid = df_clean[~df_clean["is_outlier"]]
    groups = [valid.loc[valid["educational"] == e, "avg_salary"].dropna().values for e in edu_order]
    groups = [g for g in groups if len(g) > 0]
    labels = [e for e, g in zip(edu_order, [valid.loc[valid["educational"] == e] for e in edu_order]) if len(g) > 0]
    if groups:
        bp2 = ax.boxplot(groups, labels=labels, patch_artist=True)
        colors2 = ["#FA8072", "#87CEEB", "#9370DB", "#DDA0DD"]
        for patch, c in zip(bp2["boxes"], colors2):
            patch.set_facecolor(c)
            patch.set_alpha(0.7)
        for i, g in enumerate(groups, 1):
            ax.scatter(i, g.mean(), marker="D", color="red", zorder=5, s=50)
    ax.set_ylabel("薪资 (K)")
    ax.set_title("各学历薪资分布（去离群后）")

    # ── 图5：工作经验分布 ────────────────────────────────────────
    ax = axes[1, 1]
    if "workExperience" in df_clean.columns:
        exp_counts = df_clean["workExperience"].value_counts()
        exp_counts.plot(kind="bar", ax=ax, color="#4C72B0", alpha=0.8)
        ax.set_ylabel("记录数")
        ax.set_title("工作经验分布（清洗后）")
        ax.tick_params(axis="x", rotation=30)

    # ── 图6：城市分布（Top 10）──────────────────────────────────
    ax = axes[1, 2]
    if "city" in df_clean.columns:
        city_counts = df_clean["city"].value_counts().head(10)
        city_counts.plot(kind="bar", ax=ax, color="#DD8452", alpha=0.8)
        ax.set_ylabel("记录数")
        ax.set_title("城市分布 Top10（清洗后）")
        ax.tick_params(axis="x", rotation=30)

    fig.tight_layout()
    out_path = OUTPUT_DIR / "cleaning_report.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  ✔ 诊断图表已保存: {out_path}")

# ══════════════════════════════════════════════════════════════════════
# 6. 输出清洗报告 & 干净数据
# ══════════════════════════════════════════════════════════════════════════════
def save_outputs(df_clean: pd.DataFrame, report: dict, import_to_db: bool = False):
    # 输出 CSV（去掉离群点的干净数据）
    df_no_outlier = df_clean[~df_clean["is_outlier"]].copy()
    csv_path = OUTPUT_DIR / "cleaned_jobs.csv"
    df_no_outlier.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 输出离群点单独文件供人工检查
    df_outlier = df_clean[df_clean["is_outlier"]].copy()
    if not df_outlier.empty:
        outlier_path = OUTPUT_DIR / "outlier_jobs.csv"
        df_outlier.to_csv(outlier_path, index=False, encoding="utf-8-sig")
        print(f"  ✔ 离群点数据已保存: {outlier_path}（{len(df_outlier)} 条，请人工核查）")

    # 打印汇总报告
    print("\n" + "=" * 50)
    print("清洗汇总报告")
    print("=" * 50)
    for k, v in report.items():
        print(f"  {k:<20} {v}")
    print(f"  {'最终可用记录':<20} {len(df_no_outlier)}")
    print(f"  {'输出路径':<20} {csv_path}")
    print("=" * 50)

    # 导入回数据库
    if import_to_db:
        import_to_database(df_no_outlier)


# ══════════════════════════════════════════════════════════════════════
# 6.1 导入清洗后数据到数据库
# ══════════════════════════════════════════════════════════════════════
def import_to_database(df_clean: pd.DataFrame):
    """将清洗后的数据更新回数据库（通过新增字段）"""
    from django.db import transaction

    print("\n── 导入数据到数据库 ──")

    # 注意：这里需要在 JobInfo 模型中先添加新字段才能更新
    # 如果模型没有新字段，可以选择：
    # 1. 直接更新现有字段（薪资标准化）
    # 2. 添加新字段后再更新

    updated_count = 0
    skipped_count = 0

    with transaction.atomic():
        for _, row in df_clean.iterrows():
            job_id = row.get("id")
            if not job_id:
                skipped_count += 1
                continue

            try:
                job = JobInfo.objects.get(id=job_id)

                # 更新标准化后的字段（学历、工作经验等）
                if "educational" in row and pd.notna(row.get("educational")):
                    job.educational = row["educational"]
                if "workExperience" in row and pd.notna(row.get("workExperience")):
                    job.workExperience = row["workExperience"]

                # 如果有新增字段，可以更新如：
                # if hasattr(job, 'avg_salary'):
                #     job.avg_salary = row.get("avg_salary")
                # if hasattr(job, 'city'):
                #     job.city = row.get("city")

                job.save()
                updated_count += 1
            except JobInfo.DoesNotExist:
                skipped_count += 1
            except Exception as e:
                print(f"  ⚠ 更新失败 ID={job_id}: {e}")
                skipped_count += 1

    print(f"  ✔ 更新成功: {updated_count} 条")
    print(f"  ⚠ 跳过/失败: {skipped_count} 条")

    return updated_count, skipped_count

# ══════════════════════════════════════════════════════════════════════
# 7. 入口
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="招聘数据清洗脚本")
    parser.add_argument("--import", dest="import_db", action="store_true",
                     help="将清洗后的数据导入回数据库")
    args = parser.parse_args()

    print("=" * 50)
    print("招聘数据清洗脚本")
    print("=" * 50)

    # 读取原始数据
    df_raw = load_from_django()

    # 执行清洗
    df_clean, report = clean(df_raw.copy())

    # 生成诊断图表
    print("\n── 生成诊断图表 ──")
    plot_diagnostics(df_raw, df_clean)

    # 保存输出
    save_outputs(df_clean, report, import_to_db=args.import_db)

    if args.import_db:
        print("\n✅ 数据清洗完成并已导入数据库！")
    else:
        print("\n✅ 数据清洗完成！")
        print(f"   如需导入数据库，请添加参数: python data_clean.py --import")

    print(f"   干净数据：{OUTPUT_DIR}/cleaned_jobs.csv")
    print(f"   诊断图表：{OUTPUT_DIR}/cleaning_report.png")