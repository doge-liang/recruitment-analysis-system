#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
爬虫脚本注册表
自动发现 crawler/ 目录下的有效爬虫脚本
"""

import ast
import os
import importlib
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional

# 排除的非爬虫文件/目录
EXCLUDED_FILES = {
    "__init__.py",
    "checkpoint_manager.py",
    "registry.py",
}

EXCLUDED_DIRS = {
    "tests",
    "__pycache__",
}


def _get_crawler_dir() -> Path:
    """获取爬虫目录路径"""
    return Path(__file__).resolve().parent


def _is_excluded(name: str, path: Path) -> bool:
    """检查是否应该排除该文件"""
    if name in EXCLUDED_FILES:
        return True
    if path.is_dir() and name in EXCLUDED_DIRS:
        return True
    return False


def _has_run_crawler_function(file_path: Path) -> bool:
    """
    使用 AST 检查文件是否定义了 run_crawler 函数
    不执行代码，只解析语法树
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_crawler":
                return True
        return False
    except Exception:
        return False


def _get_module_description_from_source(file_path: Path) -> str:
    """从源码中获取模块描述（docstring）"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        # 获取模块级别的 docstring
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, (ast.Str, ast.Constant))
        ):
            doc = tree.body[0].value
            if isinstance(doc, ast.Constant):
                doc = doc.value
            if isinstance(doc, str):
                first_line = doc.strip().split("\n")[0].strip()
                # 去除 Python docstring 格式
                for quote in ('"""', "'''"):
                    if first_line.startswith(quote) and first_line.endswith(quote):
                        first_line = first_line[3:-3].strip()
                        break
                return first_line
        return ""
    except Exception:
        return ""


def is_valid_crawler(script_name: str) -> bool:
    """
    验证是否是有效爬虫（必须有 run_crawler 函数）

    Args:
        script_name: 脚本文件名，如 "job51_crawler.py"

    Returns:
        bool: 是否为有效爬虫
    """
    if not script_name.endswith(".py"):
        script_name += ".py"

    crawler_dir = _get_crawler_dir()
    script_path = crawler_dir / script_name

    if not script_path.exists():
        return False

    return _has_run_crawler_function(script_path)


def get_crawler_module(script_name: str):
    """
    获取爬虫模块对象

    Args:
        script_name: 脚本文件名，如 "job51_crawler.py"

    Returns:
        module: 模块对象

    Raises:
        FileNotFoundError: 脚本不存在
        ValueError: 不是有效爬虫
        ImportError: 导入失败
    """
    if not script_name.endswith(".py"):
        script_name += ".py"

    crawler_dir = _get_crawler_dir()
    script_path = crawler_dir / script_name

    if not script_path.exists():
        raise ValueError(f"脚本不存在: {script_path}")

    if not is_valid_crawler(script_name):
        raise ValueError(f"不是有效爬虫脚本（缺少 run_crawler 函数）: {script_name}")

    module_name = script_name[:-3]
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {script_name}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def _get_module_description(module) -> str:
    """从模块的 docstring 中获取描述"""
    doc = getattr(module, "__doc__", None)
    if doc:
        first_line = doc.strip().split("\n")[0].strip()
        for quote in ('"""', "'''"):
            if first_line.startswith(quote) and first_line.endswith(quote):
                first_line = first_line[3:-3].strip()
                break
        return first_line.strip()
    return ""


def list_crawlers() -> List[Dict[str, Any]]:
    """
    返回可用爬虫脚本列表

    Returns:
        List[Dict]: 爬虫信息列表，每项包含:
            - name: 脚本文件名
            - module: 模块路径（crawler.xxx）
            - description: 脚本描述
    """
    crawler_dir = _get_crawler_dir()
    crawlers = []

    for item in crawler_dir.iterdir():
        name = item.name

        # 只处理 .py 文件
        if not name.endswith(".py"):
            continue

        # 排除
        if _is_excluded(name, item):
            continue

        # 验证是否是有效爬虫
        if is_valid_crawler(name):
            description = _get_module_description_from_source(item)
            crawlers.append(
                {
                    "name": name,
                    "module": f"crawler.{name[:-3]}",
                    "description": description,
                }
            )

    return crawlers


if __name__ == "__main__":
    # 测试
    print("可用爬虫列表:")
    for crawler in list_crawlers():
        print(f"  - {crawler['name']}: {crawler['description']}")
