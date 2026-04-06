# 大数据人才招聘分析系统

基于Python的招聘数据爬取与可视化分析系统，用于毕业设计。

## 技术栈

- **后端框架**: Django 3.2+
- **数据库**: SQLite（开发）/ MySQL（生产）
- **爬虫**: Selenium + ChromeDriver
- **数据处理**: Pandas, NumPy
- **可视化**: ECharts
- **机器学习**: scikit-learn (随机森林回归, K近邻分类)

## 功能模块

1. **用户认证**: 登录、注册、会话管理
2. **数据采集**: 从前程无忧(51job)爬取大数据岗位招聘数据
3. **爬虫管理**: 管理员界面可视化控制爬虫任务（启动、监控、日志）
4. **薪资分析**: 柱状图、饼图、漏斗图展示
5. **企业分析**: 企业性质、规模、融资状态分布
6. **学历分布**: 环形图、折线图展示
7. **城市分布**: 饼图、词云图展示
8. **岗位查询**: 条件筛选、详情查看
9. **薪资预测**: 随机森林回归模型
10. **岗位推荐**: K近邻分类模型

---

## 快速部署（Windows + Docker MySQL）

### 第一步：安装 Miniconda

下载并安装：https://docs.conda.io/en/latest/miniconda.html

安装完成后打开 **CMD**，添加环境变量：

```batch
setx PATH "%PATH%;C:\Users\你的用户名\miniconda3;C:\Users\你的用户名\miniconda3\Scripts;C:\Users\你的用户名\miniconda3\Library\bin"
```

关闭并重新打开 CMD，验证：
```batch
conda --version
```

### 第二步：创建 Python 3.10 环境

```batch
conda create -n recruitment python=3.10
```

当提示 `Proceed ([y]/n):` 时输入 `y`

### 第三步：激活环境并安装依赖

```batch
conda activate recruitment
pip install -r requirements.txt
```

### 第四步：下载 ECharts

在项目 `static/js/` 目录下创建文件：

**echarts.min.js**：
```batch
curl -o static/js/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js
```

**echarts-wordcloud.min.js**（词云图需要）：
```batch
curl -o static/js/echarts-wordcloud.min.js https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js
```

### 第五步：启动 MySQL（Docker）

```batch
docker run -d --name recruitment_mysql -e MYSQL_ROOT_PASSWORD=root123456 -e MYSQL_DATABASE=recruitment_db -p 3306:3306 mysql:8.0
```

如果容器已存在：
```batch
docker start recruitment_mysql
```

### 第六步：初始化 MySQL 数据库

```batch
docker exec -it recruitment_mysql mysql -uroot -proot123456 -e "CREATE DATABASE IF NOT EXISTS recruitment_db;"
```

### 第七步：修改 settings.py（使用 MySQL）

找到 `settings.py` 中的 `DATABASES` 配置：

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'recruitment_db',
        'USER': 'root',
        'PASSWORD': 'root123456',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

并在 `settings.py` 顶部添加（Windows 兼容 MySQL）：
```python
import pymysql
pymysql.install_as_MySQLdb()
```

### 第八步：运行迁移

```batch
cd recruitment_system
python manage.py migrate
```

### 第九步：运行服务器

```batch
python manage.py runserver 0.0.0.0:8000
```

### 第十步：训练机器学习模型

首次部署或更新代码后，必须训练薪资预测和岗位推荐模型：

```powershell
cd ml_model
python salary_predictor.py
```

训练完成后会生成：
- `ml_model/salary_model.pkl` - 薪资预测模型
- `ml_model/job_recommender.pkl` - 岗位推荐模型

### 第十一步：访问系统

浏览器打开：http://localhost:8000/myApp/login/

默认管理员账号自行创建：
```batch
python manage.py createsuperuser
```

---

## 开发模式（使用 SQLite，不需要 MySQL）

### 1. 创建虚拟环境

```bash
cd recruitment_system
python -m venv venv
venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 下载 ECharts

```bash
curl -o static/js/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js
curl -o static/js/echarts-wordcloud.min.js https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js
```

### 4. 初始化数据库

```bash
python manage.py migrate
```

### 5. 运行开发服务器

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/myApp/login/

---

## 项目结构

```
recruitment_system/
├── db.sqlite3              # SQLite数据库（开发用）
├── manage.py               # Django管理脚本
├── requirements.txt        # 依赖列表
├── crawl_20000_data.sh     # 大规模数据采集脚本
├── recruitment_system/     # 项目配置
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── myApp/                 # 主应用
│   ├── models.py          # 数据模型
│   ├── views.py           # 视图函数
│   ├── urls.py            # URL路由
│   └── admin.py           # 后台管理
├── crawler/               # 爬虫模块
│   ├── job51_crawler.py           # 前程无忧基础爬虫
│   ├── job51_crawler_enhanced.py  # 增强版（断点续传、批量控制）
│   ├── checkpoint_manager.py      # 检查点管理器
│   ├── boss_crawler.py            # BOSS直聘爬虫（旧）
│   └── tests/                     # 测试文件
│       ├── test_crawler_admin_playwright.py
│       └── test_checkpoint_manager.py
├── ml_model/              # 机器学习模块
│   └── salary_predictor.py
├── docs/                  # 文档
│   ├── TDD_PLAN_A.md
│   ├── IMPLEMENTATION_REPORT.md
│   └── PHASE4_DEPLOYMENT_GUIDE.md
├── templates/              # HTML模板
│   └── crawl_admin.html   # 爬虫管理界面
└── static/                # 静态文件
    └── js/
        ├── echarts.min.js
        └── echarts-wordcloud.min.js
