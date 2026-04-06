#!/bin/bash
# -*- coding: utf-8 -*-
#
# 前程无忧大规模数据爬取脚本
# 用于在生产环境收集20000+条数据
#
# 使用方法:
#   chmod +x crawl_20000_data.sh
#   ./crawl_20000_data.sh
#

set -e  # 遇到错误立即退出

# 配置
PROJECT_DIR="/path/to/recruitment_system"
CONDA_ENV="recruitment_sys"
LOG_DIR="$PROJECT_DIR/logs"
DATA_DIR="$PROJECT_DIR/data"

# 创建目录
mkdir -p "$LOG_DIR"
mkdir -p "$DATA_DIR"

# 获取当前时间
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/crawl_20000_$TIMESTAMP.log"

echo "========================================"
echo "前程无忧20000+数据爬取任务"
echo "========================================"
echo "开始时间: $(date)"
echo "日志文件: $LOG_FILE"
echo ""

# 激活conda环境
echo "[1/5] 激活conda环境..."
source ~/miniconda/etc/profile.d/conda.sh
conda activate $CONDA_ENV

# 进入项目目录
cd "$PROJECT_DIR"

# 检查当前数据量
echo "[2/5] 检查当前数据量..."
CURRENT_COUNT=$(conda run -n $CONDA_ENV python -c "
import os
import sys
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruitment_system.settings')
import django
django.setup()
from myApp.models import JobInfo
print(JobInfo.objects.count())
")
echo "当前数据库记录数: $CURRENT_COUNT"

# 计算需要爬取的页数（每页约20条）
TARGET_RECORDS=20000
NEED_RECORDS=$((TARGET_RECORDS - CURRENT_COUNT))
if [ $NEED_RECORDS -le 0 ]; then
    echo "✓ 已达到目标数据量!"
    exit 0
fi

NEED_PAGES=$(( (NEED_RECORDS + 19) / 20 ))  # 向上取整
echo "需要爬取约 $NEED_RECORDS 条记录（$NEED_PAGES 页）"
echo ""

# 关键词列表
KEYWORDS=("大数据" "数据分析" "数据挖掘" "机器学习" "人工智能" "数据仓库" "商业智能")
PAGES_PER_KEYWORD=$(( (NEED_PAGES + ${#KEYWORDS[@]} - 1) / ${#KEYWORDS[@]} ))

echo "[3/5] 爬取计划:"
echo "  - 关键词数量: ${#KEYWORDS[@]}"
echo "  - 每关键词页数: $PAGES_PER_KEYWORD"
echo ""

# 开始爬取
echo "[4/5] 开始爬取数据..."
echo ""

TOTAL_SUCCESS=0
TOTAL_FAILED=0

for keyword in "${KEYWORDS[@]}"; do
    echo "========================================"
    echo "关键词: $keyword"
    echo "========================================"
    
    START_TIME=$(date +%s)
    
    # 运行爬虫
    if conda run -n $CONDA_ENV python crawler/job51_crawler_enhanced.py \
        --keyword "$keyword" \
        --pages $PAGES_PER_KEYWORD \
        --no-resume 2>&1 | tee -a "$LOG_FILE"; then
        
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        
        echo "✓ 关键词 '$keyword' 完成，耗时 ${DURATION} 秒"
        ((TOTAL_SUCCESS++))
    else
        echo "✗ 关键词 '$keyword' 失败"
        ((TOTAL_FAILED++))
    fi
    
    # 关键词间休息
    if [ "$keyword" != "${KEYWORDS[-1]}" ]; then
        REST_TIME=300  # 5分钟
        echo "休息 $REST_TIME 秒..."
        sleep $REST_TIME
    fi
    
    echo ""
done

# 检查最终结果
echo "[5/5] 检查最终结果..."
FINAL_COUNT=$(conda run -n $CONDA_ENV python -c "
import os
import sys
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruitment_system.settings')
import django
django.setup()
from myApp.models import JobInfo
print(JobInfo.objects.count())
")

echo ""
echo "========================================"
echo "爬取任务完成!"
echo "========================================"
echo "结束时间: $(date)"
echo "成功关键词: $TOTAL_SUCCESS"
echo "失败关键词: $TOTAL_FAILED"
echo "初始记录数: $CURRENT_COUNT"
echo "最终记录数: $FINAL_COUNT"
echo "新增记录数: $((FINAL_COUNT - CURRENT_COUNT))"
echo "日志文件: $LOG_FILE"
echo "========================================"

# 导出数据备份
echo "导出数据备份..."
conda run -n $CONDA_ENV python -c "
import os
import sys
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruitment_system.settings')
import django
django.setup()

import pandas as pd
from myApp.models import JobInfo

jobs = JobInfo.objects.all().values()
df = pd.DataFrame(list(jobs))
df.to_csv('$DATA_DIR/jobs_backup_$TIMESTAMP.csv', index=False, encoding='utf-8-sig')
print(f'已导出 {len(df)} 条记录到 CSV')
"

echo "✓ 所有任务完成!"
