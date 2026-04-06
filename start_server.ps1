#!/usr/bin/env pwsh
# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    启动招聘分析系统服务器 (Windows)
.DESCRIPTION
    激活 conda 环境并启动 Django 开发服务器
    服务器将监听 0.0.0.0:8000
.EXAMPLE
    .\start_server.ps1
#>

# 设置编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  招聘分析系统 - Windows 服务器启动器  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 conda 是否可用
$condaPath = Get-Command conda -ErrorAction SilentlyContinue
if (-not $condaPath) {
    Write-Host "错误: 未找到 conda。请确保已安装 Miniconda 或 Anaconda。" -ForegroundColor Red
    Write-Host "下载地址: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor Yellow
    exit 1
}

# 激活 conda 环境
Write-Host "正在激活 conda 环境 'recruitment'..." -ForegroundColor Yellow
conda activate recruitment

if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 无法激活环境 'recruitment'" -ForegroundColor Red
    Write-Host "请确保已创建环境: conda create -n recruitment python=3.10" -ForegroundColor Yellow
    exit 1
}

Write-Host "环境激活成功！" -ForegroundColor Green
Write-Host ""

# 检查必要的文件
if (-not (Test-Path "manage.py")) {
    Write-Host "错误: 未找到 manage.py" -ForegroundColor Red
    Write-Host "请确保在正确的目录中运行此脚本。" -ForegroundColor Yellow
    exit 1
}

# 启动服务器
Write-Host "正在启动 Django 开发服务器..." -ForegroundColor Yellow
Write-Host "访问地址: http://localhost:8000/myApp/login/" -ForegroundColor Cyan
Write-Host "管理后台: http://localhost:8000/admin/" -ForegroundColor Cyan
Write-Host "爬虫管理: http://localhost:8000/myApp/admin/crawl/" -ForegroundColor Cyan
Write-Host ""
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

python manage.py runserver 0.0.0.0:8000
