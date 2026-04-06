#!/usr/bin/env python3
"""
51job分页机制诊断工具

这个脚本用于诊断前程无忧(51job)网站的分页机制，帮助发现：
1. 真实的分页参数名（page/p/pn/pageNo等）
2. 分页是通过URL参数还是AJAX请求实现的
3. 是否需要点击分页按钮
4. 分页验证失败的常见原因

使用方法：
    python diagnose_pagination.py --keyword 大数据 --show-browser

建议步骤：
1. 先运行此脚本，观察浏览器中的分页行为
2. 查看控制台输出的诊断信息
3. 根据诊断结果调整爬虫配置
"""

import argparse
import json
import time
from urllib.parse import parse_qs, urlparse


def diagnose_pagination(keyword: str = "大数据", show_browser: bool = True):
    """
    诊断51job分页机制

    Args:
        keyword: 搜索关键词
        show_browser: 是否显示浏览器窗口（建议True以便观察）
    """
    print("=" * 70)
    print("51job分页机制诊断工具")
    print("=" * 70)
    print()
    print(f"搜索关键词: {keyword}")
    print(f"显示浏览器: {'是' if show_browser else '否'}")
    print()

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError as e:
        print(f"[错误] 缺少必要的依赖: {e}")
        print("请安装依赖: pip install selenium webdriver-manager")
        return

    # 设置Chrome选项
    chrome_options = Options()
    if not show_browser:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    driver = None

    try:
        print("[1/6] 启动浏览器...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 15)

        base_url = "https://we.51job.com/pc/search"

        # 测试1: 访问第一页，记录基准数据
        print("\n[2/6] 测试第1页...")
        url_page1 = f"{base_url}?keyword={keyword}"
        print(f"  访问URL: {url_page1}")
        driver.get(url_page1)
        time.sleep(5)  # 等待页面加载

        # 滚动加载
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 400)")
            time.sleep(0.5)

        # 记录第1页数据
        current_url_1 = driver.current_url
        print(f"  当前URL: {current_url_1}")

        # 获取职位列表
        try:
            job_cards_1 = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "joblist-item-job"))
            )
        except:
            job_cards_1 = driver.find_elements(
                By.CSS_SELECTOR, "[class*='joblist-item']"
            )

        print(f"  找到 {len(job_cards_1)} 个职位卡片")

        # 获取第一条职位信息
        first_job_1 = None
        if job_cards_1:
            try:
                title_elem = job_cards_1[0].find_element(By.CLASS_NAME, "jname")
                company_elem = job_cards_1[0].find_element(By.CLASS_NAME, "cname")
                first_job_1 = {
                    "title": title_elem.text.strip(),
                    "company": company_elem.text.strip(),
                }
                print(
                    f"  第1页第1条: {first_job_1['title']} @ {first_job_1['company']}"
                )
            except Exception as e:
                print(f"  无法获取第1页职位信息: {e}")

        # 测试2: 尝试URL参数 page=2
        print("\n[3/6] 测试URL参数 page=2...")
        url_page2_param = f"{base_url}?keyword={keyword}&page=2"
        print(f"  访问URL: {url_page2_param}")
        driver.get(url_page2_param)
        time.sleep(5)

        # 滚动加载
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 400)")
            time.sleep(0.5)

        current_url_2 = driver.current_url
        print(f"  当前URL: {current_url_2}")

        # 检查page参数是否被保留
        parsed_url_2 = urlparse(current_url_2)
        query_params_2 = parse_qs(parsed_url_2.query)
        if "page" in query_params_2:
            print(f"  URL参数 'page' 值为: {query_params_2['page'][0]}")
        else:
            print("  [警告] URL参数 'page' 不存在！")

        # 获取第2页数据
        try:
            job_cards_2 = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "joblist-item-job"))
            )
        except:
            job_cards_2 = driver.find_elements(
                By.CSS_SELECTOR, "[class*='joblist-item']"
            )

        print(f"  找到 {len(job_cards_2)} 个职位卡片")

        # 获取第2页第一条职位
        first_job_2 = None
        if job_cards_2:
            try:
                title_elem = job_cards_2[0].find_element(By.CLASS_NAME, "jname")
                company_elem = job_cards_2[0].find_element(By.CLASS_NAME, "cname")
                first_job_2 = {
                    "title": title_elem.text.strip(),
                    "company": company_elem.text.strip(),
                }
                print(
                    f"  第2页第1条: {first_job_2['title']} @ {first_job_2['company']}"
                )
            except Exception as e:
                print(f"  无法获取第2页职位信息: {e}")

        # 比较第1页和第2页数据
        print("\n[4/6] 分析分页效果...")
        if first_job_1 and first_job_2:
            if first_job_1 == first_job_2:
                print("  [❌ 失败] 第1页和第2页数据完全相同！")
                print("  说明: URL参数 'page=2' 无效，数据仍然是第1页")
            else:
                print("  [✅ 成功] 第1页和第2页数据不同！")
                print("  说明: URL参数 'page=2' 有效")

        # 测试3: 尝试点击分页按钮
        print("\n[5/6] 测试点击分页按钮...")

        # 回到第1页
        driver.get(url_page1)
        time.sleep(3)

        # 尝试点击第2页按钮
        pagination_clicked = False
        pagination_selectors = [
            '//div[contains(@class,"page")]//a[text()="2"]',
            '//div[contains(@class,"pagination")]//a[text()="2"]',
            '//a[@data-page="2"]',
            '//li[contains(@class,"page")]//a[text()="2"]',
        ]

        for selector in pagination_selectors:
            try:
                page2_button = driver.find_element(By.XPATH, selector)
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", page2_button
                )
                time.sleep(1)
                page2_button.click()
                pagination_clicked = True
                print(f"  成功点击第2页按钮: {selector}")
                break
            except:
                continue

        if not pagination_clicked:
            print("  [警告] 未找到分页按钮，可能需要滚动到页面底部")
            # 尝试滚动到底部查找分页
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            for selector in pagination_selectors:
                try:
                    page2_button = driver.find_element(By.XPATH, selector)
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", page2_button
                    )
                    time.sleep(1)
                    page2_button.click()
                    pagination_clicked = True
                    print(f"  成功点击第2页按钮: {selector}")
                    break
                except:
                    continue

        if pagination_clicked:
            time.sleep(5)  # 等待页面加载

            # 滚动加载
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 400)")
                time.sleep(0.5)

            # 获取点击后的数据
            try:
                job_cards_click = wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CLASS_NAME, "joblist-item-job")
                    )
                )
            except:
                job_cards_click = driver.find_elements(
                    By.CSS_SELECTOR, "[class*='joblist-item']"
                )

            print(f"  点击后找到 {len(job_cards_click)} 个职位卡片")

            if job_cards_click:
                try:
                    title_elem = job_cards_click[0].find_element(By.CLASS_NAME, "jname")
                    company_elem = job_cards_click[0].find_element(
                        By.CLASS_NAME, "cname"
                    )
                    first_job_click = {
                        "title": title_elem.text.strip(),
                        "company": company_elem.text.strip(),
                    }
                    print(
                        f"  点击后第1条: {first_job_click['title']} @ {first_job_click['company']}"
                    )

                    if first_job_1 == first_job_click:
                        print("  [❌ 失败] 点击后数据与第1页相同！")
                    else:
                        print("  [✅ 成功] 点击后数据与第1页不同！")
                        print("  说明: 需要使用点击分页按钮的方式翻页")
                except Exception as e:
                    print(f"  无法获取点击后的职位信息: {e}")
        else:
            print("  [警告] 未能点击分页按钮")

        # 测试4: 检查网络请求
        print("\n[6/6] 检查浏览器日志（查看AJAX请求）...")
        try:
            logs = driver.get_log("performance")
            ajax_requests = []
            for entry in logs:
                try:
                    log = json.loads(entry["message"])["message"]
                    if log.get("method") in ["Network.requestWillBeSent"]:
                        url = log.get("params", {}).get("request", {}).get("url", "")
                        if "search" in url or "api" in url or "ajax" in url:
                            ajax_requests.append(url)
                except:
                    continue

            if ajax_requests:
                print(f"  发现 {len(ajax_requests)} 个相关网络请求:")
                for url in ajax_requests[:5]:  # 只显示前5个
                    print(f"    - {url}")
            else:
                print("  未发现明显的AJAX请求")
        except Exception as e:
            print(f"  无法获取浏览器日志: {e}")

        # 最终诊断报告
        print("\n" + "=" * 70)
        print("诊断报告")
        print("=" * 70)

        if first_job_1 and first_job_2 and first_job_1 != first_job_2:
            print("✅ URL参数 'page' 有效，可以使用URL分页")
        else:
            print("❌ URL参数 'page' 无效，需要使用点击分页按钮的方式")

        if pagination_clicked:
            print("✅ 分页按钮可以点击，可以使用点击翻页方案")
        else:
            print("❌ 未找到分页按钮，可能需要：")
            print("   - 滚动到页面底部查看更多内容")
            print("   - 使用无限滚动而非分页")
            print("   - 检查页面是否使用了特殊的分页组件")

        print("\n建议:")
        print("1. 如果URL参数有效，使用原有的crawl_job_list()方法")
        print(
            "2. 如果URL参数无效但点击有效，使用crawl_page_with_click_pagination()方法"
        )
        print("3. 在爬虫中添加分页验证逻辑，检测是否重复获取同一页数据")
        print()

    except Exception as e:
        print(f"\n[错误] 诊断过程中出错: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if driver:
            print("\n关闭浏览器...")
            driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="51job分页机制诊断工具")
    parser.add_argument("--keyword", default="大数据", help="搜索关键词")
    parser.add_argument(
        "--show-browser",
        action="store_true",
        default=True,
        help="显示浏览器窗口（建议开启以便观察）",
    )
    parser.add_argument(
        "--headless", action="store_true", help="使用无头模式（不显示浏览器窗口）"
    )

    args = parser.parse_args()

    show_browser = not args.headless
    diagnose_pagination(keyword=args.keyword, show_browser=show_browser)
