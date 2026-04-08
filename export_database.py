#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库整库导出工具
导出所有 Django 应用的数据到 JSON 文件
"""

import os
import sys
import subprocess
import json
from datetime import datetime


def get_django_apps():
    """获取项目中的所有 Django 应用"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")

    import django

    django.setup()

    from django.apps import apps

    # 获取所有安装的应用（排除 Django 内置应用）
    builtin_apps = {
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "messages",
        "staticfiles",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    }

    project_apps = []
    for app_config in apps.get_app_configs():
        app_name = app_config.name
        if not any(builtin in app_name for builtin in builtin_apps):
            project_apps.append(app_name)

    return project_apps


def export_database():
    """导出整个数据库"""
    print("=" * 60)
    print("数据库整库导出工具")
    print("=" * 60)

    # 创建导出目录
    export_dir = "database_export"
    os.makedirs(export_dir, exist_ok=True)

    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = os.path.join(export_dir, f"recruitment_db_{timestamp}.json")

    print(f"\n导出目录: {export_dir}")
    print(f"导出文件: {export_file}")

    # 使用 Django 的 dumpdata 命令导出所有数据
    print("\n开始导出数据...")

    try:
        # 导出所有数据（包括内置应用的数据，如 auth 用户）
        cmd = [
            sys.executable,
            "manage.py",
            "dumpdata",
            "--indent",
            "2",
            "--output",
            export_file,
            "--natural-foreign",
            "--natural-primary",
            "-e",
            "contenttypes",
            "-e",
            "admin.logentry",
            "-e",
            "sessions.session",
        ]

        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=os.path.dirname(__file__)
        )

        if result.returncode == 0:
            print("✓ 导出成功!")

            # 显示导出统计
            with open(export_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            print(f"\n导出统计:")
            print(f"  总记录数: {len(data)}")

            # 按模型统计
            model_counts = {}
            for item in data:
                model = item.get("model", "unknown")
                model_counts[model] = model_counts.get(model, 0) + 1

            print(f"\n各模型记录数:")
            for model, count in sorted(model_counts.items()):
                print(f"  {model}: {count} 条")

            # 同时创建一个最新的符号链接/副本
            latest_file = os.path.join(export_dir, "recruitment_db_latest.json")
            if os.path.exists(latest_file):
                os.remove(latest_file)

            # 复制文件作为 latest
            import shutil

            shutil.copy2(export_file, latest_file)
            print(f"\n已创建最新版本副本: {latest_file}")

            print(f"\n导出完成!")
            print(f"文件位置: {os.path.abspath(export_file)}")
            print(f"文件大小: {os.path.getsize(export_file) / 1024 / 1024:.2f} MB")

            return export_file

        else:
            print(f"✗ 导出失败!")
            print(f"错误信息: {result.stderr}")
            return None

    except Exception as e:
        print(f"✗ 导出过程中出错: {e}")
        import traceback

        traceback.print_exc()
        return None


def export_schema_only():
    """仅导出数据库结构（SQL）"""
    print("\n" + "=" * 60)
    print("导出数据库结构 (SQL)")
    print("=" * 60)

    export_dir = "database_export"
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    schema_file = os.path.join(export_dir, f"schema_{timestamp}.sql")

    # 使用 Django 的 sqlmigrate 或直接导出
    print("\n生成 SQL 结构文件...")

    try:
        cmd = [sys.executable, "manage.py", "migrate", "--run-syncdb", "--check"]
        subprocess.run(cmd, capture_output=True, cwd=os.path.dirname(__file__))

        # 使用 inspectdb 反向生成模型（仅作参考）
        print("提示: 客户环境可直接使用 Django migrate 命令创建表结构")
        print("命令: python manage.py migrate")

    except Exception as e:
        print(f"警告: {e}")

    return schema_file


def create_import_instructions():
    """创建导入说明文档"""
    instructions = """
# 数据库导入说明

## 导入前准备

1. 确保客户环境已安装:
   - Python 3.8+
   - MySQL 5.7+ 或 8.0+
   - 项目依赖: pip install -r requirements.txt

2. 创建数据库:
   ```sql
   CREATE DATABASE recruitment_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'recruitment_user'@'localhost' IDENTIFIED BY 'your_password';
   GRANT ALL PRIVILEGES ON recruitment_db.* TO 'recruitment_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. 修改数据库配置:
   编辑 `recruitment_system/settings.py`:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'recruitment_db',
           'USER': 'recruitment_user',
           'PASSWORD': 'your_password',
           'HOST': 'localhost',
           'PORT': '3306',
           'OPTIONS': {'charset': 'utf8mb4'},
       }
   }
   ```

## 导入数据

### 方法1: 使用 Django loaddata (推荐)
```bash
# 1. 先创建表结构
python manage.py migrate

# 2. 导入数据
python import_database.py
```

### 方法2: 直接运行导入脚本
```bash
python import_database.py --auto
```

## 验证导入

导入完成后，运行以下命令验证:
```bash
python manage.py shell
```

在 shell 中执行:
```python
from myApp.models import JobInfo
print(f"总记录数: {JobInfo.objects.count()}")
```

## 常见问题

1. **内存不足**: 如果 JSON 文件很大，可能需要分批导入
2. **字符编码**: 确保 MySQL 使用 utf8mb4 编码
3. **外键约束**: 导入时会自动处理依赖关系

"""

    export_dir = "database_export"
    os.makedirs(export_dir, exist_ok=True)

    readme_path = os.path.join(export_dir, "IMPORT_README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(instructions)

    print(f"\n已创建导入说明: {readme_path}")


def main():
    print("=" * 60)
    print("招聘系统数据库导出工具")
    print("=" * 60)

    # 导出数据
    export_file = export_database()

    if export_file:
        # 导出说明文档
        create_import_instructions()

        print("\n" + "=" * 60)
        print("导出完成!")
        print("=" * 60)
        print(f"\n导出文件:")
        print(f"  - 数据文件: database_export/recruitment_db_*.json")
        print(f"  - 最新版本: database_export/recruitment_db_latest.json")
        print(f"  - 导入说明: database_export/IMPORT_README.md")
        print(f"\n请将以下文件发送给客户:")
        print(f"  1. database_export/recruitment_db_latest.json (数据文件)")
        print(f"  2. import_database.py (导入脚本)")
        print(f"  3. IMPORT_README.md (导入说明)")
    else:
        print("\n导出失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
