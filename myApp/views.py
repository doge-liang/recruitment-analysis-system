"""
Django Views for Recruitment Analysis System
"""

import hashlib
import json
import random
import re
from datetime import datetime

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Avg
from django.db.models.functions import Replace
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from .models import JobInfo, History, UserProfile


# ==================== 工具函数 ====================


def md5_encrypt(password):
    """MD5加密密码"""
    return hashlib.md5(password.encode()).hexdigest()


def parse_salary(salary_str):
    """
    解析薪资字符串，返回最低、最高薪资（单位：K）
    例如: "15K-25K·13薪" -> (15, 25)
    """
    if not salary_str:
        return 0, 0
    # 移除"薪"等后缀
    salary_str = re.sub(r"[·\d]*薪", "", salary_str)
    match = re.search(r"(\d+)[kK]?-(\d+)[kK]?", salary_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def get_salary_avg(salary_str):
    """获取薪资平均值（单位：K）"""
    low, high = parse_salary(salary_str)
    return (low + high) / 2


# ==================== 用户认证 ====================


def login_view(request):
    """用户登录"""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            return render(request, "login.html", {"error": "用户名和密码不能为空"})

        # 使用Django标准认证
        user = authenticate(request, username=username, password=password)

        if user is None:
            return render(request, "login.html", {"error": "用户名或密码错误"})

        login(request, user)
        return HttpResponseRedirect("/myApp/index/")

    return render(request, "login.html")


def registry_view(request):
    """用户注册"""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        # 验证
        if not username or not password:
            return render(request, "registry.html", {"error": "用户名和密码不能为空"})

        if password != confirm_password:
            return render(request, "registry.html", {"error": "两次密码输入不一致"})

        if User.objects.filter(username=username).exists():
            return render(request, "registry.html", {"error": "用户名已存在"})

        # 创建用户，使用Django标准密码哈希（create_user会自动处理）
        user = User.objects.create_user(username=username, password=password)

        # 创建用户扩展信息
        UserProfile.objects.create(user=user)

        return HttpResponseRedirect("/myApp/login/")

    return render(request, "registry.html")


@login_required
def logout_view(request):
    """用户登出"""
    logout(request)
    return HttpResponseRedirect("/myApp/login/")


# ==================== 首页 ====================


@login_required
def index(request):
    """系统首页"""
    # 获取统计数据
    total_jobs = JobInfo.objects.count()
    total_users = User.objects.count()

    # 学历分布
    edu_dist = (
        JobInfo.objects.order_by().values("educational").annotate(count=Count("id"))
    )
    edu_labels = [item["educational"] for item in edu_dist]
    edu_counts = [item["count"] for item in edu_dist]

    # 薪资分布
    salary_ranges = [
        ("5K以下", 0, 5),
        ("5K-10K", 5, 10),
        ("10K-15K", 10, 15),
        ("15K-20K", 15, 20),
        ("20K-30K", 20, 30),
        ("30K以上", 30, 999),
    ]

    salary_dist = []
    all_jobs = JobInfo.objects.all()
    for label, low, high in salary_ranges:
        count = 0
        for job in all_jobs:
            low_sal, high_sal = parse_salary(job.salary)
            if low <= low_sal < high:
                count += 1
        salary_dist.append({"label": label, "count": count})

    # 最新职位
    recent_jobs = JobInfo.objects.all()[:10]

    # 最近数据入库日期
    latest_job = JobInfo.objects.order_by("-createTime").first()
    latest_job_date = (
        latest_job.createTime.strftime("%Y-%m-%d") if latest_job else "暂无数据"
    )

    context = {
        "total_jobs": total_jobs,
        "total_users": total_users,
        "edu_labels": json.dumps(edu_labels),
        "edu_counts": json.dumps(edu_counts),
        "recent_jobs": recent_jobs,
        "username": request.user.username,
        "latest_job_date": latest_job_date,
    }
    return render(request, "index.html", context)


# ==================== 薪资分析 ====================


@login_required
def salary_view(request):
    """薪资分析页面"""
    return render(request, "salaryChart.html")


@login_required
def salary_data_api(request):
    """薪资分析API"""
    educational = request.GET.get("educational", "")
    work_experience = request.GET.get("workExperience", "")

    # 构建查询
    queryset = JobInfo.objects.all()
    if educational:
        queryset = queryset.filter(educational=educational)
    if work_experience:
        queryset = queryset.filter(workExperience=work_experience)

    # 薪资区间统计（柱状图）
    salary_ranges = [
        ("5K以下", 0, 5),
        ("5K-10K", 5, 10),
        ("10K-15K", 10, 15),
        ("15K-20K", 15, 20),
        ("20K-30K", 20, 30),
        ("30K以上", 30, 100),
    ]

    bar_data = []
    for label, low, high in salary_ranges:
        count = 0
        for job in queryset:
            low_sal, high_sal = parse_salary(job.salary)
            if low <= low_sal < high:
                count += 1
        bar_data.append({"name": label, "value": count})

    # 饼图数据（不同薪资级别占比）
    salary_levels = {
        "低薪(5K以下)": 0,
        "中薪(5K-15K)": 0,
        "高薪(15K-30K)": 0,
        "超高薪(30K以上)": 0,
    }
    for job in queryset:
        avg_sal = get_salary_avg(job.salary)
        if avg_sal < 5:
            salary_levels["低薪(5K以下)"] += 1
        elif avg_sal < 15:
            salary_levels["中薪(5K-15K)"] += 1
        elif avg_sal < 30:
            salary_levels["高薪(15K-30K)"] += 1
        else:
            salary_levels["超高薪(30K以上)"] += 1

    pie_data = [{"name": k, "value": v} for k, v in salary_levels.items()]

    # 漏斗图数据（按薪资排序）
    funnel_data = sorted(bar_data, key=lambda x: x["value"], reverse=True)

    # 可选的筛选条件
    educations = list(JobInfo.objects.values_list("educational", flat=True).distinct())
    experiences = list(
        JobInfo.objects.values_list("workExperience", flat=True).distinct()
    )

    return JsonResponse(
        {
            "bar_data": bar_data,
            "pie_data": pie_data,
            "funnel_data": funnel_data,
            "educations": educations,
            "experiences": experiences,
        }
    )


# ==================== 企业分析 ====================


@login_required
def company_view(request):
    """企业分析页面"""
    return render(request, "companyChart.html")


@login_required
def company_data_api(request):
    """企业分析API"""
    job_type = request.GET.get("type", "")

    queryset = JobInfo.objects.all()
    if job_type:
        queryset = queryset.filter(type=job_type)

    # 企业性质分布
    company_natures = (
        queryset.order_by().values("companyNature").annotate(count=Count("id"))
    )
    nature_data = [
        {"name": item["companyNature"] or "未知", "value": item["count"]}
        for item in company_natures
    ]

    # 融资状态分布
    company_status = (
        queryset.order_by().values("companyStatus").annotate(count=Count("id"))
    )
    status_data = [
        {"name": item["companyStatus"] or "未知", "value": item["count"]}
        for item in company_status
    ]

    # 公司规模分布
    company_people = (
        queryset.order_by().values("companyPeople").annotate(count=Count("id"))
    )
    people_data = [
        {"name": item["companyPeople"] or "未知", "value": item["count"]}
        for item in company_people
    ]

    # 行业分布
    industry_dist = (
        queryset.order_by()
        .values("companyNature")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    industry_data = [
        {"name": item["companyNature"] or "未知", "value": item["count"]}
        for item in industry_dist
    ]

    # 岗位类型
    job_types = list(JobInfo.objects.values_list("type", flat=True).distinct())

    return JsonResponse(
        {
            "nature_data": nature_data,
            "status_data": status_data,
            "people_data": people_data,
            "industry_data": industry_data,
            "job_types": job_types,
        }
    )


# ==================== 学历分布 ====================


@login_required
def educational_view(request):
    """学历分布页面"""
    return render(request, "educationalChart.html")


@login_required
def educational_data_api(request):
    """学历分布API"""
    educational = request.GET.get("educational", "")

    queryset = JobInfo.objects.all()
    if educational:
        queryset = queryset.filter(educational=educational)

    # 学历分布饼图
    edu_dist = queryset.order_by().values("educational").annotate(count=Count("id"))
    pie_data = [
        {"name": item["educational"], "value": item["count"]} for item in edu_dist
    ]

    # 经验-薪资折线图
    experience_dist = (
        queryset.order_by()
        .values("workExperience")
        .annotate(count=Count("id"), avg_salary=Avg("salary"))
    )

    line_data = []
    for item in experience_dist:
        # 计算平均薪资
        avg_sal = 0
        jobs = queryset.filter(workExperience=item["workExperience"])
        salaries = [get_salary_avg(job.salary) for job in jobs]
        if salaries:
            avg_sal = sum(salaries) / len(salaries)
        line_data.append(
            {
                "name": item["workExperience"] or "未知",
                "count": item["count"],
                "avg_salary": round(avg_sal, 1),
            }
        )

    # 所有学历选项
    educations = list(JobInfo.objects.values_list("educational", flat=True).distinct())

    return JsonResponse(
        {
            "pie_data": pie_data,
            "line_data": line_data,
            "educations": educations,
        }
    )


# ==================== 城市分布 ====================


@login_required
def address_view(request):
    """城市分布页面"""
    return render(request, "addressChart.html")


@login_required
def address_data_api(request):
    """城市分布API"""
    address = request.GET.get("address", "")

    queryset = JobInfo.objects.all()
    if address:
        queryset = queryset.filter(address=address)

    # 城市分布饼图
    city_dist = (
        queryset.values("address").annotate(count=Count("id")).order_by("-count")
    )
    pie_data = [
        {"name": item["address"], "value": item["count"]} for item in city_dist
    ][:20]

    # 行政区分布
    dist_dist = (
        queryset.filter(dist__isnull=False)
        .exclude(dist="")
        .values("dist")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    dist_data = [{"name": item["dist"], "value": item["count"]} for item in dist_dist]

    # 热门城市薪资对比
    top_cities = [
        "北京",
        "上海",
        "深圳",
        "广州",
        "杭州",
        "成都",
        "南京",
        "武汉",
        "西安",
        "苏州",
    ]
    city_salary_data = []
    for city in top_cities:
        city_jobs = queryset.filter(address__contains=city)
        if city_jobs.exists():
            salaries = [get_salary_avg(job.salary) for job in city_jobs]
            avg_sal = sum(salaries) / len(salaries) if salaries else 0
            city_salary_data.append(
                {"city": city, "avg_salary": round(avg_sal, 1), "count": len(salaries)}
            )

    # 所有城市选项
    cities = list(JobInfo.objects.values_list("address", flat=True).distinct())

    return JsonResponse(
        {
            "pie_data": pie_data,
            "dist_data": dist_data,
            "city_salary_data": city_salary_data,
            "cities": cities,
        }
    )


# ==================== 岗位查询 ====================


@login_required
def joblist_view(request):
    """岗位列表页面"""
    jobs = JobInfo.objects.all()[:50]
    return render(request, "joblist.html", {"jobs": jobs})


@login_required
def jobdetail_view(request, job_id):
    """岗位详情页面"""
    job = get_object_or_404(JobInfo, id=job_id)

    # 记录浏览历史
    if request.user.is_authenticated:
        History.objects.create(user=request.user, job=job)

    return render(request, "jobdetail.html", {"job": job})


@login_required
def job_search_api(request):
    """岗位搜索API"""
    keyword = request.GET.get("keyword", "")
    address = request.GET.get("address", "")
    educational = request.GET.get("educational", "")

    queryset = JobInfo.objects.all()

    if keyword:
        queryset = queryset.filter(title__icontains=keyword)
    if address:
        queryset = queryset.filter(address=address)
    if educational:
        queryset = queryset.filter(educational=educational)

    jobs = list(
        queryset.values(
            "id",
            "title",
            "address",
            "companyTitle",
            "salary",
            "educational",
            "workExperience",
            "companyNature",
        )[:50]
    )

    return JsonResponse({"jobs": jobs})


# ==================== 爬虫管理 ====================


@login_required
def crawl_view(request):
    """爬虫管理页面"""
    if not request.user.is_staff:
        return JsonResponse({"error": "权限不足"})
    return render(request, "crawl_admin.html")


@login_required
def crawl_start_api(request):
    """启动爬虫API"""
    if not request.user.is_staff:
        return JsonResponse({"error": "权限不足", "success": False})

    # 这里应该启动异步爬虫任务
    # 实际实现中可以使用Celery等任务队列
    from .crawler import boss_crawler
    import threading

    thread = threading.Thread(target=boss_crawler.run_crawler)
    thread.daemon = True
    thread.start()

    return JsonResponse({"success": True, "message": "爬虫已启动"})


# ==================== 机器学习 ====================


@login_required
def salary_predict_view(request):
    """薪资预测页面"""
    return render(request, "salary_predict.html")


@login_required
@login_required
def salary_predict_api(request):
    """薪资预测API"""
    if request.method == "POST":
        data = json.loads(request.body)
        educational = data.get("educational", "")
        work_experience = data.get("workExperience", "")
        company_people = data.get("companyPeople", "")
        address = data.get("address", "")

        # 使用机器学习模型预测
        from ml_model.salary_predictor import SalaryPredictor

        predictor = SalaryPredictor()
        prediction = predictor.predict(
            [educational, work_experience, company_people, address]
        )
        # 获取各城市平均薪资对比
        city_salaries = []
        for city in ["北京", "上海", "深圳", "广州", "杭州"]:
            city_jobs = JobInfo.objects.filter(address__contains=city)
            if city_jobs.exists():
                avg = (
                    sum(get_salary_avg(j.salary) for j in city_jobs) / city_jobs.count()
                )
                city_salaries.append({"city": city, "avg_salary": round(avg, 1)})

        return JsonResponse(
            {"predicted_salary": prediction, "city_comparison": city_salaries}
        )
        return JsonResponse({"predicted_salary": prediction})

    return JsonResponse({"error": "仅支持POST请求"})


@login_required
def job_recommend_view(request):
    """岗位推荐页面"""
    return render(request, "job_recommend.html")


@login_required
def job_recommend_api(request):
    """岗位推荐API"""
    if request.method == "POST":
        data = json.loads(request.body)
        user_edu = data.get("educational", "")
        user_exp = data.get("workExperience", "")
        user_addr = data.get("address", "")

        # 使用KNN模型推荐岗位
        from ml_model.salary_predictor import JobRecommender

        recommender = JobRecommender()
        recommendations = recommender.recommend(user_edu, user_exp, user_addr, top_n=10)

        return JsonResponse({"recommendations": recommendations})

    return JsonResponse({"error": "仅支持POST请求"})