```

## 数据采集

### 方式一：使用管理员界面（推荐）

管理员可通过Web界面可视化控制爬虫任务：

1. **访问爬虫管理页面**
   - 登录管理员账号
   - 访问 http://localhost:8000/myApp/admin/crawl/

2. **配置爬取参数**
   - 搜索关键词（如：大数据、数据分析）
   - 选择城市（支持15个主要城市）
   - 设置爬取页数（1-50页）

3. **启动爬虫**
   - 点击"开始采集"按钮
   - 实时查看进度和日志
   - 支持随时查询任务状态

**API端点：**
- `GET /myApp/admin/crawl/` - 管理页面
- `POST /myApp/admin/crawl/start/` - 启动爬虫
- `GET /myApp/admin/crawl/status/` - 查询进度

### 方式二：命令行运行

#### 基础版爬虫

```bash
cd crawler
python job51_crawler.py
```

#### 增强版爬虫（支持断点续传和批量控制）

```bash
# 小规模测试（5页）
python crawler/job51_crawler_enhanced.py --keyword "大数据" --pages 5

# 中等规模（100页）
python crawler/job51_crawler_enhanced.py --keyword "大数据" --pages 100

# 大规模爬取（1000页 ≈ 20000条数据）
python crawler/job51_crawler_enhanced.py --keyword "大数据" --pages 1000

# 断点续传（恢复之前的爬取）
python crawler/job51_crawler_enhanced.py --keyword "大数据" --pages 1000

# 从头开始（忽略检查点）
python crawler/job51_crawler_enhanced.py --keyword "大数据" --pages 1000 --no-resume
```

#### 自动脚本（批量采集20000+数据）

```bash
chmod +x crawl_20000_data.sh
./crawl_20000_data.sh
```

爬虫会从前程无忧(51job.com)采集大数据相关岗位信息，包括：
- 职位名称
- 薪资范围
- 学历要求
- 工作经验
- 公司名称
- 公司规模
- 所属行业
- 城市

### 采集参数

在代码中修改参数：

```python
# 基础版
from crawler.job51_crawler import run_crawler
run_crawler(keyword='大数据', pages=5)

# 增强版（支持断点续传）
from crawler.job51_crawler_enhanced import run_crawler
run_crawler(keyword='大数据', city='上海', pages=50, resume=True)
```

**支持的城市：** 全国、北京、上海、深圳、广州、杭州、成都、武汉、南京、苏州、西安、重庆、天津、长沙、郑州、合肥

**关键词建议：** 大数据、数据分析、数据挖掘、机器学习、人工智能、数据仓库、商业智能

## 机器学习模型

### 训练模型

```bash
cd ml_model
python salary_predictor.py
```

### 薪资预测

使用随机森林回归算法，基于学历、工作经验、公司规模、城市预测薪资。

### 岗位推荐

使用K近邻分类算法，根据用户条件推荐匹配度最高的岗位。

## 导入CSV数据

如果已经有 CSV 格式的岗位数据：

```bash
cd recruitment_system
python import_jobs.py
```

## 注意事项

### 环境要求

1. **Python 版本**：Django 3.2 不支持 Python 3.13，需要使用 Python 3.8-3.10
2. **Docker MySQL**：确保 Docker Desktop 已启动
3. **ChromeDriver**: 确保Chrome浏览器版本与ChromeDriver匹配

### 爬虫运行环境说明

**重要**：Selenium爬虫需要在有图形界面的环境中运行，以下环境可能无法正常启动Chrome：

- ❌ Docker容器环境（无/dev/shm）
- ❌ 纯命令行服务器（无X11）
- ✅ Windows本地环境（推荐）
- ✅ Linux桌面环境
- ✅ WSL2 + Windows Chrome

**解决方案：**
```bash
# Windows本地运行
conda activate recruitment_sys
python crawler/job51_crawler.py

# 或使用增强版
python crawler/job51_crawler_enhanced.py --keyword "大数据" --pages 50
```

### 反爬机制

1. **前程无忧有反爬机制**，实际使用建议：
   - 控制爬取频率（已内置自适应限速）
   - 每批50页后休息5-10分钟
   - 单日爬取不超过500页
   - 如遇验证码需手动处理

2. **断点续传**：
   - 爬虫崩溃后可自动恢复
   - 进度保存在 `crawler_checkpoint.json`
   - 默认启用断点续传，使用 `--no-resume` 可从头开始

### 数据量建议

- **小规模测试**：5-10页（约100-200条）
- **中等规模**：50-100页（约1000-2000条）
- **大规模采集**：1000页（约20000条，需分多天完成）

## 许可证

仅供学习研究使用
