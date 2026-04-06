from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib.admin import AdminSite
from .models import JobInfo, History, UserProfile


class CustomAdminSite(AdminSite):
    """自定义 Admin Site，添加爬虫管理入口"""

    site_header = "招聘信息分析系统管理后台"
    site_title = "管理后台"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "crawl-manager/",
                self.admin_view(self.crawl_manager_view),
                name="crawl_manager",
            ),
        ]
        return custom_urls + urls

    def crawl_manager_view(self, request):
        """爬虫管理入口 - 重定向到爬虫管理页面"""
        return redirect("/myApp/admin/crawl/")

    def index(self, request, extra_context=None):
        """重写首页，添加自定义链接"""
        if extra_context is None:
            extra_context = {}

        # 添加爬虫管理链接到上下文
        extra_context["crawl_url"] = "/admin/myApp/jobinfo/crawl-manager/"
        extra_context["crawl_name"] = "🕷️ 爬虫管理（前程无忧数据采集）"

        return super().index(request, extra_context)


# 创建自定义 admin site 实例
custom_admin_site = CustomAdminSite(name="custom_admin")


# 注册模型到自定义 admin site
@admin.register(JobInfo, site=custom_admin_site)
class JobInfoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "companyTitle",
        "address",
        "salary",
        "educational",
        "createTime",
    )
    list_filter = ("address", "educational", "workExperience")
    search_fields = ("title", "companyTitle")
    date_hierarchy = "createTime"
    ordering = ("-createTime",)


@admin.register(History, site=custom_admin_site)
class HistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "viewTime", "count")
    list_filter = ("viewTime",)
    search_fields = ("user__username", "job__title")


@admin.register(UserProfile, site=custom_admin_site)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "educational", "workExperience", "address", "work")
    search_fields = ("user__username",)


# 同时注册到默认 admin（兼容现有代码）
admin.site.register(JobInfo, JobInfoAdmin)
admin.site.register(History, HistoryAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
