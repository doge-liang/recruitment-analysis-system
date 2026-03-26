from django.db import models
from django.contrib.auth.models import User


class JobInfo(models.Model):
    """招聘信息模型"""

    title = models.CharField(max_length=200, verbose_name="职位名称")
    address = models.CharField(max_length=100, verbose_name="工作城市")
    type = models.CharField(max_length=100, verbose_name="岗位类型")
    educational = models.CharField(max_length=50, verbose_name="学历要求")
    workExperience = models.CharField(max_length=100, verbose_name="工作经验")
    workTag = models.CharField(
        max_length=500, verbose_name="技能标签", blank=True, null=True
    )
    salary = models.CharField(max_length=100, verbose_name="薪资范围")
    salaryMonth = models.CharField(
        max_length=50, verbose_name="年终奖", blank=True, null=True
    )
    companyTags = models.CharField(
        max_length=500, verbose_name="公司福利", blank=True, null=True
    )
    hrWork = models.CharField(
        max_length=100, verbose_name="HR职位", blank=True, null=True
    )
    hrName = models.CharField(
        max_length=100, verbose_name="HR姓名", blank=True, null=True
    )
    pratice = models.BooleanField(default=False, verbose_name="是否实习")
    companyTitle = models.CharField(max_length=200, verbose_name="公司名称")
    companyAvatar = models.CharField(
        max_length=500, verbose_name="公司头像", blank=True, null=True
    )
    companyNature = models.CharField(
        max_length=100, verbose_name="公司性质", blank=True, null=True
    )
    companyStatus = models.CharField(
        max_length=100, verbose_name="融资状态", blank=True, null=True
    )
    companyPeople = models.CharField(
        max_length=100, verbose_name="公司规模", blank=True, null=True
    )
    detailUrl = models.CharField(
        max_length=500, verbose_name="详情地址", blank=True, null=True
    )
    companyUrl = models.CharField(
        max_length=500, verbose_name="公司地址", blank=True, null=True
    )
    createTime = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    dist = models.CharField(
        max_length=100, verbose_name="行政区", blank=True, null=True
    )

    class Meta:
        db_table = "jobinfo"
        verbose_name = "招聘信息"
        verbose_name_plural = "招聘信息"
        ordering = ["-createTime"]

    def __str__(self):
        return f"{self.title} - {self.companyTitle}"


class History(models.Model):
    """浏览记录模型"""

    job = models.ForeignKey(JobInfo, on_delete=models.CASCADE, verbose_name="职位")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    count = models.IntegerField(default=0, verbose_name="收藏次数")
    viewTime = models.DateTimeField(auto_now_add=True, verbose_name="浏览时间")

    class Meta:
        db_table = "history"
        verbose_name = "浏览记录"
        verbose_name_plural = "浏览记录"
        ordering = ["-viewTime"]

    def __str__(self):
        return f"{self.user.username} - {self.job.title}"


class UserProfile(models.Model):
    """用户扩展信息"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    educational = models.CharField(
        max_length=50, verbose_name="学历", blank=True, null=True
    )
    workExperience = models.CharField(
        max_length=100, verbose_name="工作经验", blank=True, null=True
    )
    address = models.CharField(
        max_length=100, verbose_name="意向城市", blank=True, null=True
    )
    work = models.CharField(
        max_length=100, verbose_name="意向岗位", blank=True, null=True
    )
    avatar = models.ImageField(
        upload_to="avatars/", verbose_name="头像", blank=True, null=True
    )
    createTime = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "user_profile"
        verbose_name = "用户扩展信息"
        verbose_name_plural = "用户扩展信息"

    def __str__(self):
        return f"{self.user.username}'s profile"
