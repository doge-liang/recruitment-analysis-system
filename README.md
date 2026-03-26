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

## 安装步骤

### 1. 创建虚拟环境

```bash
cd recruitment_system
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. 创建管理员账户

```bash
python manage.py createsuperuser
```

### 5. 下载ECharts

将ECharts.js下载到 `static/js/` 目录：

```bash
# Linux/Mac
curl -o static/js/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js
curl -o static/js/echarts-wordcloud.min.js https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js

# Windows - 手动下载
# 从 https://echarts.apache.org/download.html 下载
```

### 6. 运行开发服务器

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/myApp/login/

## 项目结构

```
recruitment_system/
├── db.sqlite3              # SQLite数据库
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
    ├── css/
    └── js/
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

## 注意事项

1. **反爬机制**: BOSS直聘有反爬机制，实际使用可能需要Cookie登录或代理IP
2. **数据量**: 建议采集5000+条数据以获得更好的分析效果
3. **ChromeDriver**: 确保Chrome浏览器版本与ChromeDriver匹配

## 许可证

仅供学习研究使用
