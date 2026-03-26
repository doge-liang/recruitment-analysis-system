from django.contrib import admin
from .models import JobInfo, History, UserProfile


@admin.register(JobInfo)
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


@admin.register(History)
class HistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "viewTime", "count")
    list_filter = ("viewTime",)
    search_fields = ("user__username", "job__title")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "educational", "workExperience", "address", "work")
    search_fields = ("user__username",)
