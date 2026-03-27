#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试爬取BOSS直聘职位数据"""

import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def test_crawl():
    print("启动 Chrome 浏览器...")

    chrome_options = Options()
    chrome_options.binary_location = (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )
    # 有头模式，可以看到浏览器操作
    # chrome_options.add_argument('--headless')  # 注释掉，可以看到浏览器

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    try:
        # 直接访问大数据岗位搜索页面
        print("打开 BOSS直聘 大数据岗位搜索页...")
        url = "https://www.zhipin.com/web/geek/job?query=大数据&city=101280600"
        driver.get(url)

        print(f"当前 URL: {driver.current_url}")
        print(f"页面标题: {driver.title}")

        # 等待页面加载
        time.sleep(3)

        # 检查是否被拦截
        if "login" in driver.current_url or "security" in driver.current_url:
            print("⚠️ 被重定向到登录页，爬虫被拦截")
            return

        # 尝试找到职位列表
        print("\n查找职位列表...")

        # 等待职位卡片加载
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "job-card-box"))
            )
            print("✅ 职位列表已加载")
        except Exception as e:
            print(f"职位列表未找到: {e}")

        # 获取前5个职位
        job_cards = driver.find_elements(By.CLASS_NAME, "job-card-box")[:5]

        print(f"\n找到 {len(job_cards)} 个职位:")
        for i, card in enumerate(job_cards, 1):
            try:
                title = card.find_element(By.CLASS_NAME, "job-name").text
                salary = card.find_element(By.CLASS_NAME, "salary").text
                company = card.find_element(By.CLASS_NAME, "company-name").text
                print(f"{i}. {title} | {salary} | {company}")
            except Exception as e:
                print(f"{i}. 解析失败: {e}")

        print("\n按回车键关闭浏览器...")
        input()

    finally:
        driver.quit()
        print("完成。")


if __name__ == "__main__":
    test_crawl()
