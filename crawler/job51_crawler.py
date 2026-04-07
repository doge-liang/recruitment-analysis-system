#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
前程无忧爬虫模块
集成断点续传、批量控制、自适应限速功能
用于大规模数据爬取（20000+记录）
"""

import json
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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from myApp.models import JobInfo

# 导入检查点管理器
# 确保 crawler 目录在 Python 路径中
_crawler_dir = Path(__file__).resolve().parent
if str(_crawler_dir) not in sys.path:
    sys.path.insert(0, str(_crawler_dir))

try:
    from checkpoint_manager import (
        BatchCalculator,
        BatchStateManager,
        CheckpointManager,
    )
except ImportError as e:
    print(f"[错误] 无法导入 checkpoint_manager: {e}")
    print(f"[调试] Python path: {sys.path}")
    print(f"[调试] 当前文件: {__file__}")
    raise

# 导入运行存储管理器
try:
    from run_store import CrawlRunStore, build_crawler_logger
except ImportError as e:
    print(f"[错误] 无法导入 run_store: {e}")
    raise


class AdaptiveRateLimiter:
    """
    自适应速率限制器

    根据成功/失败动态调整延迟，避免被检测
    """

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
        # 添加抖动 (0.8x 到 1.5x)
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

        # 连续失败3次以上，额外等待
        if self.consecutive_failures >= 3:
            extra_wait = min(60, 10 * self.consecutive_failures)
            print(f"  连续失败{self.consecutive_failures}次，额外等待{extra_wait}秒...")
            time.sleep(extra_wait)


class Job51Crawler:
    """
    前程无忧爬虫类

    新特性:
    - 断点续传: 崩溃后可恢复
    - 批量控制: 分页处理，批次间休息
    - 自适应限速: 动态调整请求频率
    - 增强日志: 详细进度跟踪
    """

    def __init__(
        self,
        checkpoint_file: str = "crawler_checkpoint.json",
        batch_state_file: str = "batch_state.json",
        headless: bool = True,
        run_store: Optional[CrawlRunStore] = None,
        run_id: Optional[str] = None,
    ):
        self.base_url = "https://we.51job.com/pc/search"
        self.data = []
        self.chrome_options = Options()

        # 反检测设置
        self._setup_anti_detection(headless=headless)

        # 检查点管理
        self.checkpoint_manager = CheckpointManager(checkpoint_file)
        self.batch_state_manager = BatchStateManager(batch_state_file)

        # 自适应限速器
        self.rate_limiter = AdaptiveRateLimiter(base_delay=3.0, max_delay=30.0)

        # 统计信息
        self.stats = {
            "pages_processed": 0,
            "records_collected": 0,
            "records_saved": 0,
            "errors": 0,
            "start_time": None,
            "last_page_time": None,
        }

        # 运行存储和日志
        self.run_store = run_store
        self.run_id = run_id
        self.logger = self._setup_logger()

    def _setup_anti_detection(self, headless=True):
        """配置反检测选项

        Args:
            headless: 是否使用无头模式（默认True）。设为False可显示浏览器窗口用于调试
        """
        self.chrome_options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )
        self.chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        self.chrome_options.add_experimental_option("useAutomationExtension", False)

        # 控制是否显示浏览器窗口
        if headless:
            self.chrome_options.add_argument("--headless")

        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")

        # 额外的反检测参数
        self.chrome_options.add_argument("--disable-blink-features")
        self.chrome_options.add_argument("--disable-web-security")
        self.chrome_options.add_argument(
            "--disable-features=IsolateOrigins,site-per-process"
        )
        self.chrome_options.add_argument("--allow-running-insecure-content")

        self.chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器

        如果有 run_store 和 run_id，使用文件日志；否则使用控制台日志。
        """
        if self.run_store and self.run_id:
            return build_crawler_logger(self.run_store, self.run_id)
        else:
            # 创建简单的控制台 logger
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

    def parse_company_info(self, info_text):
        """解析公司信息文本"""
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

    def parse_education_and_experience(self, tags_text):
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

    def crawl_job_list(self, keyword: str = "大数据", page: int = 1) -> List[Dict]:
        """
        爬取单页职位列表

        【修复】前程无忧使用AJAX分页，URL参数无效，改用点击翻页
        
        Args:
            keyword: 搜索关键词
            page: 页码

        Returns:
            List[Dict]: 职位信息列表
        """
        # 使用点击翻页方案（URL参数分页已失效）
        return self.crawl_page_with_click_pagination(keyword=keyword, target_page=page)

    def crawl_job_list_with_click_pagination(
        self, driver, keyword: str, target_page: int
    ) -> List[Dict]:
        """
        【备选方案】使用点击分页按钮的方式进行翻页

        当URL参数分页失效时使用此方法。它会：
        1. 首先访问第一页
        2. 点击分页按钮跳转到目标页
        3. 等待页面内容更新

        Args:
            driver: Selenium WebDriver实例（已打开第一页）
            keyword: 搜索关键词
            target_page: 目标页码

        Returns:
            List[Dict]: 职位信息列表
        """
        wait = WebDriverWait(driver, 15)

        if target_page == 1:
            # 第一页无需翻页
            self._log("  当前已在第1页")
        else:
            self._log(f"  [点击翻页] 正在点击分页按钮跳转到第{target_page}页...")

            try:
                # 方法1: 尝试找到并点击具体的页码按钮
                # 常见的分页按钮选择器（包括 Element UI）
                pagination_selectors = [
                    f'//ul[contains(@class,"el-pager")]//li[contains(@class,"number")][text()="{target_page}"]',  # Element UI
                    f'//div[contains(@class,"el-pagination")]//li[contains(@class,"number")][text()="{target_page}"]',  # Element UI 2
                    f'//div[contains(@class,"page")]//a[text()="{target_page}"]',  # 通用分页
                    f'//div[contains(@class,"pagination")]//a[text()="{target_page}"]',
                    f'//a[@data-page="{target_page}"]',
                    f'//button[@data-page="{target_page}"]',
                    f'//li[contains(@class,"page")]//a[text()="{target_page}"]',
                ]

                page_clicked = False
                for selector in pagination_selectors:
                    try:
                        page_button = driver.find_element(By.XPATH, selector)
                        # 滚动到按钮可见
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});",
                            page_button,
                        )
                        time.sleep(0.5)

                        # 【Element UI特殊处理】检查是否是当前已选中的页码
                        button_class = page_button.get_attribute("class") or ""
                        if "active" in button_class:
                            self._log(f"  [点击翻页] 目标页 {target_page} 已是当前页")
                            page_clicked = True
                            break

                        # 点击前记录第一条职位信息
                        first_job_before = None
                        try:
                            first_card = driver.find_element(
                                By.CLASS_NAME, "joblist-item-job"
                            )
                            title_elem = first_card.find_element(By.CLASS_NAME, "jname")
                            company_elem = first_card.find_element(
                                By.CLASS_NAME, "cname"
                            )
                            first_job_before = (
                                f"{title_elem.text.strip()}_{company_elem.text.strip()}"
                            )
                        except:
                            pass

                        page_button.click()
                        page_clicked = True
                        self._log(f"  [点击翻页] 成功点击页码按钮: {selector}")

                        # 【关键】等待AJAX数据加载完成
                        self._log(f"  [点击翻页] 等待AJAX数据加载...")
                        time.sleep(random.uniform(2, 3))

                        # 【验证1】检查当前页码高亮是否更新
                        try:
                            # Element UI 当前页码有 .active 类
                            active_page_elem = driver.find_element(
                                By.XPATH,
                                '//ul[contains(@class,"el-pager")]//li[contains(@class,"active")]',
                            )
                            active_page = active_page_elem.text.strip()
                            if active_page == str(target_page):
                                self._log(
                                    f"  [点击翻页] ✅ 页码高亮验证通过: 当前第{active_page}页"
                                )
                            else:
                                self._log(
                                    f"  [点击翻页] ⚠️ 页码高亮验证失败: 显示第{active_page}页，期望第{target_page}页",
                                    level="warning",
                                )
                        except:
                            self._log(f"  [点击翻页] 无法验证页码高亮", level="debug")

                        # 【验证2】检查职位列表是否更新
                        try:
                            if first_job_before:
                                # 重新获取第一条职位
                                time.sleep(1)  # 等待DOM更新
                                first_card_after = driver.find_element(
                                    By.CLASS_NAME, "joblist-item-job"
                                )
                                title_elem_after = first_card_after.find_element(
                                    By.CLASS_NAME, "jname"
                                )
                                company_elem_after = first_card_after.find_element(
                                    By.CLASS_NAME, "cname"
                                )
                                first_job_after = f"{title_elem_after.text.strip()}_{company_elem_after.text.strip()}"

                                if first_job_before == first_job_after:
                                    self._log(
                                        f"  [点击翻页] ⚠️ 数据未更新警告: 第一条职位与点击前相同",
                                        level="warning",
                                    )
                                    self._log(
                                        f"  [点击翻页] 点击前: {first_job_before}",
                                        level="debug",
                                    )
                                    self._log(
                                        f"  [点击翻页] 点击后: {first_job_after}",
                                        level="debug",
                                    )
                                else:
                                    self._log(
                                        f"  [点击翻页] ✅ 数据已更新", level="debug"
                                    )
                        except Exception as e:
                            self._log(f"  [点击翻页] 数据验证出错: {e}", level="debug")

                        break
                    except:
                        continue

                # 方法2: 如果没找到具体页码，尝试点击"下一页"按钮多次
                if not page_clicked and target_page > 1:
                    self._log(f"  [点击翻页] 未找到页码按钮，尝试点击'下一页'按钮...")
                    next_button_selectors = [
                        '//a[contains(text(),"下一页")]',
                        '//a[contains(@class,"next")]',
                        '//button[contains(text(),"下一页")]',
                        '//li[contains(@class,"next")]//a',
                        '//span[contains(text(),"下一页")]/parent::a',
                    ]

                    for i in range(target_page - 1):  # 需要点击 (target_page - 1) 次
                        clicked = False
                        for selector in next_button_selectors:
                            try:
                                next_button = driver.find_element(By.XPATH, selector)
                                # 检查是否禁用
                                disabled = (
                                    next_button.get_attribute("disabled")
                                    or "disabled" in next_button.get_attribute("class")
                                    or "class"
                                    in str(next_button.get_attribute("class")).lower()
                                )
                                if disabled:
                                    self._log(
                                        f"  [点击翻页] '下一页'按钮已禁用，可能已到达最后一页"
                                    )
                                    break

                                driver.execute_script(
                                    "arguments[0].scrollIntoView({block: 'center'});",
                                    next_button,
                                )
                                time.sleep(0.5)
                                next_button.click()
                                clicked = True
                                self._log(
                                    f"  [点击翻页] 点击'下一页' ({i + 1}/{target_page - 1})"
                                )

                                # 等待页面加载
                                time.sleep(random.uniform(2, 3))

                                # 等待职位列表更新
                                try:
                                    wait.until(
                                        EC.presence_of_element_located(
                                            (By.CLASS_NAME, "joblist-item-job")
                                        )
                                    )
                                except:
                                    pass
                                break
                            except:
                                continue

                        if not clicked:
                            self._log(
                                f"  [警告] 无法点击'下一页'按钮，可能已到达最后一页或被反爬",
                                level="warning",
                            )
                            break

                # 方法3: 如果是小页数，尝试输入框跳转
                if not page_clicked and target_page <= 10:
                    try:
                        # 查找页码输入框
                        input_selectors = [
                            '//input[@type="text"][contains(@class,"page")]',
                            '//input[@placeholder="页码"]',
                            '//input[contains(@class,"pagination")]',
                        ]

                        for selector in input_selectors:
                            try:
                                page_input = driver.find_element(By.XPATH, selector)
                                page_input.clear()
                                page_input.send_keys(str(target_page))

                                # 查找并点击确认/跳转按钮
                                confirm_selectors = [
                                    '//button[contains(text(),"确定")]',
                                    '//button[contains(text(),"跳转")]',
                                    '//a[contains(text(),"GO")]',
                                    '//input[@type="submit"]',
                                ]

                                for confirm_selector in confirm_selectors:
                                    try:
                                        confirm_btn = driver.find_element(
                                            By.XPATH, confirm_selector
                                        )
                                        confirm_btn.click()
                                        page_clicked = True
                                        self._log(
                                            f"  [点击翻页] 通过输入框跳转到第{target_page}页"
                                        )
                                        break
                                    except:
                                        continue

                                if page_clicked:
                                    break
                            except:
                                continue
                    except:
                        pass

                # 等待页面内容更新
                if page_clicked:
                    self._log(f"  [点击翻页] 等待第{target_page}页内容加载...")
                    time.sleep(random.uniform(3, 5))

                    # 滚动加载
                    for _ in range(3):
                        driver.execute_script("window.scrollBy(0, 400)")
                        time.sleep(0.5)

                    # 验证当前页码是否已更新
                    try:
                        # 查找当前页码的高亮元素（包含 Element UI）
                        current_page_selectors = [
                            '//ul[contains(@class,"el-pager")]//li[contains(@class,"active")]',  # Element UI
                            '//div[contains(@class,"el-pagination")]//li[contains(@class,"active")]',  # Element UI 2
                            '//div[contains(@class,"page")]//a[contains(@class,"active") or contains(@class,"current") or contains(@class,"selected")]',
                            '//div[contains(@class,"pagination")]//a[contains(@class,"active") or contains(@class,"current")]',
                            '//li[contains(@class,"active")]//a',
                        ]

                        for selector in current_page_selectors:
                            try:
                                current_page_elem = driver.find_element(
                                    By.XPATH, selector
                                )
                                current_page_text = current_page_elem.text.strip()
                                if current_page_text == str(target_page):
                                    self._log(
                                        f"  [点击翻页] ✅ 验证成功，当前页码显示为第{target_page}页"
                                    )
                                else:
                                    self._log(
                                        f"  [点击翻页] ⚠️ 当前页码显示为第{current_page_text}页，与目标{target_page}页不符",
                                        level="warning",
                                    )
                                break
                            except:
                                continue
                    except:
                        pass
                else:
                    self._log(
                        f"  [警告] 无法找到分页按钮，可能需要检查页面结构",
                        level="warning",
                    )

            except Exception as e:
                self._log(f"  [点击翻页] 翻页过程中出错: {e}", level="error")

    def crawl_page_with_click_pagination(
        self, keyword: str, target_page: int, headless: bool = True
    ) -> List[Dict]:
        """
        【点击翻页方案】爬取单页职位列表

        使用点击分页按钮的方式翻页，当URL参数分页失效时使用。
        这种方法更接近真实用户行为，能有效绕过反爬。

        Args:
            keyword: 搜索关键词
            target_page: 目标页码
            headless: 是否使用无头模式

        Returns:
            List[Dict]: 职位信息列表
        """
        driver = None
        try:
            driver = self.create_driver()
            wait = WebDriverWait(driver, 15)

            # 首先访问第一页
            url = f"{self.base_url}?keyword={keyword}"
            self._log(f"  [点击翻页] 访问第一页: {url}")
            driver.get(url)

            # 等待页面加载
            time.sleep(random.uniform(3, 5))

            # 检查是否被重定向
            current_url = driver.current_url
            if "we.51job.com" not in current_url:
                self._log(f"  [警告] 页面被重定向！可能遇到反爬验证", level="warning")
                return []

            # 如果目标不是第一页，执行翻页
            if target_page > 1:
                self._log(f"  [点击翻页] 准备点击翻页到第{target_page}页...")
                self.crawl_job_list_with_click_pagination(driver, keyword, target_page)

            # 滚动加载内容
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 400)")
                time.sleep(0.5)

            # 获取职位卡片（复用原有的解析逻辑）
            try:
                job_cards = wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CLASS_NAME, "joblist-item-job")
                    )
                )
            except:
                try:
                    job_cards = driver.find_elements(
                        By.CSS_SELECTOR, "[class*='joblist-item']"
                    )
                except:
                    self._log("  [点击翻页] 未找到职位卡片")
                    return []

            self._log(f"  [点击翻页] 找到 {len(job_cards)} 个职位卡片")

            # 解析职位信息（简化版）
            jobs = []
            for i, card in enumerate(job_cards):
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
                        tags_elem = card.find_element(
                            By.CLASS_NAME, "joblist-item-tags"
                        )
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

                    # 其他字段
                    job_info["companyTags"] = ""
                    job_info["hrWork"] = ""
                    job_info["hrName"] = ""
                    job_info["companyAvatar"] = ""
                    job_info["companyUrl"] = ""
                    job_info["dist"] = ""

                    jobs.append(job_info)

                except Exception as e:
                    self._log(
                        f"  [点击翻页] 解析第 {i + 1} 个职位卡片时出错: {e}",
                        level="error",
                    )
                    continue

            if jobs:
                self.rate_limiter.report_success()
            else:
                self.rate_limiter.report_failure()

            return jobs

        except Exception as e:
            self._log(f"  [点击翻页] 爬取页面时出错: {e}", level="error")
            self.rate_limiter.report_failure()
            return []

        finally:
            if driver:
                driver.quit()

    def crawl_with_infinite_scroll(
        self,
        keyword: str = "大数据",
        target_count: int = 100,
        max_scroll_attempts: int = 50,
    ) -> List[Dict]:
        """
        【无限滚动方案】爬取职位列表

        51job使用无限滚动而非传统分页。此方法通过持续滚动页面
        触发加载更多职位，直到获取足够数据或没有新内容。

        Args:
            keyword: 搜索关键词
            target_count: 目标爬取数量
            max_scroll_attempts: 最大滚动尝试次数（防止无限循环）

        Returns:
            List[Dict]: 职位信息列表
        """
        driver = None
        try:
            self.rate_limiter.wait()

            driver = self.create_driver()
            wait = WebDriverWait(driver, 15)

            # 访问搜索页面
            url = f"{self.base_url}?keyword={keyword}"
            self._log(f"  [无限滚动] 访问: {url}")
            driver.get(url)

            # 等待初始页面加载
            time.sleep(random.uniform(3, 5))

            # 检查是否被重定向
            current_url = driver.current_url
            if "we.51job.com" not in current_url:
                self._log(f"  [警告] 页面被重定向！可能遇到反爬验证", level="warning")
                return []

            self._log(f"  [无限滚动] 开始滚动加载，目标: {target_count} 条")

            all_jobs = []
            seen_job_signatures = set()  # 用于去重
            last_job_count = 0
            no_new_count = 0  # 连续无新数据的次数

            for scroll_attempt in range(max_scroll_attempts):
                # 滚动到底部
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self._log(f"  [无限滚动] 第 {scroll_attempt + 1} 次滚动", level="debug")

                # 等待加载
                time.sleep(random.uniform(2, 3))

                # 获取当前所有职位卡片
                try:
                    job_cards = driver.find_elements(By.CLASS_NAME, "joblist-item-job")
                except:
                    try:
                        job_cards = driver.find_elements(
                            By.CSS_SELECTOR, "[class*='joblist-item']"
                        )
                    except:
                        job_cards = []

                current_job_count = len(job_cards)
                self._log(
                    f"  [无限滚动] 当前页面有 {current_job_count} 个职位卡片",
                    level="debug",
                )

                # 检查是否有新数据
                if current_job_count == last_job_count:
                    no_new_count += 1
                    if no_new_count >= 3:
                        self._log(
                            f"  [无限滚动] 连续 {no_new_count} 次无新数据，可能已到达底部"
                        )
                        break
                else:
                    no_new_count = 0

                last_job_count = current_job_count

                # 解析新增的职位
                new_jobs_count = 0
                for i, card in enumerate(job_cards):
                    try:
                        # 获取职位签名用于去重
                        try:
                            title_elem = card.find_element(By.CLASS_NAME, "jname")
                            title = title_elem.text.strip()
                            company_elem = card.find_element(By.CLASS_NAME, "cname")
                            company = company_elem.text.strip()
                            job_signature = f"{title}_{company}"
                        except:
                            continue

                        # 跳过已解析的职位
                        if job_signature in seen_job_signatures:
                            continue

                        seen_job_signatures.add(job_signature)

                        # 解析职位详情
                        job_info = {"title": title, "companyTitle": company}

                        # 薪资
                        try:
                            salary_elem = card.find_element(By.CLASS_NAME, "sal")
                            salary_text = salary_elem.text.strip()
                            job_info["salary"], job_info["salaryMonth"] = (
                                self.parse_salary(salary_text)
                            )
                        except:
                            job_info["salary"] = "薪资面议"
                            job_info["salaryMonth"] = "12薪"

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
                            tags_elem = card.find_element(
                                By.CLASS_NAME, "joblist-item-tags"
                            )
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

                        # 其他字段
                        job_info["companyTags"] = ""
                        job_info["hrWork"] = ""
                        job_info["hrName"] = ""
                        job_info["companyAvatar"] = ""
                        job_info["companyUrl"] = ""
                        job_info["dist"] = ""

                        all_jobs.append(job_info)
                        new_jobs_count += 1

                        # 检查是否达到目标
                        if len(all_jobs) >= target_count:
                            self._log(
                                f"  [无限滚动] 已达到目标数量 {target_count}，停止滚动"
                            )
                            break

                    except Exception as e:
                        self._log(
                            f"  [无限滚动] 解析第 {i + 1} 个职位时出错: {e}",
                            level="error",
                        )
                        continue

                self._log(
                    f"  [无限滚动] 本次解析 {new_jobs_count} 条新数据，累计 {len(all_jobs)} 条"
                )

                # 达到目标数量则退出
                if len(all_jobs) >= target_count:
                    break

                # 如果连续多次没有新数据，提前退出
                if no_new_count >= 3:
                    break

            self._log(
                f"  [无限滚动] 完成，共获取 {len(all_jobs)} 条数据（滚动 {scroll_attempt + 1} 次）"
            )

            if all_jobs:
                self.rate_limiter.report_success()
            else:
                self.rate_limiter.report_failure()

            return all_jobs

        except Exception as e:
            self._log(f"  [无限滚动] 爬取时出错: {e}", level="error")
            self.rate_limiter.report_failure()
            return []

        finally:
            if driver:
                driver.quit()

    def save_to_database(self, jobs: List[Dict]) -> Tuple[int, int]:
        """
        批量保存数据到数据库

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

    def run_crawler_with_checkpoint(
        self,
        keyword: str = "大数据",
        city: str = "",
        pages: int = 5,
        resume: bool = True,
    ) -> Dict:
        """
        运行爬虫（支持断点续传）

        Args:
            keyword: 搜索关键词
            city: 城市
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

                # 使用检查点的参数
                keyword = checkpoint.keyword
                city = checkpoint.city

                # 获取剩余页面
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
        self._log(f"  - 城市: {city or '全国'}")
        self._log(f"  - 页数: {pages}")
        self._log(f"  - 断点续传: {'已启用' if resume else '已禁用'}")
        self._log(f"  - 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 标记为运行中
        self._update_status(
            status="running", keyword=keyword, city=city, total_pages=pages
        )

        # 使用批次计算
        batch_calc = BatchCalculator(total_pages=pages, batch_size=50)
        self._log(
            f"[批次] 共分为 {batch_calc.total_batches} 批，每批约{batch_calc.batch_size}页"
        )

        all_jobs = []

        try:
            for batch_num in range(1, batch_calc.total_batches + 1):
                start_page, end_page = batch_calc.get_batch_range(batch_num)

                # 如果是恢复模式，检查哪些页面还需要爬取
                if resume and checkpoint:
                    pages_in_batch = [
                        p
                        for p in range(start_page, end_page + 1)
                        if not self.checkpoint_manager.is_page_completed(p)
                    ]
                    if not pages_in_batch:
                        self._log(f"\n[批次 {batch_num}] 该批次所有页面已完成，跳过")
                        continue
                    start_page = min(pages_in_batch)
                    end_page = max(pages_in_batch)

                self._log(f"\n{'=' * 70}")
                self._log(
                    f"[批次 {batch_num}/{batch_calc.total_batches}] 页面 {start_page}-{end_page}"
                )
                self._log(f"{'=' * 70}")

                batch_jobs = []
                for page in range(start_page, end_page + 1):
                    self._log(f"\n正在爬取第 {page}/{pages} 页...")

                    jobs = self.crawl_job_list(keyword=keyword, page=page)

                    if jobs:
                        batch_jobs.extend(jobs)
                        all_jobs.extend(jobs)
                        self.stats["pages_processed"] += 1
                        self.stats["records_collected"] += len(jobs)
                        self._log(f"  第 {page} 页成功获取 {len(jobs)} 条职位信息")
                        self._log(
                            f"  本批累计: {len(batch_jobs)} 条 | 总计: {len(all_jobs)} 条"
                        )
                        # 更新进度状态
                        self._update_status(
                            current_page=page, raw_count=self.stats["records_collected"]
                        )
                    else:
                        self._log(f"  第 {page} 页无数据或出错")
                        self.stats["errors"] += 1
                        self._update_status(
                            current_page=page, error_count=self.stats["errors"]
                        )

                    # 保存检查点（每页保存）
                    self.checkpoint_manager.save_checkpoint(
                        keyword=keyword,
                        city=city,
                        current_page=page,
                        total_pages=pages,
                        records_collected=self.stats["records_collected"],
                    )

                    # 页面间延时（最后页不需要）
                    if page < end_page:
                        delay = random.uniform(4, 7)
                        self._log(f"  等待 {delay:.1f} 秒后翻页...")
                        time.sleep(delay)

        except KeyboardInterrupt:
            self._log("\n\n[!] 用户中断爬虫")
            self._log("[断点续传] 进度已保存，下次运行将自动恢复")
            self._mark_error("用户中断")

        except Exception as e:
            self._log(f"\n\n[!] 爬虫异常: {e}")
            self._log("[断点续传] 进度已保存，下次运行将自动恢复")
            self._mark_error(str(e))

        finally:
            # 保存剩余数据
            if all_jobs and len(all_jobs) > self.stats["records_saved"]:
                remaining_jobs = all_jobs[self.stats["records_saved"] :]
                if remaining_jobs:
                    self._log(f"\n[收尾] 保存剩余 {len(remaining_jobs)} 条数据...")
                    saved, skipped = self.save_to_database(remaining_jobs)
                    self.stats["records_saved"] += saved

        return self._get_final_stats()

    def run_crawler_with_click_pagination(
        self,
        keyword: str = "大数据",
        city: str = "",
        pages: int = 5,
        resume: bool = True,
    ) -> Dict:
        """
        【Element UI点击翻页方案】运行爬虫（支持断点续传）

        使用点击分页按钮的方式翻页，适用于 Element UI 分页组件。
        在同一个浏览器实例中连续点击分页，提高效率。

        Args:
            keyword: 搜索关键词
            city: 城市
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

                # 使用检查点的参数
                keyword = checkpoint.keyword
                city = checkpoint.city

                # 获取剩余页面
                remaining_pages = self.checkpoint_manager.get_remaining_pages(1, pages)
                if not remaining_pages:
                    self._log("[断点续传] 所有页面已完成！")
                    return self._get_final_stats()

                self._log(f"[断点续传] 继续爬取 {len(remaining_pages)} 个剩余页面")

        self._log("=" * 70)
        self._log("前程无忧爬虫启动 [Element UI 点击翻页方案]")
        self._log("=" * 70)
        self._log(f"\n配置:")
        self._log(f"  - 关键词: {keyword}")
        self._log(f"  - 城市: {city or '全国'}")
        self._log(f"  - 页数: {pages}")
        self._log(f"  - 断点续传: {'已启用' if resume else '已禁用'}")
        self._log(f"  - 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 标记为运行中
        self._update_status(
            status="running", keyword=keyword, city=city, total_pages=pages
        )

        all_jobs = []
        driver = None

        try:
            # 创建 driver 实例（只创建一次）
            driver = self.create_driver()
            wait = WebDriverWait(driver, 15)

            # 访问第一页
            url = f"{self.base_url}?keyword={keyword}"
            self._log(f"[初始化] 访问第一页: {url}")
            driver.get(url)

            # 等待初始页面加载
            time.sleep(random.uniform(3, 5))

            # 检查是否被重定向
            current_url = driver.current_url
            if "we.51job.com" not in current_url:
                self._log(f"[错误] 页面被重定向！可能遇到反爬验证", level="error")
                return self._get_final_stats()

            self._log(f"[初始化] 页面加载完成")

            # 连续爬取多页
            for page in range(1, pages + 1):
                # 如果是恢复模式，检查该页是否已完成
                if (
                    resume
                    and checkpoint
                    and self.checkpoint_manager.is_page_completed(page)
                ):
                    self._log(f"\n[跳过] 第 {page} 页已完成")
                    # 如果不是最后一页，点击下一页
                    if page < pages:
                        self._click_next_page(driver, page + 1)
                    continue

                self._log(f"\n{'=' * 70}")
                self._log(f"[页面 {page}/{pages}] 正在爬取...")
                self._log(f"{'=' * 70}")

                # 如果不是第一页，点击分页按钮
                if page > 1:
                    success = self._click_next_page(driver, page)
                    if not success:
                        self._log(
                            f"[错误] 无法翻页到第 {page} 页，停止爬取", level="error"
                        )
                        break

                # 滚动加载内容
                for _ in range(3):
                    driver.execute_script("window.scrollBy(0, 400)")
                    time.sleep(0.5)

                # 解析当前页职位
                jobs = self._parse_current_page(driver, wait, keyword)

                if jobs:
                    all_jobs.extend(jobs)
                    self.stats["pages_processed"] += 1
                    self.stats["records_collected"] += len(jobs)
                    self._log(f"[页面 {page}] 成功获取 {len(jobs)} 条职位信息")
                    self._log(f"[累计] 总计: {len(all_jobs)} 条")

                    # 更新进度状态
                    self._update_status(
                        current_page=page, raw_count=self.stats["records_collected"]
                    )

                    # 保存到数据库（每页保存，避免数据丢失）
                    saved, skipped = self.save_to_database(jobs)
                    self.stats["records_saved"] += saved
                    self._log(f"[保存] 保存成功: {saved} 条 | 跳过重复: {skipped} 条")
                    self._update_status(saved_count=self.stats["records_saved"])
                else:
                    self._log(f"[页面 {page}] 无数据或出错", level="warning")
                    self.stats["errors"] += 1
                    self._update_status(
                        current_page=page, error_count=self.stats["errors"]
                    )

                # 保存检查点
                self.checkpoint_manager.save_checkpoint(
                    keyword=keyword,
                    city=city,
                    current_page=page,
                    total_pages=pages,
                    records_collected=self.stats["records_collected"],
                )

                # 页面间延时（最后页不需要）
                if page < pages:
                    delay = random.uniform(4, 7)
                    self._log(f"[延时] 等待 {delay:.1f} 秒后翻页...")
                    time.sleep(delay)

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

        return self._get_final_stats()

    def _click_next_page(self, driver, target_page: int) -> bool:
        """
        点击分页按钮翻页

        Args:
            driver: Selenium WebDriver 实例
            target_page: 目标页码

        Returns:
            bool: 是否成功翻页
        """
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
        """
        获取第一条职位的签名（用于验证数据是否更新）

        Args:
            driver: Selenium WebDriver 实例

        Returns:
            str: 职位签名（标题_公司）
        """
        try:
            first_card = driver.find_element(By.CLASS_NAME, "joblist-item-job")
            title_elem = first_card.find_element(By.CLASS_NAME, "jname")
            company_elem = first_card.find_element(By.CLASS_NAME, "cname")
            return f"{title_elem.text.strip()}_{company_elem.text.strip()}"
        except:
            return ""

    def _parse_current_page(self, driver, wait, keyword: str) -> List[Dict]:
        """
        解析当前页面的职位列表

        Args:
            driver: Selenium WebDriver 实例
            wait: WebDriverWait 实例
            keyword: 搜索关键词

        Returns:
            List[Dict]: 职位信息列表
        """
        try:
            # 获取职位卡片
            try:
                job_cards = wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CLASS_NAME, "joblist-item-job")
                    )
                )
            except:
                job_cards = driver.find_elements(
                    By.CSS_SELECTOR, "[class*='joblist-item']"
                )

            if not job_cards:
                self._log("  未找到职位卡片", level="warning")
                return []

            self._log(f"  找到 {len(job_cards)} 个职位卡片")

            jobs = []
            for i, card in enumerate(job_cards):
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
                        tags_elem = card.find_element(
                            By.CLASS_NAME, "joblist-item-tags"
                        )
                        tags_text = tags_elem.text.strip()
                        job_info["workTag"] = tags_text
                        job_info["educational"], job_info["workExperience"] = (
                            self.parse_education_and_experience(tags_text)
                        )
                    except:
                        job_info["workTag"] = ""
                        job_info["educational"] = "学历不限"
                        job_info["workExperience"] = "经验不限"

                    # 岗位类型和其他字段
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

                    # 其他字段
                    job_info["companyTags"] = ""
                    job_info["hrWork"] = ""
                    job_info["hrName"] = ""
                    job_info["companyAvatar"] = ""
                    job_info["companyUrl"] = ""
                    job_info["dist"] = ""

                    jobs.append(job_info)

                except Exception as e:
                    self._log(f"  解析第 {i + 1} 个职位卡片时出错: {e}", level="error")
                    continue

            if jobs:
                self.rate_limiter.report_success()
            else:
                self.rate_limiter.report_failure()

            return jobs

        except Exception as e:
            self._log(f"  解析页面时出错: {e}", level="error")
            self.rate_limiter.report_failure()
            return []

        return self._get_final_stats()

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

        # 标记为完成（如果还没有标记为错误）
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


def save_to_database(jobs):
    """
    独立函数：保存职位数据到数据库（向后兼容）

    Args:
        jobs: 职位数据列表

    Returns:
        tuple: (保存成功数, 跳过重复数)
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
                print(f"  保存数据时出错: {e}")
                continue

    return saved_count, skipped_count


def run_crawler(
    keyword: str = "大数据",
    city: str = "",
    pages: int = 5,
    resume: bool = True,
    headless: bool = True,
    run_store: Optional[CrawlRunStore] = None,
    run_id: Optional[str] = None,
) -> Dict:
    """
    运行爬虫主函数（便捷接口）

    Args:
        keyword: 搜索关键词
        city: 城市
        pages: 爬取页数
        resume: 是否启用断点续传
        headless: 是否使用无头模式（默认True）。设为False显示浏览器窗口用于调试
        run_store: 运行存储管理器（用于Web UI进度跟踪）
        run_id: 运行ID（用于Web UI进度跟踪）

    Returns:
        Dict: 爬取统计信息
    """
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
    # 命令行接口
    import argparse

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
