#!/usr/bin/env python3
"""
51job API爬虫 - 直接调用AJAX接口

基于Playwright探索发现的真实API：
https://we.51job.com/api/job/search-pc?api_key=51job&timestamp={ts}&keyword={kw}&pageNum={page}&pageSize=20&...

使用方法：
    python crawler/job51_api_crawler.py --keyword 大数据 --pages 5
"""

import argparse
import json
import random
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests


def generate_timestamp() -> int:
    """生成时间戳"""
    return int(time.time())


def generate_request_id() -> str:
    """生成请求ID"""
    import uuid

    return hashlib.md5(uuid.uuid4().hex.encode()).hexdigest()


def build_search_url(
    keyword: str,
    page: int = 1,
    job_area: str = "",
    page_size: int = 20,
) -> str:
    """
    构建搜索API URL

    Args:
        keyword: 搜索关键词
        page: 页码（从1开始）
        job_area: 城市代码（如020000表示上海）
        page_size: 每页数量

    Returns:
        完整的API URL
    """
    timestamp = generate_timestamp()
    request_id = generate_request_id()

    params = {
        "api_key": "51job",
        "timestamp": timestamp,
        "keyword": keyword,
        "searchType": 2,
        "function": "",
        "industry": "",
        "jobArea": job_area,
        "jobArea2": "",
        "landmark": "",
        "metro": "",
        "salary": "",
        "workYear": "",
        "degree": "",
        "companyType": "",
        "companySize": "",
        "jobType": "",
        "issueDate": "",
        "sortType": 0,
        "pageNum": page,
        "requestId": request_id,
        "pageSize": page_size,
        "source": 1,
        "accountId": "",
        "pageCode": "sou|sou|soulb",
        "scene": 7,
    }

    # 构建URL
    base_url = "https://we.51job.com/api/job/search-pc"
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"


def parse_salary(salary_text: str) -> Tuple[str, str]:
    """解析薪资文本"""
    if not salary_text or salary_text == "薪资面议":
        return "薪资面议", "12薪"

    # 处理类似 "1.5-2.5万·13薪" 或 "20-30万·15薪" 的格式
    import re

    # 提取薪资金额部分和发放月数部分
    salary_match = re.search(r"([\d\.]+)(?:-([\d\.]+))?万", salary_text)
    month_match = re.search(r"(\d+)薪", salary_text)

    if salary_match:
        min_salary = salary_match.group(1)
        max_salary = salary_match.group(2) if salary_match.group(2) else min_salary
        salary_str = f"{min_salary}-{max_salary}万"
    else:
        salary_str = salary_text

    # 提取发放月数
    if month_match:
        salary_month = f"{month_match.group(1)}薪"
    else:
        salary_month = "12薪"

    return salary_str, salary_month


def parse_company_info(info_text: str) -> Tuple[str, str, str]:
    """解析公司信息"""
    parts = [p.strip() for p in info_text.split("|")]

    nature = parts[0] if len(parts) > 0 else "未知"
    people = parts[1] if len(parts) > 1 else "未知"
    status = parts[2] if len(parts) > 2 else "未知"

    return nature, people, status


def parse_education_and_experience(tags_text: str) -> Tuple[str, str]:
    """解析学历和工作经验"""
    parts = [p.strip() for p in tags_text.split("|")]

    educational = "学历不限"
    work_experience = "经验不限"

    for part in parts:
        if (
            "学历" in part
            or "博士" in part
            or "硕士" in part
            or "本科" in part
            or "大专" in part
        ):
            educational = part
        elif "经验" in part or "年" in part:
            work_experience = part

    return educational, work_experience


