# myApp/tests/test_auth.py
"""Tests for user authentication views"""

from django.test import TestCase, Client
from django.contrib.auth.models import User


class AuthTests(TestCase):
    """Test cases for login, registry, logout"""

    def setUp(self):
        """Set up test client and users"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = self.client.post(
            "/myApp/login/", {"username": "testuser", "password": "testpass123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/myApp/index/")

    def test_login_invalid_password(self):
        """Test login with wrong password"""
        response = self.client.post(
            "/myApp/login/", {"username": "testuser", "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertEqual(response.context["error"], "用户名或密码错误")

    def test_login_nonexistent_user(self):
        """Test login with non-existent username"""
        response = self.client.post(
            "/myApp/login/", {"username": "nonexistent", "password": "somepass"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertEqual(response.context["error"], "用户名或密码错误")

    def test_login_missing_username(self):
        """Test login with missing username"""
        response = self.client.post(
            "/myApp/login/", {"username": "", "password": "testpass123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_login_missing_password(self):
        """Test login with missing password"""
        response = self.client.post(
            "/myApp/login/", {"username": "testuser", "password": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_registry_success(self):
        """Test successful user registration"""
        response = self.client.post(
            "/myApp/registry/",
            {
                "username": "newuser",
                "password": "newpass123",
                "confirm_password": "newpass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/myApp/login/")
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_registry_password_mismatch(self):
        """Test registration with mismatched passwords"""
        response = self.client.post(
            "/myApp/registry/",
            {
                "username": "newuser2",
                "password": "pass123",
                "confirm_password": "differentpass",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertEqual(response.context["error"], "两次密码输入不一致")

    def test_registry_duplicate_username(self):
        """Test registration with existing username"""
        response = self.client.post(
            "/myApp/registry/",
            {
                "username": "testuser",
                "password": "newpass123",
                "confirm_password": "newpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertEqual(response.context["error"], "用户名已存在")

    def test_registry_missing_fields(self):
        """Test registration with missing fields"""
        response = self.client.post(
            "/myApp/registry/", {"username": "", "password": "", "confirm_password": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_logout(self):
        """Test logout"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/myApp/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/myApp/login/")

    def test_protected_view_redirects_unauthenticated(self):
        """Test that protected views redirect unauthenticated users to login"""
        protected_urls = [
            "/myApp/index/",
            "/myApp/salary/",
            "/myApp/company/",
            "/myApp/educational/",
            "/myApp/address/",
            "/myApp/joblist/",
            "/myApp/api/salary/data/",
            "/myApp/api/company/data/",
            "/myApp/api/educational/data/",
            "/myApp/api/address/data/",
            "/myApp/api/job/search/",
            "/myApp/api/ml/salary_predict/",
            "/myApp/api/ml/job_recommend/",
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"{url} should redirect")
