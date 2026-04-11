#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
机器学习模块 - 薪资预测和岗位推荐
"""

import os
import re
import sys
import platform
import joblib
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
from pathlib import Path
from scipy import stats
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

# ── 中文字体配置（按操作系统自动选择）────────────────────────────────
def _setup_chinese_font():
    """自动检测并配置中文字体，兼容 Windows / macOS / Linux"""
    matplotlib.rcParams["axes.unicode_minus"] = False  # 修复负号显示

    _os = platform.system()
    if _os == "Windows":
        candidates = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi", "FangSong"]
    elif _os == "Darwin":
        candidates = ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS"]
    else:
        candidates = ["WenQuanYi Micro Hei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"]

    available = {f.name for f in fm.fontManager.ttflist}
    chosen = next((f for f in candidates if f in available), None)

    if chosen:
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = [chosen] + matplotlib.rcParams["font.sans-serif"]
        print(f"[字体] 使用中文字体: {chosen}")
    else:
        print(f"[字体警告] 未找到中文字体，图表中文标签可能显示为方块。")
        print(f"  Windows 用户建议安装 Microsoft YaHei 或 SimHei。")
        print(f"  当前可用字体: {sorted(available)[:10]} ...")

_setup_chinese_font()

# ── Django 配置 ────────────────────────────────────────────────────────
import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
django.setup()

from myApp.models import JobInfo


# ══════════════════════════════════════════════════════════════════════
# 薪资预测模型
# ══════════════════════════════════════════════════════════════════════
class SalaryPredictor:
    """薪资预测模型 - 使用随机森林回归"""

    # 常用技能标签映射
    SKILL_TAGS = {
        "Python": ["python", "爬虫", "django", "flask", "tornado"],
        "Java": ["java", "spring", "springboot", "mybatis"],
        "Go": ["go", "golang", "gin"],
        "前端": ["vue", "react", "javascript", "js", "typescript", "html", "css", "前端"],
        "数据库": ["mysql", "redis", "mongodb", "oracle", "sql", "elasticsearch"],
        "大数据": ["hadoop", "spark", "hive", "kafka", "flink"],
        "算法": ["算法", "机器学习", "深度学习", "ai", "人工智能", "nlp"],
        "测试": ["测试", "自动化", "selenium", "unittest"],
        "Linux": ["linux", "shell", "运维", "docker", "k8s", "kubernetes"],
        "架构": ["架构", "微服务", "分布式", "高并发", "设计模式"],
    }

    # 融资状态映射
    COMPANY_STATUS_MAP = {
        "上市": "已上市",
        "已上市": "已上市",
        "B轮": "B轮",
        "C轮": "C轮",
        "D轮及以上": "D轮及以上",
        "天使": "初创期",
        "战略投资": "战略投资",
        "不需要融资": "不需要融资",
    }

    # 岗位类型映射
    TYPE_MAP = {
        "技术": ["后端", "前端", "全栈", "移动", "测试", "运维", "开发", "算法", "安全", "数据"],
        "产品": ["产品", "策划", "设计", "交互"],
        "运营": ["运营", "编辑", "客服", "商务", "市场"],
        "职能": ["行政", "人力", "财务", "法务"],
    }

    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.skill_encoders = {}
        self.feature_columns = [
            "educational",        # 学历要求
            "workExperience",   # 工作经验
            "companyPeople",   # 公司规模
            "companyStatus",  # 融资状态（新增）
            "type",           # 岗位类型（新增）
            "city",           # 城市
        ]
        self.skill_columns = list(self.SKILL_TAGS.keys())  # 技能特征
        self.target_column = "avg_salary"
        self.model_path = Path(__file__).parent / "salary_model.pkl"
        self.plot_dir = Path(__file__).parent / "plots"
        self.plot_dir.mkdir(exist_ok=True)

    # ── 薪资解析 ───────────────────────────────────────────────────���────
    def parse_salary(self, salary_str: str):
        """解析薪资字符串，返回 (low_k, high_k, avg_k, issue)"""
        if not salary_str or pd.isna(salary_str):
            return None, None, None, "空值"

        s = str(salary_str).strip()

        # 面议
        if re.search(r"面议|待遇|negotiable", s, re.I):
            return None, None, None, "面议"

        # 万元格式
        wan_match = re.search(r"([\d.]+)\s*万?\s*[-~至到]\s*([\d.]+)\s*万", s)
        if wan_match:
            low = float(wan_match.group(1)) * 10
            high = float(wan_match.group(2)) * 10
            return low, high, (low + high) / 2, ""

        # 标准 K 格式
        k_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]?\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*[kK]", s, re.I)
        if k_match:
            low = float(k_match.group(1))
            high = float(k_match.group(2))
            # 判断单位是否是元
            if low > 5000 or high > 5000:
                low, high = low / 1000, high / 1000
                return low, high, (low + high) / 2, "单位转换"
            return low, high, (low + high) / 2, ""

        # 纯数字
        num_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]", s, re.I)
        if num_match:
            val = float(num_match.group(1))
            return val, val, val, "单点值"

        return None, None, None, f"无法解析: {s}"

    # ── 技能标签解析 ────────────────────────────────────────────────────────
    def parse_skills(self, work_tag: str) -> dict:
        """解析技能标签，返回各技能是否匹配"""
        if not work_tag or pd.isna(work_tag):
            return {tag: 0 for tag in self.SKILL_TAGS.keys()}

        tag_lower = str(work_tag).lower()
        return {
            tag: 1 if any(kw in tag_lower for kw in keywords) else 0
            for tag, keywords in self.SKILL_TAGS.items()
        }

    # ── 城市提取 ────────────────────────────────────────────────────────
    def extract_city(self, address: str) -> str:
        """从地址中提取城市名"""
        if not address or pd.isna(address):
            return "其他"

        major_cities = [
            "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉",
            "南京", "西安", "重庆", "苏州", "天津", "郑州", "长沙",
        ]
        for city in major_cities:
            if city in str(address):
                return city
        return "其他"

    # ── 岗位类型分类 ───────────────────────────────────────────
    def categorize_type(self, job_type: str) -> str:
        """将岗位类型映射到大类"""
        if not job_type or pd.isna(job_type):
            return "技术"

        for category, keywords in self.TYPE_MAP.items():
            if any(kw in str(job_type) for kw in keywords):
                return category
        return "技术"

    # ── 融资状态标准化 ───────────────────────────────────────────
    def normalize_status(self, status: str) -> str:
        """标准化融资状态"""
        if not status or pd.isna(status):
            return "未知"

        for key, value in self.COMPANY_STATUS_MAP.items():
            if key in str(status):
                return value
        return "未知"

    # ── 数据准备 ──────────────────────────────────────────────────────
    def prepare_data(self):
        """准备训练数据"""
        jobs = JobInfo.objects.all()

        data = []
        for job in jobs:
            # 解析薪资
            low, high, avg_salary, issue = self.parse_salary(job.salary)
            if avg_salary is None:
                continue

            # 解析技能标签
            skills = self.parse_skills(job.workTag)

            data.append({
                "title": job.title,
                "address": job.address,
                "city": self.extract_city(job.address),
                "type": self.categorize_type(job.type),
                "educational": job.educational or "学历不限",
                "workExperience": job.workExperience or "经验不限",
                "companyNature": job.companyNature or "未知",
                "companyPeople": job.companyPeople or "未知",
                "companyStatus": self.normalize_status(job.companyStatus),
                "workTag": job.workTag,
                "avg_salary": avg_salary,
                **skills,
            })

        return pd.DataFrame(data)

    # ── 特征编码 ──────────────────────────────────────────────────────
    def encode_categorical(self, df, fit=True):
        """对分类特征进行标签编码"""
        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = "未知"
            df[col] = df[col].fillna("未知").astype(str)

            if fit:
                le = LabelEncoder()
                le.fit(df[col])
                self.label_encoders[col] = le
                df[col + "_encoded"] = le.transform(df[col])
            else:
                le = self.label_encoders.get(col)
                if le is None:
                    df[col + "_encoded"] = 0
                else:
                    known_classes = set(le.classes_)
                    default_value = (
                        "未知" if "未知" in known_classes else le.classes_[0]
                    )
                    df[col] = df[col].apply(
                        lambda x: x if x in known_classes else default_value
                    )
                    df[col + "_encoded"] = le.transform(df[col])

        return df

    # ── 训练 ──────────────────────────────────────────────────────────
    def train(self, test_size=0.2, n_estimators=100, max_depth=15):
        """训练模型，训练完成后自动生成全部可视化图表"""
        print("准备训练数据...")
        df = self.prepare_data()

        if len(df) < 10:
            print("数据量不足，无法训练模型")
            return False

        print(f"共有 {len(df)} 条有效数据")

        df = self.encode_categorical(df, fit=True)

        # 分类特征 + 技能特征
        feature_cols = [col + "_encoded" for col in self.feature_columns] + self.skill_columns
        X = df[feature_cols].values
        y = df[self.target_column].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        print("训练随机森林回归模型...")
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        # ── 评估 ──────────────────────────────────────────────────────
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        metrics = {
            "train": {
                "mae":  mean_absolute_error(y_train, y_train_pred),
                "rmse": np.sqrt(mean_squared_error(y_train, y_train_pred)),
                "r2":   r2_score(y_train, y_train_pred),
            },
            "test": {
                "mae":  mean_absolute_error(y_test, y_test_pred),
                "rmse": np.sqrt(mean_squared_error(y_test, y_test_pred)),
                "r2":   r2_score(y_test, y_test_pred),
            },
        }

        print(f"训练集 MAE={metrics['train']['mae']:.2f}  RMSE={metrics['train']['rmse']:.2f}  R²={metrics['train']['r2']:.4f}")
        print(f"测试集 MAE={metrics['test']['mae']:.2f}   RMSE={metrics['test']['rmse']:.2f}  R²={metrics['test']['r2']:.4f}")

        self.save_model()

        # ── 生成可视化 ────────────────────────────────────────────────
        feature_names_cn = ["学历要求", "工作经验", "公司规模", "融资状态", "岗位类型", "城市"] + self.skill_columns
        self._plot_pred_vs_actual(y_test, y_test_pred)
        self._plot_feature_importance(feature_names_cn)
        self._plot_metrics(metrics)
        self._plot_error_distribution(y_test, y_test_pred)
        self._plot_salary_by_education(df)

        print(f"\n✅ 所有图表已保存到: {self.plot_dir}")
        return True

    # ── 预测 ──────────────────────────────────────────────────────────
    def predict(self, features, skills=None):
        """
        预测薪资

        Args:
            features: [educational, workExperience, companyPeople, companyStatus, type, city]
            skills: dict 可选，技能标签 dict，如 {"Python": 1, "Java": 0, ...}

        Returns:
            预测的薪资（单位：K）
        """
        if self.model is None:
            self.load_model()

        if self.model is None:
            return 15.0

        # 构建特征字典
        feature_dict = dict(zip(self.feature_columns, features))
        if skills:
            feature_dict.update(skills)
        else:
            feature_dict.update({tag: 0 for tag in self.skill_columns})

        df = pd.DataFrame([feature_dict])
        df = self.encode_categorical(df, fit=False)

        # 分类特征 + 技能特征
        feature_cols = [col + "_encoded" for col in self.feature_columns] + self.skill_columns
        X = df[feature_cols].values

        return round(float(self.model.predict(X)[0]), 1)

    # ══════════════════════════════════════════════════════════════════
    # 可视化方法
    # ══════════════════════════════════════════════════════════════════

    def _plot_pred_vs_actual(self, y_true, y_pred):
        """图①  预测值 vs 实际值散点图"""
        r2 = r2_score(y_true, y_pred)
        errors = np.abs(y_pred - y_true)

        fig, ax = plt.subplots(figsize=(7, 6))
        sc = ax.scatter(
            y_true, y_pred,
            c=errors, cmap="RdYlGn_r",
            alpha=0.75, s=60, edgecolors="none",
        )
        plt.colorbar(sc, ax=ax, label="预测误差 (K)")

        # 理想预测线
        lims = [min(y_true.min(), y_pred.min()) - 2,
                max(y_true.max(), y_pred.max()) + 2]
        ax.plot(lims, lims, "r--", linewidth=1.5, label="理想预测线 (y=x)")

        ax.set_xlabel("实际薪资 (K)")
        ax.set_ylabel("预测薪资 (K)")
        ax.set_title("随机森林回归模型 - 薪资预测结果对比")
        ax.text(0.05, 0.93, f"R² = {r2:.3f}", transform=ax.transAxes,
                fontsize=12, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.plot_dir / "01_pred_vs_actual.png", dpi=150)
        plt.close(fig)
        print("  ✔ 图①已保存: 01_pred_vs_actual.png")

    def _plot_feature_importance(self, feature_names_cn):
        """图②  特征重要性柱状图"""
        importances = self.model.feature_importances_
        indices = np.argsort(importances)[::-1]
        sorted_names = [feature_names_cn[i] for i in indices]
        sorted_vals = importances[indices]

        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.barh(sorted_names[::-1], sorted_vals[::-1] * 100,
                       color="#1f77b4", edgecolor="white")

        for bar, val in zip(bars, sorted_vals[::-1] * 100):
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f}%", va="center", fontsize=10)

        ax.set_xlabel("特征重要性")
        ax.set_ylabel("特征名称")
        ax.set_title("随机森林模型 - 特征重要性分析")
        ax.set_xlim(0, sorted_vals.max() * 130)
        fig.tight_layout()
        fig.savefig(self.plot_dir / "02_feature_importance.png", dpi=150)
        plt.close(fig)
        print("  ✔ 图②已保存: 02_feature_importance.png")

    def _plot_metrics(self, metrics):
        """图③（左）  回归性能指标对比柱状图"""
        labels = ["MAE", "RMSE", "R²"]
        train_vals = [metrics["train"]["mae"], metrics["train"]["rmse"], metrics["train"]["r2"]]
        test_vals  = [metrics["test"]["mae"],  metrics["test"]["rmse"],  metrics["test"]["r2"]]

        x = np.arange(len(labels))
        width = 0.35

        fig, ax = plt.subplots(figsize=(6, 5))
        b1 = ax.bar(x - width / 2, train_vals, width, label="训练集", color="#4C72B0")
        b2 = ax.bar(x + width / 2, test_vals,  width, label="测试集",  color="#DD8452")

        for bar in list(b1) + list(b2):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=9)

        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("指标值")
        ax.set_title("随机森林回归 - 性能指标")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.plot_dir / "03_regression_metrics.png", dpi=150)
        plt.close(fig)
        print("  ✔ 图③已保存: 03_regression_metrics.png")

    def _plot_error_distribution(self, y_true, y_pred):
        """图⑤  预测误差分布直方图"""
        errors = y_pred - y_true
        mu, sigma = errors.mean(), errors.std()

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(errors, bins=30, density=True, alpha=0.7, color="#4C72B0",
                edgecolor="white", label="误差分布")

        # 正态分布拟合曲线
        x_range = np.linspace(errors.min() - 1, errors.max() + 1, 300)
        ax.plot(x_range, stats.norm.pdf(x_range, mu, sigma),
                "r-", linewidth=2, label=f"正态分布拟合\nμ={mu:.2f}, σ={sigma:.2f}")

        ax.axvline(0, color="green", linestyle="--", linewidth=1.5, label="零误差线")
        ax.set_xlabel("预测误差 (K)")
        ax.set_ylabel("概率密度")
        ax.set_title("随机森林回归 - 预测误差分布")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.plot_dir / "05_error_distribution.png", dpi=150)
        plt.close(fig)
        print("  ✔ 图⑤已保存: 05_error_distribution.png")

    def _plot_salary_by_education(self, df):
        """图⑥  不同学历层次的薪资预测分布箱线图"""
        edu_order = ["大专", "本科", "硕士", "博士"]
        edu_col = "educational"

        # 过滤出在预定顺序中的学历
        df_plot = df[df[edu_col].isin(edu_order)].copy()
        if df_plot.empty:
            print("  ⚠ 学历数据不足，跳过图⑥")
            return

        groups = [df_plot.loc[df_plot[edu_col] == e, "avg_salary"].values
                  for e in edu_order if e in df_plot[edu_col].values]
        labels = [e for e in edu_order if e in df_plot[edu_col].values]

        colors = ["#FA8072", "#87CEEB", "#9370DB", "#DDA0DD"]

        fig, ax = plt.subplots(figsize=(8, 6))
        bp = ax.boxplot(groups, labels=labels, patch_artist=True, widths=0.5)

        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        # 均值标记
        for i, g in enumerate(groups, 1):
            if len(g) > 0:
                ax.scatter(i, g.mean(), marker="D", color="red", zorder=5, s=60)

        # 图例
        ax.scatter([], [], marker="D", color="red", label="均值")
        ax.legend()
        ax.set_xlabel("学历层次")
        ax.set_ylabel("预测薪资 (K)")
        ax.set_title("不同学历层次的薪资预测分布")
        fig.tight_layout()
        fig.savefig(self.plot_dir / "06_salary_by_education.png", dpi=150)
        plt.close(fig)
        print("  ✔ 图⑥已保存: 06_salary_by_education.png")

    # ══════════════════════════════════════════════════════════════════════════
    # 薪资预测模型持久化
    # ══════════════════════════════════════════════════════════════════════════
    def save_model(self):
        model_data = {
            "model": self.model,
            "label_encoders": self.label_encoders,
            "feature_columns": self.feature_columns,
            "skill_columns": self.skill_columns,
        }
        joblib.dump(model_data, self.model_path)
        print(f"模型已保存到: {self.model_path}")

    def load_model(self):
        if self.model_path.exists():
            try:
                model_data = joblib.load(self.model_path)
                self.model = model_data["model"]
                self.label_encoders = model_data["label_encoders"]
                self.feature_columns = model_data["feature_columns"]
                self.skill_columns = model_data.get("skill_columns", list(self.SKILL_TAGS.keys()))
                print("模型已加载")
                return True
            except Exception as e:
                print(f"加载模型失败: {e}")
                return False
        return False


# ══════════════════════════════════════════════════════════════════════
# 岗位推荐模型
# ══════════════════════════════════════════════════════════════════════
class JobRecommender:
    """岗位推荐模型 - 使用随机森林分类"""

    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.feature_columns = ["educational", "workExperience", "address", "companyStatus"]
        self.model_path = Path(__file__).parent / "job_recommender.pkl"
        self.plot_dir = Path(__file__).parent / "plots"
        self.plot_dir.mkdir(exist_ok=True)
        self.salary_labels = ["低薪", "中薪", "高薪"]

    # ── 复用 SalaryPredictor 的解析方法 ───────────────────────────────
    def parse_salary(self, salary_str: str):
        predictor = SalaryPredictor()
        return predictor.parse_salary(salary_str)

    def extract_city(self, address: str):
        predictor = SalaryPredictor()
        return predictor.extract_city(address)

    # ── 数据准备 ──────────────────────────────────────────────────────
    def prepare_data(self):
        jobs = JobInfo.objects.all()

        data = []
        for job in jobs:
            low, high, avg_salary, issue = self.parse_salary(job.salary)
            if avg_salary is None:
                continue

            data.append({
                "title": job.title,
                "address": job.address,
                "city": self.extract_city(job.address),
                "type": job.type,
                "educational": job.educational or "学历不限",
                "workExperience": job.workExperience or "经验不限",
                "companyTitle": job.companyTitle,
                "companyStatus": job.companyStatus or "未知",
                "salary": job.salary,
                "avg_salary": avg_salary,
            })

        return pd.DataFrame(data)

    # ── 特征编码 ──────────────────────────────────────────────────────
    def encode_categorical(self, df, fit=True):
        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = "未知"
            df[col] = df[col].fillna("未知").astype(str)

            if fit:
                le = LabelEncoder()
                le.fit(df[col])
                self.label_encoders[col] = le
                df[col + "_encoded"] = le.transform(df[col])
            else:
                le = self.label_encoders.get(col)
                if le is None:
                    df[col + "_encoded"] = 0
                else:
                    known_classes = set(le.classes_)
                    df[col] = df[col].apply(
                        lambda x: x if x in known_classes else "未知"
                    )
                    df[col + "_encoded"] = le.transform(df[col])

        return df

    # ── 训练 ──────────────────────────────────────────────────────────
    def train(self, test_size=0.2, n_estimators=100):
        print("准备训练数据...")
        df = self.prepare_data()

        if len(df) < 10:
            print("数据量不足，无法训练模型")
            return False

        print(f"共有 {len(df)} 条有效数据")

        df = self.encode_categorical(df, fit=True)

        salary_bins = [0, 10, 20, float("inf")]
        df["salary_level"] = pd.cut(
            df["avg_salary"], bins=salary_bins, labels=self.salary_labels
        )

        feature_cols = [col + "_encoded" for col in self.feature_columns]
        X = df[feature_cols].values
        y = df["salary_level"].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        print("训练随机森林分类模型...")
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=15,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        y_train_pred = self.model.predict(X_train)
        y_test_pred  = self.model.predict(X_test)

        cls_metrics = {
            "train": {
                "accuracy":  accuracy_score(y_train, y_train_pred),
                "precision": precision_score(y_train, y_train_pred, average="weighted", zero_division=0),
                "recall":    recall_score(y_train, y_train_pred, average="weighted", zero_division=0),
                "f1":        f1_score(y_train, y_train_pred, average="weighted", zero_division=0),
            },
            "test": {
                "accuracy":  accuracy_score(y_test, y_test_pred),
                "precision": precision_score(y_test, y_test_pred, average="weighted", zero_division=0),
                "recall":    recall_score(y_test, y_test_pred, average="weighted", zero_division=0),
                "f1":        f1_score(y_test, y_test_pred, average="weighted", zero_division=0),
            },
        }

        print(f"训练集准确率: {cls_metrics['train']['accuracy']:.4f}")
        print(f"测试集准确率: {cls_metrics['test']['accuracy']:.4f}")

        self.save_model()

        # ── 生成可视化 ────────────────────────────────────────────────
        self._plot_cls_metrics(cls_metrics)
        self._plot_confusion_matrix(y_test, y_test_pred)

        print(f"\n✅ 所有图表已保存到: {self.plot_dir}")
        return True

    # ── 推荐 ──────────────────────────────────────────────────────────
    def recommend(self, educational, workExperience, address, top_n=10):
        if self.model is None:
            self.load_model()

        jobs = JobInfo.objects.all()
        recommendations = []

        for job in jobs:
            score = 0
            if job.educational == educational:
                score += 3
            if job.workExperience == workExperience:
                score += 3
            if address in job.address:
                score += 2

            avg_salary = 0
            if job.salary and "K" in job.salary.upper():
                match = re.search(r"(\d+)[kK]?-(\d+)[kK]?", job.salary, re.IGNORECASE)
                if match:
                    avg_salary = (int(match.group(1)) + int(match.group(2))) / 2

            recommendations.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "companyTitle": job.companyTitle,
                    "address": job.address,
                    "salary": job.salary,
                    "avg_salary": avg_salary,
                    "educational": job.educational,
                    "workExperience": job.workExperience,
                    "match_score": score,
                }
            )

        recommendations.sort(key=lambda x: x["match_score"], reverse=True)
        return recommendations[:top_n]

    # ══════════════════════════════════════════════════════════════════
    # 可视化方法
    # ══════════════════════════════════════════════════════════════════

    def _plot_cls_metrics(self, cls_metrics):
        """图③（右）  分类性能指标对比柱状图"""
        metric_names = ["准确率", "精确率", "召回率", "F1分数"]
        metric_keys  = ["accuracy", "precision", "recall", "f1"]
        train_vals = [cls_metrics["train"][k] for k in metric_keys]
        test_vals  = [cls_metrics["test"][k]  for k in metric_keys]

        x = np.arange(len(metric_names))
        width = 0.35

        fig, ax = plt.subplots(figsize=(6, 5))
        b1 = ax.bar(x - width / 2, train_vals, width, label="训练集", color="#55A868")
        b2 = ax.bar(x + width / 2, test_vals,  width, label="测试集",  color="#C44E52")

        for bar in list(b1) + list(b2):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                    f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=8)

        ax.set_xticks(x)
        ax.set_xticklabels(metric_names)
        ax.set_ylim(0.7, 1.02)
        ax.set_ylabel("指标值")
        ax.set_title("随机森林分类 - 性能指标")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.plot_dir / "03_classification_metrics.png", dpi=150)
        plt.close(fig)
        print("  ✔ 图③（右）已保存: 03_classification_metrics.png")

    def _plot_confusion_matrix(self, y_true, y_pred):
        """图④  混淆矩阵热力图"""
        present_labels = sorted(set(y_true) | set(y_pred),
                                key=lambda x: self.salary_labels.index(x)
                                if x in self.salary_labels else 99)
        cm = confusion_matrix(y_true, y_pred, labels=present_labels)

        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=present_labels, yticklabels=present_labels,
            linewidths=0.5, ax=ax,
        )
        ax.set_xlabel("预测类别")
        ax.set_ylabel("实际类别")
        ax.set_title("随机森林分类 - 混淆矩阵")
        fig.tight_layout()
        fig.savefig(self.plot_dir / "04_confusion_matrix.png", dpi=150)
        plt.close(fig)
        print("  ✔ 图④已保存: 04_confusion_matrix.png")

    # ══════════════════════════════════════════════════════════════════════════
    # 岗位推荐模型持久化
    # ══════════════════════════════════════════════════════════════════════════
    def save_model(self):
        model_data = {
            "model": self.model,
            "label_encoders": self.label_encoders,
            "feature_columns": self.feature_columns,
        }
        joblib.dump(model_data, self.model_path)
        print(f"模型已保存到: {self.model_path}")

    def load_model(self):
        if self.model_path.exists():
            try:
                model_data = joblib.load(self.model_path)
                self.model = model_data["model"]
                self.label_encoders = model_data["label_encoders"]
                self.feature_columns = model_data["feature_columns"]
                print("模型已加载")
                return True
            except Exception as e:
                print(f"加载模型失败: {e}")
                return False
        return False


# ══════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("测试薪资预测模型")
    print("=" * 50)

    predictor = SalaryPredictor()

    if not predictor.model_path.exists():
        print("模型不存在，开始训练...")
        predictor.train()
    else:
        predictor.load_model()

    # 新特征: [educational, workExperience, companyPeople, companyStatus, type, city]
    test_features = ["本科", "3-5年", "1000-9999人", "B轮", "技术", "北京"]
    # 测试技能标签
    test_skills = {"Python": 1, "Java": 0, "Go": 0, "前端": 0, "数据库": 0,
                  "大数据": 0, "算法": 0, "测试": 0, "Linux": 0, "架构": 0}
    pred = predictor.predict(test_features, test_skills)
    print(f"预测薪资: {pred}K")

    print("\n" + "=" * 50)
    print("测试岗位推荐模型")
    print("=" * 50)

    recommender = JobRecommender()

    if not recommender.model_path.exists():
        print("模型不存在，开始训练...")
        recommender.train()
    else:
        recommender.load_model()

    recs = recommender.recommend("本科", "3-5年", "北京", top_n=5)
    print(f"推荐岗位数: {len(recs)}")
    for rec in recs:
        print(f"  - {rec['title']} @ {rec['companyTitle']} ({rec['salary']})")