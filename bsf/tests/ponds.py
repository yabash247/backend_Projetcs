from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test import TestCase
from bsf.models import Company

User = get_user_model()

class PondViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create and log in a test user
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.login(username='testuser', password='testpassword')

        # Create a company associated with the test user
        self.company = Company.objects.create(name='Test Company', creator=self.user)

    def test_create_pond(self):
        data = {
            "name": "Test Pond",
        }
        response = self.client.post('/api/bsf/ponds/?company=5&farm=8', data=data)
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Data: {response.data}")
        self.assertEqual(response.status_code, 201)
