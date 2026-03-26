from django.urls import path
from . import views

app_name = "myApp"

urlpatterns = [
    # 首页
    path("index/", views.index, name="index"),
    path("", views.index, name="home"),
    # 用户认证
    path("login/", views.login_view, name="login"),
    path("registry/", views.registry_view, name="registry"),
    path("logout/", views.logout_view, name="logout"),
    # 薪资分析
    path("salary/", views.salary_view, name="salary"),
    path("api/salary/data/", views.salary_data_api, name="salary_data_api"),
    # 企业分析
    path("company/", views.company_view, name="company"),
    path("api/company/data/", views.company_data_api, name="company_data_api"),
    # 学历分布
    path("educational/", views.educational_view, name="educational"),
    path(
        "api/educational/data/", views.educational_data_api, name="educational_data_api"
    ),
    # 城市分布
    path("address/", views.address_view, name="address"),
    path("api/address/data/", views.address_data_api, name="address_data_api"),
    # 岗位查询
    path("joblist/", views.joblist_view, name="joblist"),
    path("jobdetail/<int:job_id>/", views.jobdetail_view, name="jobdetail"),
    path("api/job/search/", views.job_search_api, name="job_search_api"),
    # 爬虫管理
    path("admin/crawl/", views.crawl_view, name="crawl"),
    path("admin/crawl/start/", views.crawl_start_api, name="crawl_start"),
    # 机器学习
    path("ml/salary_predict/", views.salary_predict_view, name="salary_predict"),
    path("api/ml/salary_predict/", views.salary_predict_api, name="salary_predict_api"),
    path("ml/job_recommend/", views.job_recommend_view, name="job_recommend"),
    path("api/ml/job_recommend/", views.job_recommend_api, name="job_recommend_api"),
]
