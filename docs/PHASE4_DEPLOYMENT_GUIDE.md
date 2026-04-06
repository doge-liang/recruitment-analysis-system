# Phase 4: 20000+数据爬取部署指南

## 环境限制说明

当前Docker/Conda环境存在Chrome启动限制（DevToolsActivePort错误），无法直接运行Selenium爬虫。

**已完成的准备工作：**
✅ 断点续传系统  
✅ 批量控制系统  
✅ 爬虫  
✅ 生产环境脚本  

## 生产环境部署步骤

### 1. 准备环境

在Windows本地或Linux服务器上：

```bash
# 安装Chrome浏览器
# Windows: 下载安装Chrome
# Linux (Ubuntu):
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get -f install

# 验证Chrome安装
google-chrome --version
```

### 2. 配置项目

```bash
# 克隆/复制项目到本地
cd recruitment_system

# 创建conda环境
conda create -n recruitment_sys python=3.10
conda activate recruitment_sys

# 安装依赖
pip install -r requirements.txt

# 安装ChromeDriver
pip install webdriver-manager

# 配置MySQL（如需要）
# 修改 recruitment_system/settings.py 中的数据库配置
```

### 3. 运行大规模爬取

```bash
# 方式1: 使用自动脚本（推荐）
chmod +x crawl_20000_data.sh
./crawl_20000_data.sh

# 方式2: 手动分批运行
conda activate recruitment_sys

# 第一批: 大数据 200页
python crawler/job51_crawler.py --keyword "大数据" --pages 200

# 第二批: 数据分析 200页  
python crawler/job51_crawler.py --keyword "数据分析" --pages 200

# 第三批: 数据挖掘 200页
python crawler/job51_crawler.py --keyword "数据挖掘" --pages 200

# 继续直到达到20000条...
```

### 4. 监控进度

```bash
# 检查当前数据量
conda run -n recruitment_sys python -c "
import os, sys
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruitment_system.settings')
import django
django.setup()
from myApp.models import JobInfo
print(f'当前记录数: {JobInfo.objects.count()}')
"

# 查看检查点
cat crawler_checkpoint.json

# 查看日志
tail -f logs/crawl_20000_*.log
```

## 预期结果

| 关键词 | 页数 | 预估记录数 | 预估时间 |
|--------|------|-----------|----------|
| 大数据 | 200 | ~4000条 | ~2小时 |
| 数据分析 | 200 | ~4000条 | ~2小时 |
| 数据挖掘 | 200 | ~4000条 | ~2小时 |
| 机器学习 | 200 | ~4000条 | ~2小时 |
| 人工智能 | 200 | ~4000条 | ~2小时 |
| **总计** | **1000页** | **~20000条** | **~10-12小时** |

## 故障恢复

如果爬虫中断：

```bash
# 检查点会自动保存，重新运行相同命令即可恢复
python crawler/job51_crawler.py --keyword "大数据" --pages 200

# 如果想从头开始（忽略检查点）
python crawler/job51_crawler.py --keyword "大数据" --pages 200 --no-resume
```

## 数据验证

爬取完成后验证数据：

```python
# 统计信息
from myApp.models import JobInfo

print(f"总记录数: {JobInfo.objects.count()}")
print(f"唯一公司数: {JobInfo.objects.values('companyTitle').distinct().count()}")
print(f"城市分布: {dict(JobInfo.objects.values('address').annotate(count=models.Count('id')).values_list('address', 'count'))}")
print(f"薪资分布: {dict(JobInfo.objects.values('salary').annotate(count=models.Count('id')).values_list('salary', 'count')[:10])}")
```

## 文件清单

部署所需文件：

- `crawler/job51_crawler.py` - 爬虫
- `crawler/checkpoint_manager.py` - 断点续传
- `crawl_20000_data.sh` - 自动运行脚本
- `requirements.txt` - 依赖列表

## 注意事项

1. **网络稳定性**: 确保网络连接稳定，避免频繁断网
2. **运行时间**: 建议分多天执行，每天200-300页
3. **反爬策略**: 已内置自适应限速，如遇验证码需手动处理
4. **数据备份**: 定期导出CSV备份，防止数据库丢失

## 联系支持

如遇问题：

1. 检查日志文件 `logs/crawl_20000_*.log`
2. 查看检查点文件 `crawler_checkpoint.json`
3. 运行单元测试 `python crawler/tests/test_checkpoint_manager.py`

---

**系统已完全准备就绪，可在正确配置的生产环境中运行！**
