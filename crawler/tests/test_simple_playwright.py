"""
Simple Playwright test for crawler admin page
"""

import pytest
from playwright.sync_api import sync_playwright


def test_admin_page_loads():
    """测试管理页面加载"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 访问登录页
        page.goto("http://localhost:8000/myApp/login/")

        # 检查页面标题
        assert "登录" in page.title() or "Login" in page.title()

        browser.close()


def test_admin_page_elements():
    """测试页面元素存在"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://localhost:8000/myApp/admin/crawl/")

        # 等待页面加载
        page.wait_for_load_state("networkidle")

        # 检查关键元素
        assert page.locator("h1").count() > 0

        browser.close()


if __name__ == "__main__":
    print("测试管理页面加载...")
    test_admin_page_loads()
    print("✓ 页面加载测试通过")

    print("\n测试页面元素...")
    test_admin_page_elements()
    print("✓ 元素测试通过")

    print("\n所有测试完成！")
