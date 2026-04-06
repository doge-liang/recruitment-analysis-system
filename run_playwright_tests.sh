#!/bin/bash
# 运行 Playwright 测试脚本
# 使用方法: bash run_playwright_tests.sh

cd /mnt/d/副业/写作/毕业设计/ed2443-3.4-泡泡专属服务群-3.15/recruitment_system

echo "=========================================="
echo "Playwright 自动化测试 - 爬虫管理界面"
echo "=========================================="
echo ""

# 检查 Django 服务器是否运行
if ! curl -s http://localhost:8000/myApp/ > /dev/null; then
    echo "❌ Django 服务器未启动，请先运行:"
    echo "   conda run -n recruitment_sys python manage.py runserver"
    exit 1
fi

echo "✓ Django 服务器已启动"
echo ""

# 运行测试
echo "开始运行测试..."
echo ""

/home/niaowuuu/miniconda/condabin/conda run -n recruitment_sys pytest crawler/tests/test_crawler_admin_playwright.py -v --tb=short 2>&1 | tee test_results.log

echo ""
echo "=========================================="
echo "测试完成！结果保存在 test_results.log"
echo "=========================================="