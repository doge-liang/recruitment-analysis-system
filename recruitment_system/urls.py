"""
URL configuration for recruitment_system project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from myApp.admin import custom_admin_site  # 导入自定义 admin site

urlpatterns = [
    path("admin/", custom_admin_site.urls),  # 使用自定义 admin site
    path("myApp/", include("myApp.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
