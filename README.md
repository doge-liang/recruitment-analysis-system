# 大数据人才招聘分析系统

基于 Python 的招聘数据爬取与可视化分析系统，用于毕业设计。

## 技术栈

- **后端**: Django 3.2+ + MySQL 8.0 / SQLite
- **爬虫**: Selenium + ChromeDriver
- **可视化**: ECharts + 词云图
- **机器学习**: scikit-learn (随机森林 + K近邻)

---

## 快速部署（推荐）

### 环境准备

```bash
# 创建环境
conda create -n recruitment python=3.10
conda activate recruitment
pip install -r requirements.txt

# 下载 ECharts
curl -o static/js/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js
curl -o static/js/echarts-wordcloud.min.js https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js
```

### 数据库配置（二选一）

**方式 A: Docker MySQL（推荐）**
```bash
# 启动 MySQL
docker run -d --name recruitment_mysql \
  -e MYSQL_ROOT_PASSWORD=root123456 \
  -e MYSQL_DATABASE=recruitment_db \
  -p 3306:3306 mysql:8.0

# 修改 settings.py 使用 MySQL
python -c "
import re
with open('recruitment_system/settings.py', 'r') as f:
    content = f.read()
content = content.replace(\"ENGINE': 'django.db.backends.sqlite3'\", \"ENGINE': 'django.db.backends.mysql'\")
content = content.replace(\"'NAME': BASE_DIR / 'db.sqlite3'\", \"'NAME': 'recruitment_db',\\n        'USER': 'root',\\n        'PASSWORD': 'root123456',\\n        'HOST': 'localhost',\\n        'PORT': '3306'\")
with open('recruitment_system/settings.py', 'w') as f:
    f.write(content)
print('已更新为 MySQL 配置')
"
```

**方式 B: SQLite（无需 MySQL，适合开发）**
```bash
# 默认配置已经是 SQLite，无需修改
```

### 数据导入（可选，推荐）

项目已包含约 **20000 条**预采集数据：

```bash
# 自动导入数据
python import_database.py --auto

# 或手动导入
python manage.py migrate
python import_database.py
```

数据文件：
- `database_export/recruitment_db_latest.sql` - SQL 格式
- `database_export/recruitment_db_latest.json` - JSON 格式

### 启动系统

```bash
# 训练机器学习模型
cd ml_model && python salary_predictor.py && cd ..

# 创建管理员账号
python manage.py createsuperuser

# 启动服务器
python manage.py runserver 0.0.0.0:8000
```

访问 http://localhost:8000/myApp/login/

---

## 项目结构

```
recruitment_system/
├── myApp/                 # 主应用（视图、模型、路由）
├── crawler/               # 爬虫模块
│   ├── job51_crawler.py           # 前程无忧爬虫
│   └── checkpoint_manager.py      # 断点续传
├── ml_model/              # 机器学习
│   └── salary_predictor.py        # 模型训练
├── database_export/       # 预采集数据（SQL/JSON）
├── templates/             # HTML 模板
├── static/                # 静态文件（JS/CSS）
└── docs/                  # 文档
```

---

## 功能说明

### 1. 数据采集

**管理员界面**（推荐）：
1. 登录后访问 http://localhost:8000/myApp/admin/crawl/
2. 配置关键词、城市、页数
3. 点击"开始采集"，实时查看进度

**命令行**（高级）：
```bash
python crawler/job51_crawler.py --keyword "大数据" --pages 50
```

**⚠️ 爬虫注意事项：**
- 需在图形界面环境运行（Windows/Linux 桌面）
- 前程无忧有反爬机制，建议每批 50 页后休息 5-10 分钟
- 如遇验证码，在浏览器窗口手动完成验证后按回车继续
- 支持断点续传，中断后可自动恢复

### 2. 数据导入

**导入现有数据：**
```bash
# 使用项目预置数据
python import_database.py --auto

# 导入 CSV
python import_jobs.py

# 导入 Excel
python import_excel.py archive/招聘信息.xlsx
```

### 3. 可视化分析

登录后可查看：
- **薪资分析**: 柱状图、饼图、漏斗图
- **企业分析**: 企业性质、规模、融资分布
- **学历分布**: 环形图、折线图
- **城市分布**: 饼图、词云图

### 4. 机器学习

- **薪资预测**: 基于学历、经验、公司规模、城市预测薪资（随机森林）
- **岗位推荐**: 根据用户条件推荐匹配岗位（K近邻）

---

## 常见问题

**Q: 爬虫启动失败？**
A: Selenium 需要图形界面环境。Docker/纯命令行环境无法运行，请使用 Windows/Linux 桌面环境。

**Q: 如何清空数据重新采集？**
```bash
python manage.py shell
>>> from myApp.models import JobInfo
>>> JobInfo.objects.all().delete()
```

**Q: 数据导入失败？**
A: 检查 `database_export/IMPORT_README.md` 中的详细说明。

---

## 许可证

仅供学习研究使用
