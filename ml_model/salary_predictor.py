#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
机器学习模块 - 薪资预测和岗位推荐
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

# Django settings
import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
django.setup()

from myApp.models import JobInfo


class SalaryPredictor:
    """薪资预测模型 - 使用随机森林回归"""

    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.feature_columns = [
            "educational",
            "workExperience",
            "companyPeople",
            "address",
        ]
        self.target_column = "avg_salary"
        self.model_path = Path(__file__).parent / "salary_model.pkl"

    def prepare_data(self):
        """准备训练数据"""
        jobs = JobInfo.objects.all()

        data = []
        for job in jobs:
            # 解析薪资
            salary_str = job.salary
            if not salary_str or "K" not in salary_str.upper():
                continue

            # 提取薪资数值
            match = re.search(r"(\d+)[kK]?-(\d+)[kK]?", salary_str, re.IGNORECASE)
            if match:
                low = int(match.group(1))
                high = int(match.group(2))
                avg_salary = (low + high) / 2
            else:
                continue

            data.append(
                {
                    "title": job.title,
                    "address": job.address,
                    "type": job.type,
                    "educational": job.educational or "学历不限",
                    "workExperience": job.workExperience or "经验不限",
                    "companyNature": job.companyNature or "未知",
                    "companyPeople": job.companyPeople or "未知",
                    "avg_salary": avg_salary,
                }
            )

        return pd.DataFrame(data)

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
                    # 处理未见过的类别
                    known_classes = set(le.classes_)
                    df[col] = df[col].apply(
                        lambda x: x if x in known_classes else "未知"
                    )
                    df[col + "_encoded"] = le.transform(df[col])

        return df

    def train(self, test_size=0.2, n_estimators=100, max_depth=15):
        """训练模型"""
        print("准备训练数据...")
        df = self.prepare_data()

        if len(df) < 10:
            print("数据量不足，无法训练模型")
            return False

        print(f"共有 {len(df)} 条有效数据")

        # 编码分类特征
        df = self.encode_categorical(df, fit=True)

        # 准备特征和标签
        feature_cols = [col + "_encoded" for col in self.feature_columns]
        X = df[feature_cols].values
        y = df[self.target_column].values

        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # 训练随机森林回归模型
        print("训练随机森林回归模型...")
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        # 评估模型
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        print(f"训练集 R2 分数: {train_score:.4f}")
        print(f"测试集 R2 分数: {test_score:.4f}")

        # 保存模型
        self.save_model()

        return True

    def predict(self, features):
        """
        预测薪资

        Args:
            features: [educational, workExperience, companyPeople, address]

        Returns:
            预测的薪资（单位：K）
        """
        if self.model is None:
            self.load_model()

        if self.model is None:
            # 模型不存在，返回默认值
            return 15.0

        # 确保特征顺序正确
        feature_dict = dict(zip(self.feature_columns, features))
        df = pd.DataFrame([feature_dict])
        df = self.encode_categorical(df, fit=False)

        feature_cols = [col + "_encoded" for col in self.feature_columns]
        X = df[feature_cols].values

        prediction = self.model.predict(X)[0]

        return round(float(prediction), 1)

    def save_model(self):
        """保存模型"""
        model_data = {
            "model": self.model,
            "label_encoders": self.label_encoders,
            "feature_columns": self.feature_columns,
        }
        joblib.dump(model_data, self.model_path)
        print(f"模型已保存到: {self.model_path}")

    def load_model(self):
        """加载模型"""
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


class JobRecommender:
    """岗位推荐模型 - 使用K近邻分类"""

    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.feature_columns = ["educational", "workExperience", "address"]
        self.model_path = Path(__file__).parent / "job_recommender.pkl"

    def prepare_data(self):
        """准备训练数据"""
        jobs = JobInfo.objects.all()

        data = []
        for job in jobs:
            if not job.salary or "K" not in job.salary.upper():
                continue

            # 提取薪资数值，计算平均值
            match = re.search(r"(\d+)[kK]?-(\d+)[kK]?", job.salary, re.IGNORECASE)
            if match:
                low = int(match.group(1))
                high = int(match.group(2))
                avg_salary = (low + high) / 2
            else:
                continue

            data.append(
                {
                    "title": job.title,
                    "address": job.address,
                    "type": job.type,
                    "educational": job.educational or "学历不限",
                    "workExperience": job.workExperience or "经验不限",
                    "companyTitle": job.companyTitle,
                    "salary": job.salary,
                    "avg_salary": avg_salary,
                }
            )

        return pd.DataFrame(data)

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
                    df[col] = df[col].apply(
                        lambda x: x if x in known_classes else "未知"
                    )
                    df[col + "_encoded"] = le.transform(df[col])

        return df

    def train(self, test_size=0.2, n_neighbors=5):
        """训练模型"""
        print("准备训练数据...")
        df = self.prepare_data()

        if len(df) < 10:
            print("数据量不足，无法训练模型")
            return False

        print(f"共有 {len(df)} 条有效数据")

        # 编码分类特征
        df = self.encode_categorical(df, fit=True)

        # 将薪资分为高中低三档作为分类标签
        salary_bins = [0, 10, 20, float("inf")]
        salary_labels = ["低薪", "中薪", "高薪"]
        df["salary_level"] = pd.cut(
            df["avg_salary"], bins=salary_bins, labels=salary_labels
        )

        # 准备特征和标签
        feature_cols = [col + "_encoded" for col in self.feature_columns]
        X = df[feature_cols].values
        y = df["salary_level"].values

        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # 训练KNN分类模型
        print("训练K近邻分类模型...")
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        # 评估模型
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        print(f"训练集准确率: {train_score:.4f}")
        print(f"测试集准确率: {test_score:.4f}")

        # 保存模型
        self.save_model()

        return True

    def recommend(self, educational, workExperience, address, top_n=10):
        """
        推荐岗位

        Args:
            educational: 学历
            workExperience: 工作经验
            address: 意向城市
            top_n: 返回推荐数量

        Returns:
            推荐的岗位列表
        """
        if self.model is None:
            self.load_model()

        # 获取所有岗位
        jobs = JobInfo.objects.all()

        recommendations = []
        for job in jobs:
            # 计算匹配度（简单实现）
            score = 0

            if job.educational == educational:
                score += 3
            if job.workExperience == workExperience:
                score += 3
            if address in job.address:
                score += 2

            # 解析薪资
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

        # 按匹配度排序
        recommendations.sort(key=lambda x: x["match_score"], reverse=True)

        return recommendations[:top_n]

    def save_model(self):
        """保存模型"""
        model_data = {
            "model": self.model,
            "label_encoders": self.label_encoders,
            "feature_columns": self.feature_columns,
        }
        joblib.dump(model_data, self.model_path)
        print(f"模型已保存到: {self.model_path}")

    def load_model(self):
        """加载模型"""
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


# 导入需要的模块
import re

if __name__ == "__main__":
    # 测试薪资预测模型
    print("=" * 50)
    print("测试薪资预测模型")
    print("=" * 50)

    predictor = SalaryPredictor()

    # 检查是否有已训练的模型
    if not predictor.model_path.exists():
        print("模型不存在，开始训练...")
        predictor.train()
    else:
        predictor.load_model()

    # 测试预测
    test_features = ["本科", "3-5年", "1000-9999人", "北京"]
    pred = predictor.predict(test_features)
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

    # 测试推荐
    recs = recommender.recommend("本科", "3-5年", "北京", top_n=5)
    print(f"推荐岗位数: {len(recs)}")
    for rec in recs:
        print(f"  - {rec['title']} @ {rec['companyTitle']} ({rec['salary']})")
