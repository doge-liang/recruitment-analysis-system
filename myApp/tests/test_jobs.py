# myApp/tests/test_jobs.py
"""Tests for job list, detail, and search views"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from myApp.models import JobInfo
import json


class JobViewsTests(TestCase):
    """Test cases for job list, detail, and search"""

    def setUp(self):
        """Set up test client and data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        # Create test job data
        self.job1 = JobInfo.objects.create(
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
        self.job2 = JobInfo.objects.create(
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

    def test_joblist_view(self):
        """Test job list page loads"""
        response = self.client.get("/myApp/joblist/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "joblist.html")

    def test_joblist_view_unauthenticated(self):
        """Test job list redirects unauthenticated user"""
        client = Client()
        response = client.get("/myApp/joblist/")
        self.assertEqual(response.status_code, 302)

    def test_joblist_context(self):
        """Test job list contains jobs in context"""
        response = self.client.get("/myApp/joblist/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("jobs", response.context)

    def test_jobdetail_view(self):
        """Test job detail page loads"""
        response = self.client.get(f"/myApp/jobdetail/{self.job1.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobdetail.html")

    def test_jobdetail_view_unauthenticated(self):
        """Test job detail redirects unauthenticated user"""
        client = Client()
        response = client.get(f"/myApp/jobdetail/{self.job1.id}/")
        self.assertEqual(response.status_code, 302)

    def test_jobdetail_context(self):
        """Test job detail contains correct job"""
        response = self.client.get(f"/myApp/jobdetail/{self.job1.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["job"], self.job1)
        self.assertEqual(response.context["job"].title, "大数据开发工程师")

    def test_jobdetail_404(self):
        """Test job detail returns 404 for non-existent job"""
        response = self.client.get("/myApp/jobdetail/99999/")
        self.assertEqual(response.status_code, 404)

    def test_jobdetail_creates_history(self):
        """Test viewing job detail creates history record"""
        from myApp.models import History

        initial_count = History.objects.count()
        response = self.client.get(f"/myApp/jobdetail/{self.job1.id}/")
        self.assertEqual(response.status_code, 200)
        new_count = History.objects.count()
        self.assertEqual(new_count, initial_count + 1)

    def test_job_search_api(self):
        """Test job search API returns results"""
        response = self.client.get("/myApp/api/job/search/?keyword=大数据")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
        self.assertEqual(len(data["jobs"]), 1)
        self.assertEqual(data["jobs"][0]["title"], "大数据开发工程师")

    def test_job_search_api_unauthenticated(self):
        """Test job search API redirects unauthenticated user"""
        client = Client()
        response = client.get("/myApp/api/job/search/?keyword=大数据")
        self.assertEqual(response.status_code, 302)

    def test_job_search_empty_keyword(self):
        """Test job search with no keyword returns all jobs"""
        response = self.client.get("/myApp/api/job/search/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
        # Should return up to 50 jobs

    def test_job_search_no_results(self):
        """Test job search with non-matching keyword"""
        response = self.client.get("/myApp/api/job/search/?keyword=xyzabcnonexistent")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["jobs"]), 0)

    def test_job_search_with_address_filter(self):
        """Test job search with address filter"""
        response = self.client.get("/myApp/api/job/search/?address=北京")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
        for job in data["jobs"]:
            self.assertEqual(job["address"], "北京")

    def test_job_search_with_educational_filter(self):
        """Test job search with educational filter"""
        response = self.client.get("/myApp/api/job/search/?educational=本科")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
        for job in data["jobs"]:
            self.assertEqual(job["educational"], "本科")

    def test_job_search_with_multiple_filters(self):
        """Test job search with multiple filters"""
        response = self.client.get("/myApp/api/job/search/?keyword=数据&address=上海")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
