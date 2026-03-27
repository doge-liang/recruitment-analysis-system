# myApp/tests/test_ml.py
"""Tests for ML endpoints (salary prediction and job recommendation)"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from myApp.models import JobInfo
from unittest.mock import patch
import json


class MLEndpointTests(TestCase):
    """Test cases for ML endpoints"""

    def setUp(self):
        """Set up test client and data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

    @patch("ml_model.salary_predictor.SalaryPredictor")
    def test_salary_predict_post(self, mock_predictor):
        """Test salary prediction with valid POST request"""
        mock_instance = mock_predictor.return_value
        mock_instance.predict.return_value = 25.5

        response = self.client.post(
            "/myApp/api/ml/salary_predict/",
            data=json.dumps({
                "educational": "本科",
                "workExperience": "3-5年",
                "companyPeople": "1000-9999人",
                "address": "北京"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("predicted_salary", data)

    def test_salary_predict_get_rejected(self):
        """Test salary prediction rejects GET requests"""
        response = self.client.get("/myApp/api/ml/salary_predict/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "仅支持POST请求")

    def test_salary_predict_unauthenticated(self):
        """Test salary prediction redirects unauthenticated user"""
        client = Client()
        response = client.post(
            "/myApp/api/ml/salary_predict/",
            data=json.dumps({
                "educational": "本科",
                "workExperience": "3-5年",
                "companyPeople": "1000-9999人",
                "address": "北京"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 302)

    @patch("ml_model.salary_predictor.JobRecommender")
    def test_job_recommend_post(self, mock_recommender):
        """Test job recommendation with valid POST request"""
        mock_instance = mock_recommender.return_value
        mock_instance.recommend.return_value = [
            {"title": "大数据工程师", "score": 0.95}
        ]

        response = self.client.post(
            "/myApp/api/ml/job_recommend/",
            data=json.dumps({
                "educational": "本科",
                "workExperience": "3-5年",
                "address": "北京"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("recommendations", data)

    def test_job_recommend_get_rejected(self):
        """Test job recommendation rejects GET requests"""
        response = self.client.get("/myApp/api/ml/job_recommend/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "仅支持POST请求")

    def test_job_recommend_unauthenticated(self):
        """Test job recommendation redirects unauthenticated user"""
        client = Client()
        response = client.post(
            "/myApp/api/ml/job_recommend/",
            data=json.dumps({
                "educational": "本科",
                "workExperience": "3-5年",
                "address": "北京"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 302)

    def test_salary_predict_view_page(self):
        """Test salary prediction view page loads"""
        response = self.client.get("/myApp/ml/salary_predict/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "salary_predict.html")

    def test_job_recommend_view_page(self):
        """Test job recommendation view page loads"""
        response = self.client.get("/myApp/ml/job_recommend/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "job_recommend.html")
