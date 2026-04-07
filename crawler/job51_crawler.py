#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
前程无忧爬虫模块

核心架构：
- Job51Crawler: 主爬虫类
  - run_crawler_with_checkpoint(): 断点续传主入口
  - _run_crawl_session(): 共享会话运行器
  - _parse_job_card(): 单条职位解析
  - _parse_current_page(): 整页解析
  - _click_next_page(): 分页点击
  - _open_search_page(): 打开搜索页
"""

import argparse
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Django settings
import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")
django.setup()

from django.db import transaction
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from myApp.models import JobInfo

# 导入检查点管理器
_crawler_dir = Path(__file__).resolve().parent
if str(_crawler_dir) not in sys.path:
    sys.path.insert(0, str(_crawler_dir))

try:
    from checkpoint_manager import CheckpointManager
except ImportError as e:
    print(f"[错误] 无法导入 checkpoint_manager: {e}")
    raise

try:
    from run_store import CrawlRunStore, build_crawler_logger
except ImportError as e:
    print(f"[错误] 无法导入 run_store: {e}")
    raise


class AdaptiveRateLimiter:
    """自适应速率限制器"""

    def __init__(
        self,
        base_delay: float = 3.0,
        max_delay: float = 30.0,
        success_cooldown: float = 0.9,
        failure_boost: float = 1.5,
    ):
        self.base_delay = base_delay
        self.current_delay = base_delay
        self.max_delay = max_delay
        self.success_cooldown = success_cooldown
        self.failure_boost = failure_boost
        self.consecutive_failures = 0

    def wait(self) -> None:
        """等待一段时间（带随机抖动）"""
        jitter = random.uniform(0.8, 1.5)
        actual_delay = self.current_delay * jitter
        time.sleep(actual_delay)

    def report_success(self) -> None:
        """报告成功，减少延迟"""
        self.consecutive_failures = 0
        self.current_delay = max(
            self.base_delay, self.current_delay * self.success_cooldown
        )

    def report_failure(self) -> None:
        """报告失败，增加延迟"""
        self.consecutive_failures += 1
        self.current_delay = min(
            self.max_delay, self.current_delay * self.failure_boost
        )
        if self.consecutive_failures >= 3:
            extra_wait = min(60, 10 * self.consecutive_failures)
            print(f"  连续失败{self.consecutive_failures}次，额外等待{extra_wait}秒...")
            time.sleep(extra_wait)


class Job51Crawler:
    """前程无忧爬虫类"""

    def __init__(
        self,
        checkpoint_file: str = "crawler_checkpoint.json",
        headless: bool = True,
        run_store: Optional[CrawlRunStore] = None,
        run_id: Optional[str] = None,
    ):
        self.base_url = "https://we.51job.com/pc/search"
        self.chrome_options = Options()
        self._setup_anti_detection(headless=headless)
        self.checkpoint_manager = CheckpointManager(checkpoint_file)
        self.rate_limiter = AdaptiveRateLimiter(base_delay=3.0, max_delay=30.0)
        self.stats = {
            "pages_processed": 0,
            "records_collected": 0,
            "records_saved": 0,
            "errors": 0,
            "start_time": None,
        }
        self.run_store = run_store
        self.run_id = run_id
        self.logger = self._setup_logger()

    def _setup_anti_detection(self, headless=True):
        """配置反检测选项"""
        self.chrome_options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )
        self.chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        self.chrome_options.add_experimental_option("useAutomationExtension", False)

        if headless:
            self.chrome_options.add_argument("--headless")

        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--disable-blink-features")
        self.chrome_options.add_argument("--disable-web-security")
        self.chrome_options.add_argument(
            "--disable-features=IsolateOrigins,site-per-process"
        )
        self.chrome_options.add_argument("--allow-running-insecure-content")
        self.chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        if self.run_store and self.run_id:
            return build_crawler_logger(self.run_store, self.run_id)
        else:
            logger = logging.getLogger(f"crawler.standalone")
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setLevel(logging.INFO)
                formatter = logging.Formatter(
                    "[%(asctime)s] %(levelname)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            return logger

    def _log(self, message: str, level: str = "info"):
        """统一的日志记录方法"""
        if level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        elif level == "debug":
            self.logger.debug(message)

    def _update_status(self, **kwargs):
        """更新运行状态到文件"""
        if self.run_store and self.run_id:
            self.run_store.update_status(self.run_id, **kwargs)

    def _mark_error(self, error: str):
        """标记运行为错误状态"""
        if self.run_store and self.run_id:
            self.run_store.mark_error(self.run_id, error)

    def _mark_completed(self):
        """标记运行为完成状态"""
        if self.run_store and self.run_id:
            self.run_store.mark_completed(
                self.run_id,
                current_page=self.stats["pages_processed"],
                raw_count=self.stats["records_collected"],
                saved_count=self.stats["records_saved"],
                error_count=self.stats["errors"],
            )

    def create_driver(self):
        """创建浏览器驱动"""
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=self.chrome_options)
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

    # ==================== 解析方法 ====================

    def parse_salary(self, salary_text: str) -> Tuple[str, str]:
        """解析薪资文本，返回(薪资范围, 薪月数)"""
        if not salary_text or salary_text == "薪资面议":
            return "薪资面议", "12薪"

        salary_processed = salary_text.replace("万", "")
        match = re.search(r"(\d+\.?\d*)-?(\d+\.?\d*)?", salary_processed)

        if match:
            min_sal = float(match.group(1))
            max_sal = float(match.group(2)) if match.group(2) else min_sal

            if min_sal < 100:
                min_sal = int(min_sal * 10)
                max_sal = int(max_sal * 10)
            else:
                min_sal = int(min_sal)
                max_sal = int(max_sal)

            salary_range = f"{min_sal}K-{max_sal}K"
        else:
            salary_range = salary_text

        month_match = re.search(r"(\d+)薪", salary_text)
        salary_month = month_match.group(1) + "薪" if month_match else "12薪"

        return salary_range, salary_month

    def parse_company_info(self, info_text: str) -> Tuple[str, str, str]:
        """解析公司信息文本，返回(公司性质, 公司规模, 公司状态)"""
        company_nature = "未知"
        company_people = "未知"
        company_status = "未知"

        if not info_text:
            return company_nature, company_people, company_status

        nature_keywords = [
            "民营",
            "国企",
            "外资",
            "合资",
            "上市公司",
            "事业单位",
            "政府机关",
        ]
        size_patterns = [r"\d+-\d+人", r"\d+人以上", r"少于\d+人"]

        parts = info_text.split("|")

        for part in parts:
            part = part.strip()
            for keyword in nature_keywords:
                if keyword in part:
                    company_nature = part
                    break

            for pattern in size_patterns:
                if re.search(pattern, part):
                    company_people = part
                    break

        remaining = [
            p.strip()
            for p in parts
            if p.strip() not in [company_nature, company_people]
        ]
        if remaining:
            company_status = (
                remaining[0] if len(remaining) == 1 else " | ".join(remaining[:2])
            )

        return company_nature, company_people, company_status

    def parse_education_and_experience(self, tags_text: str) -> Tuple[str, str]:
        """从标签中解析学历和工作经验"""
        educational = "学历不限"
        work_experience = "经验不限"

        if not tags_text:
            return educational, work_experience

        edu_keywords = ["博士", "硕士", "本科", "大专", "中专", "高中", "学历不限"]
        for edu in edu_keywords:
            if edu in tags_text:
                educational = edu
                break

        exp_match = re.search(r"(\d+)-?(\d*)年", tags_text)
        if exp_match:
            if exp_match.group(2):
                work_experience = f"{exp_match.group(1)}-{exp_match.group(2)}年"
            else:
                work_experience = f"{exp_match.group(1)}年以上"
        elif "无需经验" in tags_text or "经验不限" in tags_text:
            work_experience = "经验不限"

        return educational, work_experience

    def _parse_job_card(self, card, keyword: str) -> Optional[Dict]:
        """解析单个职位卡片

        Args:
            card: WebElement 职位卡片元素
            keyword: 搜索关键词

        Returns:
            Optional[Dict]: 职位信息字典，解析失败返回 None
        """
        try:
            job_info = {}

            # 职位名称
            try:
                title_elem = card.find_element(By.CLASS_NAME, "jname")
                job_info["title"] = title_elem.text.strip()
            except:
                job_info["title"] = ""

            # 薪资
            try:
                salary_elem = card.find_element(By.CLASS_NAME, "sal")
                salary_text = salary_elem.text.strip()
                job_info["salary"], job_info["salaryMonth"] = self.parse_salary(
                    salary_text
                )
            except:
                job_info["salary"] = "薪资面议"
                job_info["salaryMonth"] = "12薪"

            # 公司名称
            try:
                company_elem = card.find_element(By.CLASS_NAME, "cname")
                job_info["companyTitle"] = company_elem.text.strip()
            except:
                job_info["companyTitle"] = ""

            # 工作地点
            try:
                location_elem = card.find_element(By.CLASS_NAME, "area")
                job_info["address"] = location_elem.text.strip()
            except:
                job_info["address"] = ""

            # 公司信息
            try:
                company_info_elems = card.find_elements(By.CLASS_NAME, "dc")
                info_text = " | ".join(
                    [
                        elem.text.strip()
                        for elem in company_info_elems[:3]
                        if elem.text.strip()
                    ]
                )
                (
                    job_info["companyNature"],
                    job_info["companyPeople"],
                    job_info["companyStatus"],
                ) = self.parse_company_info(info_text)
            except:
                job_info["companyNature"] = "未知"
                job_info["companyPeople"] = "未知"
                job_info["companyStatus"] = "未知"

            # 职位标签
            try:
                tags_elem = card.find_element(By.CLASS_NAME, "joblist-item-tags")
                tags_text = tags_elem.text.strip()
                job_info["workTag"] = tags_text
                job_info["educational"], job_info["workExperience"] = (
                    self.parse_education_and_experience(tags_text)
                )
            except:
                job_info["workTag"] = ""
                job_info["educational"] = "学历不限"
                job_info["workExperience"] = "经验不限"

            # 岗位类型
            job_info["type"] = keyword
            job_info["pratice"] = "实习" in job_info.get(
                "title", ""
            ) or "实习" in job_info.get("workTag", "")

            # 详情链接
            try:
                link_elem = card.find_element(By.TAG_NAME, "a")
                job_info["detailUrl"] = link_elem.get_attribute("href")
            except:
                job_info["detailUrl"] = ""

            # 其他字段（默认值）
            job_info["companyTags"] = ""
            job_info["hrWork"] = ""
            job_info["hrName"] = ""
            job_info["companyAvatar"] = ""
            job_info["companyUrl"] = ""
            job_info["dist"] = ""

            return job_info

        except Exception as e:
            self._log(f"  解析职位卡片时出错: {e}", level="error")
            return None

    def _get_job_cards(self, driver, wait) -> List:
        """获取当前页面的所有职位卡片元素

        Args:
            driver: WebDriver 实例
            wait: WebDriverWait 实例

        Returns:
            List: WebElement 列表
        """
        try:
            job_cards = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "joblist-item-job"))
            )
            return job_cards
        except:
            # 回退方案
            return driver.find_elements(By.CSS_SELECTOR, "[class*='joblist-item']")

    def _parse_current_page(self, driver, wait, keyword: str) -> List[Dict]:
        """解析当前页面的职位列表

        Args:
            driver: WebDriver 实例
            wait: WebDriverWait 实例
            keyword: 搜索关键词

        Returns:
            List[Dict]: 职位信息列表
        """
        try:
            job_cards = self._get_job_cards(driver, wait)

            if not job_cards:
                self._log("  未找到职位卡片", level="warning")
                return []

            self._log(f"  找到 {len(job_cards)} 个职位卡片")

            jobs = []
            for i, card in enumerate(job_cards):
                job_info = self._parse_job_card(card, keyword)
                if job_info:
                    jobs.append(job_info)
                else:
                    self._log(f"  解析第 {i + 1} 个职位卡片失败", level="warning")

            if jobs:
                self.rate_limiter.report_success()
            else:
                self.rate_limiter.report_failure()

            return jobs

        except Exception as e:
            self._log(f"  解析页面时出错: {e}", level="error")
            self.rate_limiter.report_failure()
            return []

    # ==================== 城市选择 ====================

    def _select_city(self, driver, wait, city: str) -> bool:
        """通过点击选择城市

        Args:
            driver: WebDriver 实例
            wait: WebDriverWait 实例
            city: 目标城市名称（如"上海"、"北京"）

        Returns:
            bool: 是否成功选择城市
        """
        if not city:
            self._log("[城市选择] 未指定城市，跳过城市选择")
            return True

        self._log(f"[城市选择] 正在选择城市: {city}")

        try:
            # 1. 点击"其他城市"展开城市选择弹窗
            self._log("[城市选择] 点击'其他城市'展开城市选择器...")
            allcity_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='allcity']"))
            )
            allcity_button.click()
            self._log("[城市选择] 已展开城市选择弹窗")
            time.sleep(1)

            # 2. 在弹窗中点击目标城市
            # 先尝试点击带有 resumeDialog__top-city-active 类的城市
            city_xpath_active = f"//span[contains(@class,'resumeDialog__top-city') and contains(text(),'{city}')]"
            # 再尝试普通的 span 包含城市名
            city_xpath_normal = f"//span[contains(text(),'{city}')]"

            city_option = None
            for xpath in [city_xpath_active, city_xpath_normal]:
                try:
                    city_option = driver.find_element(By.XPATH, xpath)
                    self._log(f"[城市选择] 找到城市选项: {city}")
                    break
                except:
                    continue

            if not city_option:
                self._log(
                    f"[城市选择] 未找到城市'{city}'，可能不在热门城市列表中",
                    level="warning",
                )
                # 关闭弹窗（按ESC）
                driver.execute_script(
                    "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}));"
                )
                time.sleep(0.5)
                return False

            city_option.click()
            self._log(f"[城市选择] 已点击城市: {city}")
            time.sleep(0.5)

            # 3. 点击"确定"按钮
            self._log("[城市选择] 点击'确定'按钮...")
            confirm_button = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//span[@class='dialog_footer_wrapper']//button[@type='button']",
                    )
                )
            )
            confirm_button.click()
            self._log("[城市选择] 已点击确定按钮")

            # 4. 等待城市切换完成
            time.sleep(2)
            self._log(f"[城市选择] ✅ 成功切换到城市: {city}")
            return True

        except Exception as e:
            self._log(f"[城市选择] 选择城市时出错: {e}", level="error")
            import traceback

            self._log(traceback.format_exc(), level="debug")
            return False

    # ==================== 页面操作 ====================

    def _open_search_page(self, driver, keyword: str) -> bool:
        """打开搜索页面

        Args:
            driver: WebDriver 实例
            keyword: 搜索关键词

        Returns:
            bool: 是否成功打开
        """
        url = f"{self.base_url}?keyword={keyword}"
        self._log(f"[初始化] 访问: {url}")

        try:
            driver.get(url)
            time.sleep(random.uniform(3, 5))

            # 检查是否被重定向
            if "we.51job.com" not in driver.current_url:
                self._log(f"[错误] 页面被重定向！可能遇到反爬验证", level="error")
                return False

            return True
        except Exception as e:
            self._log(f"[错误] 打开页面失败: {e}", level="error")
            return False

    def _scroll_page_for_cards(self, driver, times: int = 3, delay: float = 0.5):
        """滚动页面以加载职位卡片

        Args:
            driver: WebDriver 实例
            times: 滚动次数
            delay: 每次滚动后的延迟（秒）
        """
        for _ in range(times):
            driver.execute_script("window.scrollBy(0, 400)")
            time.sleep(delay)

    def _get_total_pages(self, driver) -> int:
        """从页面获取搜索结果的总页数（51job限制最多50页）"""
        max_pages = 50

        try:
            # 方式1: 从分页按钮中找最大页码
            pagination_selectors = [
                '//ul[contains(@class,"el-pager")]//li[contains(@class,"number")]',
                '//div[contains(@class,"el-pagination")]//li[contains(@class,"number")]',
                '//div[contains(@class,"page")]//a',
                '//div[contains(@class,"pagination")]//a',
            ]

            for selector in pagination_selectors:
                try:
                    page_elements = driver.find_elements(By.XPATH, selector)
                    if page_elements:
                        page_numbers = []
                        for elem in page_elements:
                            text = elem.text.strip()
                            if text.isdigit():
                                page_numbers.append(int(text))

                        if page_numbers:
                            detected_max = max(page_numbers)
                            total = min(detected_max, max_pages)
                            self._log(
                                f"[页数检测] 从分页按钮检测到 {detected_max} 页，限制为 {total} 页"
                            )
                            return total
                except:
                    continue

            # 方式2: 查找 "共 X 页" 文本
            text_patterns = [
                '//span[contains(text(),"共") and contains(text(),"页")]',
                '//div[contains(text(),"共") and contains(text(),"页")]',
                '//span[contains(@class,"total")]',
            ]

            for pattern in text_patterns:
                try:
                    elem = driver.find_element(By.XPATH, pattern)
                    text = elem.text
                    match = re.search(r"(\d+)", text)
                    if match:
                        detected = int(match.group(1))
                        total = min(detected, max_pages)
                        self._log(
                            f"[页数检测] 从文本检测到 {detected} 页，限制为 {total} 页"
                        )
                        return total
                except:
                    continue

            # 方式3: 检查是否有 "下一页" 按钮
            try:
                next_buttons = driver.find_elements(
                    By.XPATH,
                    '//a[contains(text(),"下一页") or contains(@class,"next")]',
                )
                if not next_buttons:
                    self._log(f"[页数检测] 未找到下一页按钮，假设只有 1 页")
                    return 1
            except:
                pass

        except Exception as e:
            self._log(f"[页数检测] 检测总页数时出错: {e}", level="warning")

        self._log(f"[页数检测] 无法检测页数，使用默认限制 {max_pages} 页")
        return max_pages

    def _detect_and_adjust_page_limit(
        self, driver, requested_pages: int, keyword: str
    ) -> int:
        """检测实际可用的总页数并调整请求"""
        actual_total = self._get_total_pages(driver)

        if actual_total < requested_pages:
            self._log(
                f"\n[⚠️ 页数限制] 关键词 '{keyword}' 的搜索结果只有 {actual_total} 页"
                f"（您请求了 {requested_pages} 页）",
                level="warning",
            )
            self._log(f"[⚠️ 页数限制] 51job 每个搜索最多显示 50 页", level="warning")
            self._log(
                f"[⚠️ 页数限制] 将自动调整为爬取 {actual_total} 页\n", level="warning"
            )
            return actual_total

        if requested_pages > 50:
            self._log(
                f"\n[⚠️ 页数限制] 51job 限制每个搜索最多 50 页"
                f"（您请求了 {requested_pages} 页）",
                level="warning",
            )
            self._log(f"[⚠️ 页数限制] 将自动调整为爬取 50 页\n", level="warning")
            return 50

        return requested_pages

    def _click_next_page(self, driver, target_page: int) -> bool:
        """点击分页按钮翻页"""
        self._log(f"[点击翻页] 正在点击分页按钮跳转到第{target_page}页...")

        try:
            # Element UI 分页选择器
            pagination_selectors = [
                f'//ul[contains(@class,"el-pager")]//li[contains(@class,"number")][text()="{target_page}"]',
                f'//div[contains(@class,"el-pagination")]//li[contains(@class,"number")][text()="{target_page}"]',
            ]

            # 尝试点击具体页码
            for selector in pagination_selectors:
                try:
                    page_button = driver.find_element(By.XPATH, selector)

                    # 检查是否已是当前页
                    button_class = page_button.get_attribute("class") or ""
                    if "active" in button_class:
                        self._log(f"[点击翻页] 目标页 {target_page} 已是当前页")
                        return True

                    # 滚动到按钮可见
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        page_button,
                    )
                    time.sleep(0.5)

                    # 点击前记录第一条职位
                    first_job_before = self._get_first_job_signature(driver)

                    # 点击按钮
                    page_button.click()
                    self._log(f"[点击翻页] 成功点击页码按钮")

                    # 等待 AJAX 加载
                    self._log(f"[点击翻页] 等待AJAX数据加载...")
                    time.sleep(random.uniform(2, 3))

                    # 验证页码高亮
                    try:
                        active_page_elem = driver.find_element(
                            By.XPATH,
                            '//ul[contains(@class,"el-pager")]//li[contains(@class,"active")]',
                        )
                        active_page = active_page_elem.text.strip()
                        if active_page == str(target_page):
                            self._log(
                                f"[点击翻页] ✅ 页码高亮验证通过: 当前第{active_page}页"
                            )
                        else:
                            self._log(
                                f"[点击翻页] ⚠️ 页码显示为第{active_page}页，期望第{target_page}页",
                                level="warning",
                            )
                    except:
                        pass

                    # 验证数据是否更新
                    if first_job_before:
                        time.sleep(1)
                        first_job_after = self._get_first_job_signature(driver)
                        if first_job_before == first_job_after:
                            self._log(f"[点击翻页] ⚠️ 数据未更新警告", level="warning")
                        else:
                            self._log(f"[点击翻页] ✅ 数据已更新", level="debug")

                    return True

                except:
                    continue

            # 如果没找到具体页码，尝试点击"下一页"
            self._log(f"[点击翻页] 未找到页码按钮，尝试点击'下一页'...")
            next_button_selectors = [
                '//ul[contains(@class,"el-pager")]//li[contains(@class,"btn-next")]',
                '//button[contains(@class,"btn-next")]',
            ]

            for selector in next_button_selectors:
                try:
                    next_button = driver.find_element(By.XPATH, selector)

                    # 检查是否禁用
                    button_class = next_button.get_attribute("class") or ""
                    if "disabled" in button_class:
                        self._log(f"[点击翻页] '下一页'按钮已禁用，可能已到达最后一页")
                        return False

                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        next_button,
                    )
                    time.sleep(0.5)
                    next_button.click()
                    self._log(f"[点击翻页] 成功点击'下一页'按钮")

                    time.sleep(random.uniform(2, 3))
                    return True

                except:
                    continue

            self._log(f"[点击翻页] 无法找到分页按钮", level="error")
            return False

        except Exception as e:
            self._log(f"[点击翻页] 翻页过程中出错: {e}", level="error")
            return False

    def _get_first_job_signature(self, driver) -> str:
        """获取第一条职位的签名（用于验证数据是否更新）"""
        try:
            first_card = driver.find_element(By.CLASS_NAME, "joblist-item-job")
            title_elem = first_card.find_element(By.CLASS_NAME, "jname")
            company_elem = first_card.find_element(By.CLASS_NAME, "cname")
            return f"{title_elem.text.strip()}_{company_elem.text.strip()}"
        except:
            return ""

    # ==================== 验证码处理 ====================

    def _check_and_handle_captcha(self, driver) -> bool:
        """检查并处理验证码

        Returns:
            bool: 是否需要用户处理验证码
        """
        captcha_indicators = [
            '//div[contains(text(),"验证码") or contains(@class,"captcha")]',
            '//input[@placeholder="*验证码" or contains(@id,"captcha")]',
            '//div[contains(text(),"点击验证") or contains(text(),"滑动验证")]',
            '//iframe[contains(@src,"captcha") or contains(@src,"geetest")]',
        ]

        for indicator in captcha_indicators:
            try:
                elements = driver.find_elements(By.XPATH, indicator)
                if elements:
                    self._log("\n" + "=" * 60, level="warning")
                    self._log("检测到验证码！请手动完成验证", level="warning")
                    self._log("=" * 60, level="warning")
                    self._log("请在浏览器窗口中:", level="warning")
                    self._log(
                        "  1. 完成验证码（滑块、图片点击或文字输入）", level="warning"
                    )
                    self._log("  2. 完成后在此窗口按回车继续...", level="warning")
                    self._log("=" * 60 + "\n", level="warning")
                    return True
            except:
                continue

        return False

    def _wait_for_captcha_completion(self, driver, timeout: int = 300) -> bool:
        """等待用户完成验证码

        Args:
            driver: WebDriver 实例
            timeout: 超时时间（秒）

        Returns:
            bool: 用户是否完成了验证
        """
        import threading

        self._captcha_completed = False

        def wait_for_input():
            input("按回车键继续爬取（验证完成后）...")
            self._captcha_completed = True

        input_thread = threading.Thread(target=wait_for_input)
        input_thread.daemon = True
        input_thread.start()

        self._log(f"等待用户完成验证码（超时: {timeout}秒）...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._captcha_completed:
                self._log("用户已完成验证，继续爬取...")
                return True
            time.sleep(0.5)

        self._log("验证码等待超时！", level="error")
        return False

    # ==================== 主运行逻辑 ====================

    def _run_crawl_session(
        self,
        driver,
        wait,
        keyword: str,
        start_page: int,
        end_page: int,
        city: str = "",
        total_pages: int = 0,
        checkpoint=None,
    ) -> List[Dict]:
        """在同一个浏览器会话中爬取多页"""
        all_jobs = []
        resume = checkpoint is not None

        for page in range(start_page, end_page + 1):
            # 检查是否已完成
            if resume and self.checkpoint_manager.is_page_completed(page):
                self._log(f"\n[跳过] 第 {page} 页已完成")
                if page < end_page:
                    self._click_next_page(driver, page + 1)
                continue

            self._log(f"\n{'=' * 70}")
            self._log(f"[页面 {page}/{total_pages or end_page}] 正在爬取...")
            self._log(f"{'=' * 70}")

            # 验证码检测
            if self._check_and_handle_captcha(driver):
                if not self._wait_for_captcha_completion(driver):
                    self._log("验证码处理失败，停止爬取", level="error")
                    break
                time.sleep(2)

            # 如果不是第一页，需要翻页
            if page > 1:
                if page == start_page and start_page > 1:
                    # 从第1页翻页到start_page
                    self._log(f"[断点恢复] 从第1页点击翻页到第{page}页...")
                    for p in range(2, page + 1):
                        if not self._click_next_page(driver, p):
                            self._log(f"[错误] 无法翻页到第 {p} 页", level="error")
                            return all_jobs
                        time.sleep(random.uniform(2, 3))
                else:
                    # 普通翻页
                    success = self._click_next_page(driver, page)
                    if not success:
                        self._log(
                            f"[错误] 无法翻页到第 {page} 页，停止爬取", level="error"
                        )
                        break

            # 滚动加载
            self._scroll_page_for_cards(driver, times=3, delay=0.5)

            # 解析页面
            jobs = self._parse_current_page(driver, wait, keyword)

            if jobs:
                all_jobs.extend(jobs)
                self.stats["pages_processed"] += 1
                self.stats["records_collected"] += len(jobs)
                self._log(f"[页面 {page}] 成功获取 {len(jobs)} 条职位信息")
                self._log(f"[累计] 本批: {len(all_jobs)} 条")
                self._update_status(
                    current_page=page, raw_count=self.stats["records_collected"]
                )

                # 保存到数据库
                saved, skipped = self.save_to_database(jobs)
                self.stats["records_saved"] += saved
                self._log(f"[保存] 保存成功: {saved} 条 | 跳过重复: {skipped} 条")
                self._update_status(saved_count=self.stats["records_saved"])
            else:
                self._log(f"[页面 {page}] 无数据或出错", level="warning")
                self.stats["errors"] += 1
                self._update_status(current_page=page, error_count=self.stats["errors"])

            # 保存检查点
            self.checkpoint_manager.save_checkpoint(
                keyword=keyword,
                city=city,
                current_page=page,
                total_pages=total_pages or end_page,
                records_collected=self.stats["records_collected"],
            )

            # 页面间延时
            if page < end_page:
                delay = random.uniform(4, 7)
                self._log(f"[延时] 等待 {delay:.1f} 秒后翻页...")
                time.sleep(delay)

        return all_jobs

    def run_crawler_with_checkpoint(
        self,
        keyword: str = "大数据",
        city: str = "",
        pages: int = 5,
        resume: bool = True,
    ) -> Dict:
        """运行爬虫（支持断点续传）

        这是主要的爬虫入口方法。由于51job限制每个搜索最多50页，
        整个爬取过程在一个浏览器会话中完成。

        Args:
            keyword: 搜索关键词
            city: 城市（保留参数，当前未参与实际请求）
            pages: 爬取页数
            resume: 是否尝试恢复之前的进度

        Returns:
            Dict: 统计信息
        """
        self.stats["start_time"] = time.time()

        # 尝试恢复检查点
        checkpoint = None
        if resume:
            checkpoint = self.checkpoint_manager.load_checkpoint()
            if checkpoint:
                self._log(f"[断点续传] 发现之前的进度: 第{checkpoint.current_page}页")
                self._log(f"[断点续传] 已完成页面: {len(checkpoint.completed_pages)}页")
                keyword = checkpoint.keyword
                city = checkpoint.city

                remaining_pages = self.checkpoint_manager.get_remaining_pages(1, pages)
                if not remaining_pages:
                    self._log("[断点续传] 所有页面已完成！")
                    return self._get_final_stats()

                self._log(f"[断点续传] 继续爬取 {len(remaining_pages)} 个剩余页面")

        self._log("=" * 70)
        self._log("前程无忧爬虫启动")
        self._log("=" * 70)
        self._log(f"\n配置:")
        self._log(f"  - 关键词: {keyword}")
        self._log(f"  - 城市: {city}")
        self._log(f"  - 页数: {pages}")
        self._log(f"  - 断点续传: {'已启用' if resume else '已禁用'}")
        self._log(f"  - 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 标记为运行中
        self._update_status(
            status="running", keyword=keyword, city=city, total_pages=pages
        )

        driver = None
        try:
            # 创建浏览器会话
            driver = self.create_driver()
            wait = WebDriverWait(driver, 15)

            # 打开搜索页
            if not self._open_search_page(driver, keyword):
                return self._get_final_stats()

            # 【城市选择】如果指定了城市，点击选择
            if city:
                self._select_city(driver, wait, city)

            # 【页数限制】检测实际可用页数
            pages = self._detect_and_adjust_page_limit(driver, pages, keyword)

            # 运行爬取会话
            all_jobs = self._run_crawl_session(
                driver=driver,
                wait=wait,
                keyword=keyword,
                start_page=1,
                end_page=pages,
                city=city,
                total_pages=pages,
                checkpoint=checkpoint if resume else None,
            )

            self._log(f"\n[完成] 本次共获取 {len(all_jobs)} 条职位信息")

        except KeyboardInterrupt:
            self._log("\n\n[!] 用户中断爬虫")
            self._log("[断点续传] 进度已保存，下次运行将自动恢复")
            self._mark_error("用户中断")

        except Exception as e:
            self._log(f"\n\n[!] 爬虫异常: {e}")
            import traceback

            self._log(traceback.format_exc(), level="error")
            self._log("[断点续传] 进度已保存，下次运行将自动恢复")
            self._mark_error(str(e))

        finally:
            if driver:
                driver.quit()
                self._log("[清理] 浏览器会话已关闭")

        return self._get_final_stats()

    def save_to_database(self, jobs: List[Dict]) -> Tuple[int, int]:
        """批量保存数据到数据库

        Returns:
            Tuple[int, int]: (保存成功数, 跳过重复数)
        """
        saved_count = 0
        skipped_count = 0

        with transaction.atomic():
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
                    else:
                        skipped_count += 1

                except Exception as e:
                    self._log(f"  保存数据时出错: {e}", level="error")
                    continue

        return saved_count, skipped_count

    def _get_final_stats(self) -> Dict:
        """获取最终统计信息"""
        elapsed = (
            time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        )

        self._log(f"\n{'=' * 70}")
        self._log("爬取完成！")
        self._log(f"{'=' * 70}")
        self._log(f"统计信息:")
        self._log(f"  - 处理页面: {self.stats['pages_processed']} 页")
        self._log(f"  - 采集记录: {self.stats['records_collected']} 条")
        self._log(f"  - 保存记录: {self.stats['records_saved']} 条")
        self._log(f"  - 运行时间: {elapsed / 60:.1f} 分钟")
        if self.stats["pages_processed"] > 0:
            self._log(
                f"  - 平均速度: {elapsed / self.stats['pages_processed']:.1f} 秒/页"
            )
        self._log(f"{'=' * 70}")

        # 完成后清除检查点
        self.checkpoint_manager.clear_checkpoint()

        # 标记为完成
        if self.run_store and self.run_id:
            current_status = self.run_store.read_status(self.run_id)
            if current_status and current_status.get("status") != "error":
                self._mark_completed()

        return {
            "pages_processed": self.stats["pages_processed"],
            "records_collected": self.stats["records_collected"],
            "records_saved": self.stats["records_saved"],
            "elapsed_seconds": elapsed,
            "errors": self.stats["errors"],
        }


def run_crawler(
    keyword: str = "大数据",
    city: str = "",
    pages: int = 5,
    resume: bool = True,
    headless: bool = True,
    run_store: Optional[CrawlRunStore] = None,
    run_id: Optional[str] = None,
) -> Dict:
    """运行爬虫主函数（便捷接口）"""
    crawler = Job51Crawler(
        headless=headless,
        run_store=run_store,
        run_id=run_id,
    )
    return crawler.run_crawler_with_checkpoint(
        keyword=keyword,
        city=city,
        pages=pages,
        resume=resume,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="前程无忧爬虫")
    parser.add_argument("--keyword", default="大数据", help="搜索关键词")
    parser.add_argument("--city", default="", help="城市")
    parser.add_argument("--pages", type=int, default=5, help="爬取页数")
    parser.add_argument("--no-resume", action="store_true", help="禁用断点续传")
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="显示浏览器窗口（用于调试，可观察是否被反爬拦截）",
    )

    args = parser.parse_args()

    run_crawler(
        keyword=args.keyword,
        city=args.city,
        pages=args.pages,
        resume=not args.no_resume,
        headless=not args.show_browser,
    )
