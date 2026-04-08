#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库整库导入工具
用于将导出的 JSON 数据导入到客户环境的 MySQL 数据库中
"""

import os
import sys
import subprocess
import json
import argparse


def check_database_connection():
    """检查数据库连接是否正常"""
    print("检查数据库连接...")

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")

        import django

        django.setup()

        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                print("✓ 数据库连接正常")
                return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        print("\n请检查:")
        print("  1. MySQL 服务是否已启动")
        print("  2. 数据库配置是否正确 (recruitment_system/settings.py)")
        print("  3. 数据库是否存在")
        return False


def create_database_schema():
    """创建数据库表结构"""
    print("\n创建数据库表结构...")

    try:
        cmd = [sys.executable, "manage.py", "migrate"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=os.path.dirname(__file__)
        )

        if result.returncode == 0:
            print("✓ 表结构创建成功")
            return True
        else:
            print(f"✗ 创建表结构失败")
            print(f"错误: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False


def import_data(json_file, ignore_errors=False):
    """导入数据到数据库"""
    print(f"\n开始导入数据: {json_file}")

    if not os.path.exists(json_file):
        print(f"✗ 找不到数据文件: {json_file}")
        return False

    # 检查文件大小
    file_size = os.path.getsize(json_file) / 1024 / 1024  # MB
    print(f"数据文件大小: {file_size:.2f} MB")

    if file_size > 50:
        print("警告: 数据文件较大，导入可能需要较长时间")

    try:
        # 使用 Django 的 loaddata 命令
        cmd = [sys.executable, "manage.py", "loaddata", json_file]

        if ignore_errors:
            cmd.append("--ignorenonexistent")

        print(f"执行: {' '.join(cmd)}")

        # 实时显示输出
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=os.path.dirname(__file__),
        )

        for line in process.stdout:
            print(line, end="")

        process.wait()

        if process.returncode == 0:
            print("\n✓ 数据导入成功")
            return True
        else:
            print(f"\n✗ 数据导入失败 (返回码: {process.returncode})")
            return False

    except Exception as e:
        print(f"\n✗ 导入过程中出错: {e}")
        import traceback

        traceback.print_exc()
        return False


def verify_import():
    """验证导入结果"""
    print("\n" + "=" * 60)
    print("验证导入结果")
    print("=" * 60)

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")

        import django

        django.setup()

        from myApp.models import JobInfo
        from django.contrib.auth.models import User

        job_count = JobInfo.objects.count()
        user_count = User.objects.count()

        print(f"\n导入统计:")
        print(f"  招聘信息: {job_count} 条")
        print(f"  用户数量: {user_count} 个")

        if job_count > 0:
            print("\n数据示例 (前3条):")
            for job in JobInfo.objects.all()[:3]:
                print(f"  - {job.title} @ {job.companyTitle}")

            print("\n数据质量检查:")
            fields_to_check = [
                "companyNature",
                "companyStatus",
                "companyPeople",
                "type",
            ]
            for field in fields_to_check:
                null_count = JobInfo.objects.filter(
                    **{f"{field}__isnull": True}
                ).count()
                coverage = (
                    ((job_count - null_count) / job_count * 100) if job_count > 0 else 0
                )
                status = "✓" if coverage == 100 else "⚠"
                print(f"  {status} {field}: {coverage:.1f}% 有值")

            print("\n✓ 验证完成!")
            return True
        else:
            print("\n⚠ 警告: 没有导入任何招聘信息")
            return False

    except Exception as e:
        print(f"✗ 验证失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def clear_database():
    """清空数据库（谨慎使用）"""
    print("\n警告: 这将删除数据库中的所有数据!")
    response = input("确定要清空数据库吗? (yes/no): ")

    if response.lower() != "yes":
        print("已取消")
        return False

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recruitment_system.settings")

        import django

        django.setup()

        from myApp.models import JobInfo, History, UserProfile
        from django.contrib.auth.models import User

        print("清空数据...")
        History.objects.all().delete()
        UserProfile.objects.all().delete()
        JobInfo.objects.all().delete()
        # 保留超级用户，删除普通用户
        User.objects.filter(is_superuser=False).delete()

        print("✓ 数据库已清空")
        return True

    except Exception as e:
        print(f"✗ 清空失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="招聘系统数据库导入工具")
    parser.add_argument(
        "--file",
        "-f",
        default="database_export/recruitment_db_latest.json",
        help="要导入的 JSON 文件路径 (默认: database_export/recruitment_db_latest.json)",
    )
    parser.add_argument(
        "--auto", "-a", action="store_true", help="自动模式: 创建表结构并导入数据"
    )
    parser.add_argument(
        "--migrate-only", "-m", action="store_true", help="仅创建表结构，不导入数据"
    )
    parser.add_argument(
        "--clear", "-c", action="store_true", help="清空数据库（谨慎使用）"
    )
    parser.add_argument(
        "--ignore-errors", action="store_true", help="忽略导入过程中的错误"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("招聘系统数据库导入工具")
    print("=" * 60)

    # 检查数据库连接
    if not check_database_connection():
        sys.exit(1)

    # 清空数据库
    if args.clear:
        if clear_database():
            print("\n数据库已清空，可以重新导入数据")
        return

    # 创建表结构
    if args.auto or args.migrate_only:
        if not create_database_schema():
            sys.exit(1)

        if args.migrate_only:
            print("\n表结构创建完成")
            return

    # 导入数据
    if args.auto or (not args.migrate_only and not args.clear):
        # 如果文件不存在，尝试查找其他 JSON 文件
        if not os.path.exists(args.file):
            print(f"\n默认文件不存在: {args.file}")
            print("正在查找其他数据文件...")

            export_dir = "database_export"
            if os.path.exists(export_dir):
                json_files = [f for f in os.listdir(export_dir) if f.endswith(".json")]
                if json_files:
                    # 选择最新的文件
                    json_files.sort(reverse=True)
                    args.file = os.path.join(export_dir, json_files[0])
                    print(f"找到数据文件: {args.file}")
                else:
                    print("✗ 找不到任何 JSON 数据文件")
                    print("请使用 --file 参数指定数据文件路径")
                    sys.exit(1)
            else:
                print("✗ 找不到 database_export 目录")
                sys.exit(1)

        # 执行导入
        if import_data(args.file, ignore_errors=args.ignore_errors):
            # 验证导入结果
            verify_import()

            print("\n" + "=" * 60)
            print("导入完成!")
            print("=" * 60)
            print("\n现在可以启动服务器:")
            print("  python manage.py runserver")
        else:
            print("\n导入失败，请检查错误信息")
            sys.exit(1)


if __name__ == "__main__":
    main()
