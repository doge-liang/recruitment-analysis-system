#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试浏览器能否正常打开BOSS直聘"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def test_browser():
    print("启动 Chrome 浏览器...")

    chrome_options = Options()
    # Windows Chrome 路径
    chrome_options.binary_location = (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )
    # 注意：这里没有 headless！可以看到浏览器窗口

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    print("打开 BOSS直聘 首页...")
    driver.get("https://www.zhipin.com/")

    print(f"当前 URL: {driver.current_url}")
    print(f"页面标题: {driver.title}")

    if "login" in driver.current_url or "security" in driver.current_url:
        print("⚠️ 被重定向到登录页，说明BOSS检测到自动化工具")
    elif "zhipin" in driver.current_url:
        print("✅ 页面加载成功！")

    print("\n按回车键关闭浏览器...")
    input()
    driver.quit()
    print("完成。")


if __name__ == "__main__":
    test_browser()