def crawl_page_api(
    keyword: str,
    page: int = 1,
    job_area: str = "",
    session: Optional[requests.Session] = None,
) -> List[Dict]:
    """
    使用API爬取单页职位数据

    Args:
        keyword: 搜索关键词
        page: 页码
        job_area: 城市代码
        session: requests.Session对象（用于保持连接）

    Returns:
        职位数据列表
    """
    if session is None:
        session = requests.Session()

    url = build_search_url(keyword, page, job_area)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://we.51job.com/pc/search",
        "Connection": "keep-alive",
    }

    try:
        print(f"  [API] 请求第 {page} 页...")
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        # 检查响应状态
        if data.get("status") != "1":
            print(f"  [警告] API返回错误状态: {data.get('status')}")
            return []

        # 解析职位列表
        jobs = []
        job_list = (
            data.get("resultbody", {}).get("search", {}).get("job", {}).get("items", [])
        )

        if not job_list:
            print(f"  [警告] 第 {page} 页没有数据")
            return []

        for item in job_list:
            try:
                job_info = {
                    "title": item.get("job_name", ""),
                    "companyTitle": item.get("company_name", ""),
                    "salary": item.get("providesalary_text", "薪资面议"),
                    "salaryMonth": "12薪",
                    "address": item.get("job_area", ""),
                    "companyNature": item.get("companytype_text", "未知"),
                    "companyPeople": item.get("companysize_text", "未知"),
                    "companyStatus": item.get("company_status", "未知"),
                    "workTag": " | ".join(
                        filter(
                            None,
                            [
                                item.get("attribute_text", ["", ""])[0]
                                if len(item.get("attribute_text", [])) > 0
                                else "",
                                item.get("attribute_text", ["", ""])[1]
                                if len(item.get("attribute_text", [])) > 1
                                else "",
                            ],
                        )
                    ),
                    "educational": item.get("attribute_text", ["学历不限", ""])[0]
                    if len(item.get("attribute_text", [])) > 0
                    else "学历不限",
                    "workExperience": item.get("attribute_text", ["", "经验不限"])[1]
                    if len(item.get("attribute_text", [])) > 1
                    else "经验不限",
                    "type": keyword,
                    "pratice": "实习" in item.get("job_name", ""),
                    "detailUrl": item.get("job_href", ""),
                    "companyTags": "",
                    "hrWork": "",
                    "hrName": "",
                    "companyAvatar": "",
                    "companyUrl": "",
                    "dist": "",
                }

                # 解析薪资
                salary_text = item.get("providesalary_text", "")
                if salary_text and salary_text != "薪资面议":
                    job_info["salary"], job_info["salaryMonth"] = parse_salary(
                        salary_text
                    )

                jobs.append(job_info)

            except Exception as e:
                print(f"  [错误] 解析职位数据时出错: {e}")
                continue

        print(f"  [API] 第 {page} 页获取到 {len(jobs)} 条数据")
        return jobs

    except requests.exceptions.RequestException as e:
        print(f"  [错误] 请求API时出错: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"  [错误] 解析JSON响应时出错: {e}")
        return []


def crawl_jobs_api(
    keyword: str = "大数据",
    pages: int = 5,
    job_area: str = "",
    delay_range: Tuple[float, float] = (1, 3),
) -> List[Dict]:
    """
    使用API爬取多页职位数据

    Args:
        keyword: 搜索关键词
        pages: 爬取页数
        job_area: 城市代码
        delay_range: 请求间隔范围（秒）

    Returns:
        所有职位数据列表
    """
    print("=" * 70)
    print("51job API爬虫启动")
    print("=" * 70)
    print(f"\n配置:")
    print(f"  - 关键词: {keyword}")
    print(f"  - 页数: {pages}")
    print(f"  - 城市代码: {job_area or '全国'}")
    print()

    session = requests.Session()
    all_jobs = []

    for page in range(1, pages + 1):
        jobs = crawl_page_api(keyword, page, job_area, session)

        if jobs:
            all_jobs.extend(jobs)
            print(f"  累计: {len(all_jobs)} 条")
        else:
            print(f"  第 {page} 页无数据，停止爬取")
            break

        # 延时（最后一页不需要）
        if page < pages:
            delay = random.uniform(*delay_range)
            print(f"  等待 {delay:.1f} 秒...")
            time.sleep(delay)

    print()
    print("=" * 70)
    print(f"爬取完成！共获取 {len(all_jobs)} 条数据")
    print("=" * 70)

    return all_jobs


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="51job API爬虫")
    parser.add_argument("--keyword", default="大数据", help="搜索关键词")
    parser.add_argument("--pages", type=int, default=5, help="爬取页数")
    parser.add_argument("--city-code", default="", help="城市代码（如020000表示上海）")
    parser.add_argument(
        "--min-delay", type=float, default=1.0, help="最小请求间隔（秒）"
    )
    parser.add_argument(
        "--max-delay", type=float, default=3.0, help="最大请求间隔（秒）"
    )

    args = parser.parse_args()

    jobs = crawl_jobs_api(
        keyword=args.keyword,
        pages=args.pages,
        job_area=args.city_code,
        delay_range=(args.min_delay, args.max_delay),
    )

    # 保存到JSON文件
    if jobs:
        filename = (
            f"51job_{args.keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"\n数据已保存到: {filename}")


if __name__ == "__main__":
    main()
