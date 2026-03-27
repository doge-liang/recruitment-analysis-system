# myApp/tests/test_data_apis.py
"""Tests for data API endpoints"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from myApp.models import JobInfo
import json


class DataAPITests(TestCase):
    """Test cases for salary, company, educational, address APIs"""

    def setUp(self):
        """Set up test client and data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        # Create test job data
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
        JobInfo.objects.create(
            title="算法工程师",
            address="北京",
            type="算法",
            educational="硕士",
            workExperience="3-5年",
            salary="30K-50K·15薪",
            companyTitle="腾讯",
            companyNature="互联网",
            companyStatus="已上市",
            companyPeople="10000人以上",
        )

    def test_salary_api_authenticated(self):
        """Test salary API returns data for authenticated user"""
        response = self.client.get("/myApp/api/salary/data/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("bar_data", data)
        self.assertIn("pie_data", data)
        self.assertIn("funnel_data", data)
        self.assertIn("educations", data)
        self.assertIn("experiences", data)

    def test_salary_api_unauthenticated(self):
        """Test salary API redirects unauthenticated user"""
        client = Client()  # fresh client, not logged in
        response = client.get("/myApp/api/salary/data/")
        self.assertEqual(response.status_code, 302)

    def test_salary_api_with_educational_filter(self):
        """Test salary API with educational filter"""
        response = self.client.get("/myApp/api/salary/data/?educational=本科")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Should only return jobs matching filter

    def test_company_api_authenticated(self):
        """Test company API returns data for authenticated user"""
        response = self.client.get("/myApp/api/company/data/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("nature_data", data)
        self.assertIn("status_data", data)
        self.assertIn("people_data", data)
        self.assertIn("industry_data", data)
        self.assertIn("job_types", data)

    def test_company_api_unauthenticated(self):
        """Test company API redirects unauthenticated user"""
        client = Client()
        response = client.get("/myApp/api/company/data/")
        self.assertEqual(response.status_code, 302)

    def test_company_api_with_type_filter(self):
        """Test company API with job type filter"""
        response = self.client.get("/myApp/api/company/data/?type=大数据")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, dict)

    def test_educational_api_authenticated(self):
        """Test educational API returns data for authenticated user"""
        response = self.client.get("/myApp/api/educational/data/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("pie_data", data)
        self.assertIn("line_data", data)
        self.assertIn("educations", data)

    def test_educational_api_unauthenticated(self):
        """Test educational API redirects unauthenticated user"""
        client = Client()
        response = client.get("/myApp/api/educational/data/")
        self.assertEqual(response.status_code, 302)

    def test_address_api_authenticated(self):
        """Test address API returns data for authenticated user"""
        response = self.client.get("/myApp/api/address/data/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("pie_data", data)
        self.assertIn("dist_data", data)
        self.assertIn("city_salary_data", data)
        self.assertIn("cities", data)

    def test_address_api_unauthenticated(self):
        """Test address API redirects unauthenticated user"""
        client = Client()
        response = client.get("/myApp/api/address/data/")
        self.assertEqual(response.status_code, 302)

    def test_address_api_with_city_filter(self):
        """Test address API with city filter"""
        response = self.client.get("/myApp/api/address/data/?address=北京")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, dict)
