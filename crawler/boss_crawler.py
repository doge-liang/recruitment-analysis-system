#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BOSS直聘爬虫模块
使用Selenium自动采集大数据相关岗位的招聘信息
"""

import os
import re
import time
import random
import pandas as pd
from datetime import datetime
from pathlib import Path

# Django settings
import django
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
django.setup()

from myApp.models import JobInfo
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class BOSSCrawler:
    """BOSS直聘爬虫类"""

    def __init__(self):
        self.base_url = "https://www.zhipin.com/web/geek/job"
        self.data = []
        self.chrome_options = Options()

        # 反检测设置
        self.chrome_options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )
        self.chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        self.chrome_options.add_experimental_option("useAutomationExtension", False)
        self.chrome_options.add_argument("--headless")  # 无头模式
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    def create_driver(self):
        """创建浏览器驱动"""
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=self.chrome_options)

        # 反检测脚本
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
            },
        )

        return driver

    def parse_salary(self, salary_text):
        """解析薪资文本"""
        if not salary_text:
            return "薪资面议", "未知"

        # 匹配如 "15K-25K·13薪" 格式
        match = re.search(r"(\d+)K?-(\d+)K", salary_text)
        if match:
            salary_range = f"{match.group(1)}K-{match.group(2)}K"
        else:
            salary_range = salary_text

        # 匹配年终奖
        month_match = re.search(r"(\d+)薪", salary_text)
        salary_month = month_match.group(1) + "薪" if month_match else "12薪"

        return salary_range, salary_month

    def parse_company_size(self, size_text):
        """解析公司规模"""
        if not size_text:
            return "未知"

        size_map = {
            "0-99人": "0-99人",
            "100-499人": "100-499人",
            "500-999人": "500-999人",
            "1000-9999人": "1000-9999人",
            "10000人以上": "10000人以上",
        }

        for key, value in size_map.items():
            if key in size_text:
                return value
        return size_text

    def crawl_job_list(self, keyword="大数据", city="全国", page=1):
        """爬取职位列表"""
        driver = None
        try:
            driver = self.create_driver()
            wait = WebDriverWait(driver, 10)

            # 构建URL
            url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city}&page={page}"
            driver.get(url)

            time.sleep(random.uniform(2, 5))

            # 等待页面加载
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "job-list-box")))

            # 获取所有职位卡片
            job_cards = driver.find_elements(By.CLASS_NAME, "job-card-box")

            jobs = []
            for card in job_cards:
                try:
                    # 提取基本信息
                    job_info = {}

                    # 职位名称
                    title_elem = card.find_element(By.CLASS_NAME, "job-name")
                    job_info["title"] = title_elem.text if title_elem else ""

                    # 薪资
                    salary_elem = card.find_element(By.CLASS_NAME, "salary")
                    salary_text = salary_elem.text if salary_elem else ""
                    job_info["salary"], job_info["salaryMonth"] = self.parse_salary(
                        salary_text
                    )

                    # 公司名称
                    company_elem = card.find_element(By.CLASS_NAME, "company-name")
                    job_info["companyTitle"] = company_elem.text if company_elem else ""

                    # 学历和工作经验
                    job_tags = card.find_elements(By.CLASS_NAME, "tag-list")
                    if job_tags:
                        tags_text = job_tags[0].text
                        # 解析标签
                        if (
                            "大专" in tags_text
                            or "本科" in tags_text
                            or "硕士" in tags_text
                            or "博士" in tags_text
                        ):
                            for edu in ["博士", "硕士", "本科", "大专", "学历不限"]:
                                if edu in tags_text:
                                    job_info["educational"] = edu
                                    break
                        else:
                            job_info["educational"] = "学历不限"

                        if "年" in tags_text:
                            exp_match = re.search(r"(\d+)-?(\d*)年", tags_text)
                            if exp_match:
                                if exp_match.group(2):
                                    job_info["workExperience"] = (
                                        f"{exp_match.group(1)}-{exp_match.group(2)}年"
                                    )
                                else:
                                    job_info["workExperience"] = (
                                        f"{exp_match.group(1)}年以上"
                                    )
                            else:
                                job_info["workExperience"] = "经验不限"
                        else:
                            job_info["workExperience"] = "经验不限"
                    else:
                        job_info["educational"] = "学历不限"
                        job_info["workExperience"] = "经验不限"

                    # 城市
                    address_elem = card.find_element(By.CLASS_NAME, "job-area")
                    job_info["address"] = address_elem.text if address_elem else ""

                    # 公司性质
                    try:
                        company_tags = card.find_elements(
                            By.CLASS_NAME, "company-tag-list"
                        )
                        if company_tags:
                            job_info["companyNature"] = company_tags[0].text
                        else:
                            job_info["companyNature"] = "未知"
                    except:
                        job_info["companyNature"] = "未知"

                    # 岗位类型
                    job_info["type"] = keyword

                    # 其他字段初始化
                    job_info["workTag"] = ""
                    job_info["companyTags"] = ""
                    job_info["hrWork"] = ""
                    job_info["hrName"] = ""
                    job_info["pratice"] = False
                    job_info["companyAvatar"] = ""
                    job_info["companyStatus"] = ""
                    job_info["companyPeople"] = "未知"
                    job_info["detailUrl"] = ""
                    job_info["companyUrl"] = ""
                    job_info["dist"] = ""

                    jobs.append(job_info)

                except Exception as e:
                    print(f"解析职位卡片时出错: {e}")
                    continue

            return jobs

        except Exception as e:
            print(f"爬取页面时出错: {e}")
            return []

        finally:
            if driver:
                driver.quit()

    def crawl_single_job_detail(self, job_element):
        """爬取单个职位的详细信息"""
        try:
            # 点击进入详情页
            job_element.click()
            time.sleep(random.uniform(1, 2))

            # 切换到新窗口
            windows = driver.window_handles
            if len(windows) > 1:
                driver.switch_to.window(windows[-1])

                # 等待详情加载
                wait = WebDriverWait(driver, 10)
                wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "job-detail"))
                )

                # 提取详情
                # ... 详情提取逻辑

                # 关闭详情页
                driver.close()
                driver.switch_to.window(windows[0])

        except Exception as e:
            print(f"爬取详情时出错: {e}")


def save_to_database(jobs):
    """保存数据到数据库"""
    saved_count = 0
    for job_data in jobs:
        try:
            # 检查是否已存在
            exists = JobInfo.objects.filter(
                title=job_data.get("title"),
                companyTitle=job_data.get("companyTitle"),
                address=job_data.get("address"),
            ).exists()

            if not exists:
                JobInfo.objects.create(**job_data)
                saved_count += 1

        except Exception as e:
            print(f"保存数据时出错: {e}")
            continue

    return saved_count


def run_crawler(keyword="大数据", city="101280600", pages=5):
    """
    运行爬虫主函数

    Args:
        keyword: 搜索关键词
        city: 城市代码（如'101280600'表示深圳）
        pages: 爬取页数
    """
    crawler = BOSSCrawler()
    all_jobs = []

    print(f"开始爬取关键词: {keyword}, 城市代码: {city}")

    for page in range(1, pages + 1):
        print(f"正在爬取第 {page}/{pages} 页...")

        jobs = crawler.crawl_job_list(keyword=keyword, city=city, page=page)

        if jobs:
            all_jobs.extend(jobs)
            print(f"第 {page} 页获取到 {len(jobs)} 条职位信息")
        else:
            print(f"第 {page} 页无数据，可能已到达末尾或被反爬")
            break

        # 随机延时，避免请求过快
        time.sleep(random.uniform(3, 7))

    print(f"\n总共获取到 {len(all_jobs)} 条职位信息")

    # 保存到数据库
    if all_jobs:
        saved = save_to_database(all_jobs)
        print(f"成功保存 {saved} 条新记录到数据库")

    return all_jobs


if __name__ == "__main__":
    # 测试爬虫
    run_crawler(keyword="大数据", city="101280600", pages=2)
