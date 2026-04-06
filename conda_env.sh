#!/bin/bash
# Conda 环境配置脚本
# 所有 Python 命令都通过 recruitment_sys 环境执行

CONDA_BASE="/home/niaowuuu/miniconda"
CONDA_BIN="$CONDA_BASE/condabin/conda"
ENV_NAME="recruitment_sys"

# 使用 conda run 执行命令（无需激活环境）
run_in_env() {
    "$CONDA_BIN" run -n "$ENV_NAME" "$@"
}

# 快捷命令
alias py="run_in_env python"
alias pip="run_in_env pip"
alias pytest="run_in_env pytest"
alias django-admin="run_in_env django-admin"

# 项目快捷命令
cd_project() {
    cd /mnt/d/副业/写作/毕业设计/ed2443-3.4-泡泡专属服务群-3.15/recruitment_system
}

runserver() {
    cd_project
    run_in_env python manage.py runserver "$@"
}

migrate() {
    cd_project
    run_in_env python manage.py migrate "$@"
}

makemigrations() {
    cd_project
    run_in_env python manage.py makemigrations "$@"
}

test() {
    cd_project
    run_in_env python manage.py test "$@"
}

crawl() {
    cd_project
    run_in_env python crawler/job51_crawler.py "$@"
}

echo "Conda 环境配置已加载: $ENV_NAME"
echo "可用快捷命令: py, pip, pytest, runserver, migrate, test, crawl"
