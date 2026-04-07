# AGENTS.md - Coding Guidelines for Agentic Agents

> Auto-generated from codebase analysis for the 大数据人才招聘分析系统 (Big Data Recruitment Analysis System)

## Project Overview

- **Framework**: Django 3.2+ with Python 3.8-3.10
- **Database**: MySQL (production) / SQLite (development)
- **Environment**: Conda environment `recruitment`
- **Testing**: Django TestCase + pytest with Playwright for E2E
- **Main Apps**: `myApp` (core), `crawler` (scraping), `ml_model` (ML)

## Build/Test/Lint Commands

```bash
# Setup
conda create -n recruitment python=3.10
conda activate recruitment
pip install -r requirements.txt

# Run development server
python manage.py runserver          # Default port 8000
python manage.py runserver 0.0.0.0:8000

# Database operations
python manage.py migrate            # Run migrations
python manage.py makemigrations     # Create migrations
python manage.py createsuperuser    # Create admin user

# Testing - Django
python manage.py test                           # Run all Django tests
python manage.py test myApp.tests               # Run myApp tests
python manage.py test myApp.tests.test_auth     # Run single test file
python manage.py test myApp.tests.test_auth.AuthTests.test_login_success  # Single test

# Testing - pytest with Playwright
pytest crawler/tests/test_crawler_admin_playwright.py -v --tb=short
pytest crawler/tests/ -v                          # All crawler tests
bash run_playwright_tests.sh                      # Run via script

# Crawler operations
python crawler/job51_crawler.py --keyword "大数据" --pages 5
python crawler/job51_crawler.py --keyword "数据分析" --pages 100 --no-resume

# ML model training
cd ml_model && python salary_predictor.py

# Data import
python import_jobs.py               # Import CSV data
```

## Code Style Guidelines

### Imports (strict order)

```python
# 1. Standard library
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 2. Third-party packages
import django
import numpy as np
import pandas as pd
from selenium import webdriver
from sklearn.ensemble import RandomForestRegressor

# 3. Django imports
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404

# 4. Local imports (absolute preferred)
from myApp.models import JobInfo, History, UserProfile
from crawler.checkpoint_manager import CheckpointManager
```

### Naming Conventions

- **Variables/Functions**: `snake_case` (e.g., `get_salary_avg`, `checkpoint_file`)
- **Classes**: `PascalCase` (e.g., `CheckpointManager`, `SalaryPredictor`)
- **Constants**: `UPPER_CASE` (e.g., `BASE_DIR`, `MAX_DELAY`)
- **Private**: `_leading_underscore` for internal use
- **Django models**: `PascalCase` with Chinese `verbose_name`

### String Formatting

```python
# Use double quotes (Django convention)
name = "大数据"
path = "/myApp/login/"

# f-strings for interpolation
message = f"爬虫已启动: {keyword} {city} {pages}页"

# .format() for complex formatting
error = "参数错误: {}".format(str(e))
```

### Django Patterns

```python
# Models: Chinese verbose_name, db_table defined
class JobInfo(models.Model):
    """招聘信息模型"""
    title = models.CharField(max_length=200, verbose_name="职位名称")
    createTime = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "jobinfo"
        verbose_name = "招聘信息"
        ordering = ["-createTime"]

    def __str__(self):
        return f"{self.title} - {self.companyTitle}"

# Views: @login_required, JsonResponse for APIs
@login_required
def salary_data_api(request):
    """薪资分析API"""
    data = {"bar_data": [], "pie_data": []}
    return JsonResponse(data)

# URL patterns: app_name required
app_name = "myApp"
urlpatterns = [
    path("salary/", views.salary_view, name="salary"),
]
```

### Comments & Docstrings

```python
# Chinese comments for business logic understanding
"""
前程无忧爬虫模块
集成断点续传、批量控制、自适应限速功能
"""

# Section dividers for organization
# ==================== 用户认证 ====================

# Type hints encouraged for complex functions
def parse_salary(salary_str: str) -> Tuple[int, int]:
    """解析薪资字符串，返回最低、最高薪资（单位：K）"""
    pass
```

### Error Handling

```python
# Use specific exceptions
try:
    checkpoint = manager.load_checkpoint()
except json.JSONDecodeError as e:
    logger.error(f"检查点解析错误: {e}")
    return None
except FileNotFoundError:
    return None

# Django: return JsonResponse for API errors
return JsonResponse({"error": "权限不足", "success": False}, status=403)
```

### Testing Patterns

```python
# Django TestCase
class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="test", password="pass")

    def test_login_success(self):
        response = self.client.post("/myApp/login/", {...})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/myApp/index/")

# pytest with Playwright
@pytest.fixture
def login_as_admin(page: Page):
    page.goto("http://localhost:8000/myApp/login/")
    page.fill("[name=username]", "admin")
    yield page

def test_admin_page_loads(self, page: Page, login_as_admin):
    expect(page).to_have_title("爬虫管理 - 招聘信息分析系统")
```

## Special Files & Directories

- `crawler/` - Selenium-based web scrapers with checkpoint/resume
  - `job51_crawler.py` - Main crawler with city selection and CAPTCHA detection
  - `checkpoint_manager.py` - Checkpoint/resume functionality
  - `registry.py` - Crawler registration system
  - `run_store.py` - Runtime state management
- `ml_model/` - scikit-learn models (salary prediction, job recommendation)
- `myApp/` - Core Django application
- `templates/` - HTML templates (Django template engine)
- `static/` - CSS/JS assets (ECharts, etc.)
- `tests/` - Standalone test directory
- `docs/` - Documentation (Chinese)
- `archive/` - Data archive directory

## Environment Notes

- Selenium requires GUI environment (Windows/Linux desktop, or WSL2+Win Chrome)
- Docker MySQL for production-like environment
- Conda environment `recruitment` required for testing

## Crawler Architecture (Job51Crawler)

The crawler has been refactored for efficiency and maintainability:

### Core Methods
- `run_crawler_with_checkpoint()` - Main entry point with resume support
- `_select_city(driver, wait, city)` - Click-based city selection (51job uses UI clicks, not URL params)
- `_check_and_handle_captcha()` - Detects CAPTCHA and prompts for manual completion
- `_run_crawl_session()` - Single browser session for all pages (50 pages max per search)
- `_click_next_page()` - Element UI pagination click handler
- `_parse_current_page()` - Job card extraction and parsing

### Key Features
- **Browser Reuse**: One driver instance per crawl session (not per page)
- **City Selection**: Page element clicking for city filtering
- **CAPTCHA Handling**: Automatic detection with user prompt for manual solving
- **Checkpoint System**: Resume interrupted crawls via `checkpoint_manager.py`
- **Rate Limiting**: Built-in delays and adaptive speed control

### Recent Refactoring (2025-04)
- Code reduced by 45% (2087 → 1288 lines)
- Removed dead code: infinite scroll, single-page methods
- Unified parsing and navigation logic
- Simplified batch handling (51job limits to 50 pages per search)
