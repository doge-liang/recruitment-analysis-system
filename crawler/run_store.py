"""
爬虫运行时文件存储管理模块

提供原子性 JSON 写入、增量日志读取、运行历史清理等功能。
文件结构：
    runtime/crawler/
        current_run.json          -> 指向当前运行
        runs/
            {run_id}/
                status.json       -> 结构化进度数据
                crawler.log       -> 爬虫日志

使用示例：
    store = CrawlRunStore()
    run_id = store.create_run('job51', keyword='大数据', city='', pages=5)
    store.update_status(run_id, current_page=1, raw_count=10)
    logs, cursor = store.read_new_logs(run_id, cursor=0)
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging


def get_base_dir() -> Path:
    """获取项目根目录"""
    # 从当前文件向上找两级（crawler/run_store.py -> crawler/ -> BASE_DIR）
    current_file = Path(__file__).resolve()
    return current_file.parent.parent


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """
    原子性地写入 JSON 文件

    使用临时文件 + rename 确保写入的原子性，避免并发读取时读到损坏的 JSON。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 使用临时文件写入
    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 原子性替换
        os.replace(temp_path, path)
    except Exception:
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def read_json_safe(path: Path, default: Optional[Any] = None) -> Any:
    """
    安全地读取 JSON 文件

    如果文件不存在或读取失败，返回默认值。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def generate_run_id(crawler_slug: str) -> str:
    """
    生成运行 ID

    格式: {crawler_slug}_{YYYYMMDD}_{HHMMSS}_{short_uuid}
    示例: job51_20260407_153045_ab12cd34
    """
    now = datetime.now()
    short_uuid = uuid.uuid4().hex[:8]
    return f"{crawler_slug}_{now.strftime('%Y%m%d_%H%M%S')}_{short_uuid}"


class CrawlRunStore:
    """
    爬虫运行存储管理器

    管理运行时文件的创建、更新、读取和清理。
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        初始化存储管理器

        Args:
            base_dir: 项目根目录，默认为自动检测
        """
        if base_dir is None:
            base_dir = get_base_dir()
        self.base_dir = Path(base_dir)
        self.runtime_dir = self.base_dir / "runtime" / "crawler"
        self.runs_dir = self.runtime_dir / "runs"
        self.current_run_file = self.runtime_dir / "current_run.json"

        # 确保目录存在
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _get_run_dir(self, run_id: str) -> Path:
        """获取指定运行 ID 的目录路径"""
        return self.runs_dir / run_id

    def _get_status_path(self, run_id: str) -> Path:
        """获取状态文件路径"""
        return self._get_run_dir(run_id) / "status.json"

    def _get_log_path(self, run_id: str) -> Path:
        """获取日志文件路径"""
        return self._get_run_dir(run_id) / "crawler.log"

    def create_run(
        self,
        crawler: str,
        keyword: str = "",
        city: str = "",
        pages: int = 0,
        headless: bool = True,
    ) -> str:
        """
        创建新的运行记录

        Args:
            crawler: 爬虫脚本名称（如 'job51_crawler.py'）
            keyword: 搜索关键词
            city: 搜索城市
            pages: 总页数
            headless: 是否无头模式

        Returns:
            run_id: 新生成的运行 ID
        """
        # 生成运行 ID
        crawler_slug = crawler.replace(".py", "").replace("_crawler", "")
        run_id = generate_run_id(crawler_slug)

        # 创建运行目录
        run_dir = self._get_run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat()

        # 初始状态
        status = {
            "run_id": run_id,
            "crawler": crawler,
            "status": "starting",
            "keyword": keyword,
            "city": city,
            "total_pages": pages,
            "current_page": 0,
            "raw_count": 0,
            "saved_count": 0,
            "error_count": 0,
            "headless": headless,
            "error": "",
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
        }

        # 写入状态文件
        atomic_write_json(self._get_status_path(run_id), status)

        # 创建空日志文件
        log_path = self._get_log_path(run_id)
        log_path.touch()

        # 更新当前运行指针
        current_run = {"run_id": run_id, "started_at": now}
        atomic_write_json(self.current_run_file, current_run)

        return run_id

    def update_status(self, run_id: str, **fields) -> None:
        """
        更新运行状态

        Args:
            run_id: 运行 ID
            **fields: 要更新的字段（如 current_page=1, raw_count=10）
        """
        status_path = self._get_status_path(run_id)
        status = read_json_safe(status_path, {})

        # 更新字段
        status.update(fields)
        status["updated_at"] = datetime.now().isoformat()

        atomic_write_json(status_path, status)

    def mark_running(self, run_id: str) -> None:
        """标记运行为运行中状态"""
        self.update_status(run_id, status="running")

    def mark_completed(self, run_id: str, **final_counts) -> None:
        """
        标记运行为已完成

        Args:
            **final_counts: 最终计数（如 raw_count, saved_count）
        """
        self.update_status(
            run_id,
            status="completed",
            finished_at=datetime.now().isoformat(),
            **final_counts,
        )

    def mark_error(self, run_id: str, error: str) -> None:
        """
        标记运行为错误状态

        Args:
            error: 错误信息
        """
        self.update_status(
            run_id, status="error", error=error, finished_at=datetime.now().isoformat()
        )

    def get_current_run_id(self) -> Optional[str]:
        """获取当前运行的 ID"""
        current = read_json_safe(self.current_run_file)
        if current:
            return current.get("run_id")
        return None

    def read_status(self, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        读取运行状态

        Args:
            run_id: 运行 ID，默认为当前运行

        Returns:
            状态字典，如果不存在则返回 None
        """
        if run_id is None:
            run_id = self.get_current_run_id()

        if not run_id:
            return None

        return read_json_safe(self._get_status_path(run_id))

    def read_new_logs(
        self, run_id: Optional[str] = None, cursor: int = 0, limit: int = 100
    ) -> Tuple[List[str], int]:
        """
        读取新的日志行

        Args:
            run_id: 运行 ID，默认为当前运行
            cursor: 起始行号（从0开始）
            limit: 最大返回行数

        Returns:
            (日志行列表, 新的游标位置)
        """
        if run_id is None:
            run_id = self.get_current_run_id()

        if not run_id:
            return [], 0

        log_path = self._get_log_path(run_id)

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return [], 0

        # 返回从 cursor 开始的行
        new_lines = lines[cursor : cursor + limit]
        new_cursor = cursor + len(new_lines)

        # 去除行尾换行符
        new_lines = [line.rstrip("\n") for line in new_lines]

        return new_lines, new_cursor

    def is_running(self, run_id: Optional[str] = None) -> bool:
        """
        检查指定运行是否正在运行

        Args:
            run_id: 运行 ID，默认为当前运行
        """
        status = self.read_status(run_id)
        if status:
            return status.get("status") == "running"
        return False

    def has_running_run(self) -> bool:
        """检查是否有正在运行的任务"""
        return self.is_running()

    def cleanup_old_runs(self, keep_runs: int = 10, max_age_days: int = 7) -> List[str]:
        """
        清理旧的运行记录

        策略：
        1. 保留最近的 keep_runs 个运行
        2. 删除超过 max_age_days 天的已完成运行
        3. 永远不会删除正在运行的任务

        Args:
            keep_runs: 保留的运行数量
            max_age_days: 最大保留天数

        Returns:
            被删除的运行 ID 列表
        """
        deleted = []
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # 获取所有运行目录
        if not self.runs_dir.exists():
            return deleted

        run_dirs = []
        for run_dir in self.runs_dir.iterdir():
            if run_dir.is_dir():
                status = self.read_status(run_dir.name)
                if status:
                    started_at = datetime.fromisoformat(
                        status.get("started_at", "2000-01-01")
                    )
                    run_dirs.append(
                        {
                            "run_id": run_dir.name,
                            "started_at": started_at,
                            "status": status.get("status"),
                        }
                    )

        # 按时间倒序排列
        run_dirs.sort(key=lambda x: x["started_at"], reverse=True)

        # 保留最近的 keep_runs 个
        runs_to_keep = {r["run_id"] for r in run_dirs[:keep_runs]}

        # 删除旧的和超期的
        for run_info in run_dirs:
            run_id = run_info["run_id"]

            # 跳过正在运行的
            if run_info["status"] == "running":
                continue

            # 跳过需要保留的
            if run_id in runs_to_keep:
                continue

            # 删除超期的
            if run_info["started_at"] < cutoff_date:
                run_dir = self._get_run_dir(run_id)
                try:
                    # 删除目录及其内容
                    import shutil

                    shutil.rmtree(run_dir)
                    deleted.append(run_id)
                except Exception:
                    pass  # 忽略删除错误

        return deleted

    def get_run_list(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取运行列表

        Args:
            limit: 最大返回数量

        Returns:
            运行信息列表，按时间倒序
        """
        runs = []

        if not self.runs_dir.exists():
            return runs

        for run_dir in self.runs_dir.iterdir():
            if run_dir.is_dir():
                status = self.read_status(run_dir.name)
                if status:
                    runs.append(
                        {
                            "run_id": status.get("run_id"),
                            "crawler": status.get("crawler"),
                            "status": status.get("status"),
                            "keyword": status.get("keyword"),
                            "started_at": status.get("started_at"),
                            "finished_at": status.get("finished_at"),
                        }
                    )

        # 按时间倒序排列
        runs.sort(key=lambda x: x.get("started_at", ""), reverse=True)

        return runs[:limit]


def build_crawler_logger(run_store: CrawlRunStore, run_id: str) -> logging.Logger:
    """
    构建爬虫专用日志记录器

    配置：
    - 控制台输出（StreamHandler）
    - 文件输出（FileHandler）写入 crawler.log

    Args:
        run_store: 运行存储实例
        run_id: 运行 ID

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(f"crawler.{run_id}")
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 格式化器
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 handler
    log_path = run_store._get_log_path(run_id)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
