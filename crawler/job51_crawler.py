#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
前程无忧爬虫模块
集成断点续传、批量控制、自适应限速功能
用于大规模数据爬取（20000+记录）
"""

import json
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

    def crawl_job_list(self, keyword="大数据", page=1) -> List[Dict]:
        """
        爬取职位列表

        Returns:
            List[Dict]: 职位信息列表
        """
        driver = None
        try:
            # 自适应限速
            self.rate_limiter.wait()

            driver = self.create_driver()
            wait = WebDriverWait(driver, 15)

            # 构建URL
            if page == 1:
                url = f"{self.base_url}?keyword={keyword}"
            else:
                url = f"{self.base_url}?keyword={keyword}&page={page}"

            print(f"  访问: {url}")
            driver.get(url)

            # 等待页面加载
            time.sleep(random.uniform(3, 5))

            # 【调试输出】显示当前页面信息
            current_url = driver.current_url
            page_title = driver.title
            print(f"  [调试] 当前URL: {current_url}")
            print(f"  [调试] 页面标题: {page_title}")

            # 如果URL发生变化，可能被重定向到验证页面
            if "we.51job.com" not in current_url:
                print(f"  [警告] 页面被重定向！可能遇到反爬验证")
                return []

            # 滚动页面以加载所有内容
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 400)")
                time.sleep(0.5)

            # 获取所有职位卡片
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
                    print("  未找到职位卡片")
                    self.rate_limiter.report_failure()
                    return []

            print(f"  找到 {len(job_cards)} 个职位卡片")

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

                    # 是否实习
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
                    print(f"  解析第 {i + 1} 个职位卡片时出错: {e}")
                    continue

            # 报告成功
            if jobs:
                self.rate_limiter.report_success()
            else:
                self.rate_limiter.report_failure()

            return jobs

        except Exception as e:
            print(f"  爬取页面时出错: {e}")
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
                    print(f"  保存数据时出错: {e}")
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
                print(f"[断点续传] 发现之前的进度: 第{checkpoint.current_page}页")
                print(f"[断点续传] 已完成页面: {len(checkpoint.completed_pages)}页")

                # 使用检查点的参数
                keyword = checkpoint.keyword
                city = checkpoint.city

                # 获取剩余页面
                remaining_pages = self.checkpoint_manager.get_remaining_pages(1, pages)
                if not remaining_pages:
                    print("[断点续传] 所有页面已完成！")
                    return self._get_final_stats()

                print(f"[断点续传] 继续爬取 {len(remaining_pages)} 个剩余页面")

        print("=" * 70)
        print("前程无忧爬虫启动")
        print("=" * 70)
        print(f"\n配置:")
        print(f"  - 关键词: {keyword}")
        print(f"  - 城市: {city or '全国'}")
        print(f"  - 页数: {pages}")
        print(f"  - 断点续传: {'已启用' if resume else '已禁用'}")
        print(f"  - 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 使用批次计算
        batch_calc = BatchCalculator(total_pages=pages, batch_size=50)
        print(
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
                        print(f"\n[批次 {batch_num}] 该批次所有页面已完成，跳过")
                        continue
                    start_page = min(pages_in_batch)
                    end_page = max(pages_in_batch)

                print(f"\n{'=' * 70}")
                print(
                    f"[批次 {batch_num}/{batch_calc.total_batches}] 页面 {start_page}-{end_page}"
                )
                print(f"{'=' * 70}")

                batch_jobs = []
                for page in range(start_page, end_page + 1):
                    print(f"\n正在爬取第 {page}/{pages} 页...")

                    jobs = self.crawl_job_list(keyword=keyword, page=page)

                    if jobs:
                        batch_jobs.extend(jobs)
                        all_jobs.extend(jobs)
                        self.stats["pages_processed"] += 1
                        self.stats["records_collected"] += len(jobs)
                        print(f"  第 {page} 页成功获取 {len(jobs)} 条职位信息")
                        print(
                            f"  本批累计: {len(batch_jobs)} 条 | 总计: {len(all_jobs)} 条"
                        )
                    else:
                        print(f"  第 {page} 页无数据或出错")

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
                        print(f"  等待 {delay:.1f} 秒后翻页...")
                        time.sleep(delay)

                # 批次完成，保存到数据库
                if batch_jobs:
                    print(f"\n[批次 {batch_num}] 保存数据到数据库...")
                    saved, skipped = self.save_to_database(batch_jobs)
                    self.stats["records_saved"] += saved
                    print(f"  保存成功: {saved} 条 | 跳过重复: {skipped} 条")

                # 批次间休息（除最后一批）
                if batch_num < batch_calc.total_batches:
                    rest_time = random.uniform(300, 600)  # 5-10分钟
                    print(
                        f"\n[休息] 批次 {batch_num} 完成，休息 {rest_time / 60:.1f} 分钟..."
                    )
                    print(f"[进度] {batch_calc.get_progress(batch_num):.1f}% 完成")
                    time.sleep(rest_time)

        except KeyboardInterrupt:
            print("\n\n[!] 用户中断爬虫")
            print("[断点续传] 进度已保存，下次运行将自动恢复")

        except Exception as e:
            print(f"\n\n[!] 爬虫异常: {e}")
            print("[断点续传] 进度已保存，下次运行将自动恢复")

        finally:
            # 保存剩余数据
            if all_jobs and len(all_jobs) > self.stats["records_saved"]:
                remaining_jobs = all_jobs[self.stats["records_saved"] :]
                if remaining_jobs:
                    print(f"\n[收尾] 保存剩余 {len(remaining_jobs)} 条数据...")
                    saved, skipped = self.save_to_database(remaining_jobs)
                    self.stats["records_saved"] += saved

        return self._get_final_stats()

    def _get_final_stats(self) -> Dict:
        """获取最终统计信息"""
        elapsed = (
            time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        )

        print(f"\n{'=' * 70}")
        print("爬取完成！")
        print(f"{'=' * 70}")
        print(f"统计信息:")
        print(f"  - 处理页面: {self.stats['pages_processed']} 页")
        print(f"  - 采集记录: {self.stats['records_collected']} 条")
        print(f"  - 保存记录: {self.stats['records_saved']} 条")
        print(f"  - 运行时间: {elapsed / 60:.1f} 分钟")
        if self.stats["pages_processed"] > 0:
            print(f"  - 平均速度: {elapsed / self.stats['pages_processed']:.1f} 秒/页")
        print(f"{'=' * 70}")

        # 完成后清除检查点
        self.checkpoint_manager.clear_checkpoint()

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
) -> Dict:
    """
    运行爬虫主函数（便捷接口）

    Args:
        keyword: 搜索关键词
        city: 城市
        pages: 爬取页数
        resume: 是否启用断点续传
        headless: 是否使用无头模式（默认True）。设为False显示浏览器窗口用于调试

    Returns:
        Dict: 爬取统计信息
    """
    crawler = Job51Crawler(headless=headless)
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
