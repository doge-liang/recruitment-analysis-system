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
2. **数据采集**: 从BOSS直聘爬取大数据岗位招聘数据
3. **薪资分析**: 柱状图、饼图、漏斗图展示
4. **企业分析**: 企业性质、规模、融资状态分布
5. **学历分布**: 环形图、折线图展示
6. **城市分布**: 饼图、词云图展示
7. **岗位查询**: 条件筛选、详情查看
8. **薪资预测**: 随机森林回归模型
9. **岗位推荐**: K近邻分类模型

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
│   └── boss_crawler.py
├── ml_model/              # 机器学习模块
│   └── salary_predictor.py
├── templates/              # HTML模板
└── static/                # 静态文件
    └── js/
        ├── echarts.min.js
        └── echarts-wordcloud.min.js
```

## 数据采集

### 运行爬虫

```bash
cd crawler
python boss_crawler.py
```

爬虫会从BOSS直聘采集大数据相关岗位信息，包括：
- 职位名称
- 薪资范围
- 学历要求
- 工作经验
- 公司名称
- 公司规模
- 所属行业
- 城市

### 采集参数

在 `boss_crawler.py` 中修改：

```python
run_crawler(keyword='大数据', city='101280600', pages=5)
```

城市代码参考：
- 101280600: 深圳
- 101210100: 杭州
- 101010100: 北京
- 101020100: 上海

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

1. **Python 版本**：Django 3.2 不支持 Python 3.13，需要使用 Python 3.8-3.10
2. **Docker MySQL**：确保 Docker Desktop 已启动
3. **反爬机制**: BOSS直聘有反爬机制，实际使用可能需要Cookie登录或代理IP
4. **数据量**: 建议采集5000+条数据以获得更好的分析效果
5. **ChromeDriver**: 确保Chrome浏览器版本与ChromeDriver匹配

## 许可证

仅供学习研究使用
