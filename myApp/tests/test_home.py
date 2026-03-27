# myApp/tests/test_home.py
"""Tests for index/home view"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from myApp.models import JobInfo


class HomeTests(TestCase):
    """Test cases for index/home view"""

    def setUp(self):
        """Set up test client and data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        # Create some test job data
        JobInfo.objects.create(
            title="大数据开发工程师",
            address="北京",
            type="大数据",
            educational="本科",
            workExperience="3-5年",
            salary="25K-40K·14薪",
            companyTitle="字节跳动",
            companyNature="互联网",
            companyStatus="已上市",
            companyPeople="10000人以上",
        )
        JobInfo.objects.create(
            title="数据分析师",
            address="上海",
            type="数据分析",
            educational="本科",
            workExperience="1-3年",
            salary="15K-25K·13薪",
            companyTitle="美团",
            companyNature="互联网",
            companyStatus="已上市",
            companyPeople="10000人以上",
        )

    def test_index_authenticated(self):
        """Test index page loads with authenticated user"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/myApp/index/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")

    def test_index_unauthenticated(self):
        """Test index redirects to login when not authenticated"""
        response = self.client.get("/myApp/index/")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/myApp/login/?next=/myApp/index/")

    def test_index_context_data(self):
        """Test index page contains required context data"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/myApp/index/")
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIn("total_jobs", context)
        self.assertIn("total_users", context)
        self.assertIn("edu_labels", context)
        self.assertIn("edu_counts", context)
        self.assertIn("recent_jobs", context)
        self.assertIn("username", context)
        self.assertEqual(context["username"], "testuser")

    def test_index_shows_correct_job_count(self):
        """Test index shows correct total job count"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/myApp/index/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_jobs"], 2)
