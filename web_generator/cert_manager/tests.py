"""
Тесты для cert_manager.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .generator import CertificateIDGenerator
from .models import Certificate, CertificateHistory, NotificationLog
from .validators import validate_domain, validate_inn
from django.core.exceptions import ValidationError


# ==========================================
# Unit: Генератор ID
# ==========================================

class CertificateIDGeneratorTest(TestCase):
    def setUp(self):
        self.gen = CertificateIDGenerator()

    def test_generate_format(self):
        cert_id = self.gen.generate(date(2025, 12, 31))
        self.assertEqual(len(cert_id), 23)
        parts = cert_id.split('-')
        self.assertEqual(len(parts), 4)
        for part in parts:
            self.assertEqual(len(part), 5)

    def test_generate_embeds_date(self):
        cert_id = self.gen.generate(date(2025, 5, 15))
        # Последний блок: X + MMYY = X0525
        last_block = cert_id.split('-')[-1]
        self.assertEqual(last_block[1:], '0525')

    def test_generate_uniqueness(self):
        """Уникальность обеспечивается DB constraint, но генератор должен давать разные ID."""
        ids = {self.gen.generate(date(2025, 12, 31)) for _ in range(50)}
        self.assertGreater(len(ids), 45)  # допускаем редкие коллизии

    def test_validate_format_valid(self):
        cert_id = self.gen.generate(date(2025, 6, 1))
        self.assertTrue(self.gen.validate_format(cert_id))

    def test_validate_format_invalid(self):
        self.assertFalse(self.gen.validate_format(''))
        self.assertFalse(self.gen.validate_format('INVALID'))
        self.assertFalse(self.gen.validate_format('ABC-DEF-GHI-JKL'))  # wrong lengths

    def test_extract_expiry(self):
        cert_id = self.gen.generate(date(2026, 3, 1))
        month, year = self.gen.extract_expiry(cert_id)
        self.assertEqual(month, 3)
        self.assertEqual(year, 2026)


# ==========================================
# Unit: Валидаторы
# ==========================================

class ValidateDomainTest(TestCase):
    def test_valid_domains(self):
        for d in ['example.com', 'sub.example.com', '*.example.com', 'a-b.example.com']:
            validate_domain(d)  # Should not raise

    def test_invalid_domains(self):
        for d in ['', 'a', '-example.com', 'example', 'ex ample.com']:
            with self.assertRaises(ValidationError):
                validate_domain(d)


class ValidateINNTest(TestCase):
    def test_valid_inn_10(self):
        validate_inn('7707083893')  # Valid 10-digit INN

    def test_invalid_inn_wrong_length(self):
        with self.assertRaises(ValidationError):
            validate_inn('123')

    def test_invalid_inn_not_digits(self):
        with self.assertRaises(ValidationError):
            validate_inn('12345abcde')


# ==========================================
# Smoke: Views
# ==========================================

class ViewSmokeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='admin', password='adminpass123', is_staff=True
        )

    def test_login_page_accessible(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_dashboard_accessible_after_login(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_certificate_list_accessible(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('certificate_list'))
        self.assertEqual(resp.status_code, 200)

    def test_certificate_create_requires_staff(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 403)

    def test_certificate_create_accessible_for_staff(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 200)

    def test_notification_log_accessible(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('notification_log'))
        self.assertEqual(resp.status_code, 200)


class CertificateCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin', password='adminpass123', is_staff=True
        )
        self.client.login(username='admin', password='adminpass123')

    def test_create_certificate_success(self):
        today = timezone.now().date()
        resp = self.client.post(reverse('certificate_create'), {
            'domain': 'example.com',
            'inn': '7707083893',
            'valid_from': str(today),
            'valid_to': str(today + timedelta(days=365)),
            'users_count': 100,
        })
        self.assertEqual(resp.status_code, 302)  # redirect to detail
        self.assertEqual(Certificate.objects.count(), 1)
        cert = Certificate.objects.first()
        self.assertEqual(cert.domain, 'example.com')

    def test_create_certificate_invalid_inn(self):
        today = timezone.now().date()
        resp = self.client.post(reverse('certificate_create'), {
            'domain': 'example.com',
            'inn': '0000000000',
            'valid_from': str(today),
            'valid_to': str(today + timedelta(days=365)),
            'users_count': 100,
        })
        self.assertEqual(resp.status_code, 200)  # re-renders form
        self.assertEqual(Certificate.objects.count(), 0)


class CertificateRBACTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='operator', password='pass123'
        )
        self.admin = User.objects.create_user(
            username='admin', password='pass123', is_staff=True
        )
        # Create a certificate as admin
        self.client.login(username='admin', password='pass123')
        today = timezone.now().date()
        self.client.post(reverse('certificate_create'), {
            'domain': 'test.com',
            'inn': '7707083893',
            'valid_from': str(today),
            'valid_to': str(today + timedelta(days=365)),
            'users_count': 50,
        })
        self.cert = Certificate.objects.first()

    def test_operator_can_view_detail(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.get(
            reverse('certificate_detail', args=[self.cert.certificate_id])
        )
        self.assertEqual(resp.status_code, 200)

    def test_operator_cannot_deactivate(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id])
        )
        self.assertEqual(resp.status_code, 403)

    def test_operator_cannot_edit_dates(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.get(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id])
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_deactivate(self):
        self.client.login(username='admin', password='pass123')
        resp = self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id])
        )
        self.assertEqual(resp.status_code, 302)
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.is_active)

    def test_activate_shows_confirmation(self):
        # Deactivate first
        self.cert.is_active = False
        self.cert.save()

        self.client.login(username='admin', password='pass123')
        resp = self.client.get(
            reverse('certificate_activate', args=[self.cert.certificate_id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Активация сертификата')


# ==========================================
# Unit: NotificationLog uniqueness
# ==========================================

class NotificationLogTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', password='pass', is_staff=True
        )
        self.cert = Certificate.objects.create(
            certificate_id='AAAAA-BBBBB-CCCCC-D0326',
            domain='test.com',
            inn='7707083893',
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=365),
            users_count=10,
            created_by=self.admin,
        )

    def test_can_create_same_type_different_valid_to(self):
        """After certificate renewal, new expiry notifications should be allowed."""
        NotificationLog.objects.create(
            certificate=self.cert,
            notification_type='expiry_2m',
            valid_to_date=date(2027, 3, 26),
            recipients='a@b.com',
        )
        # Same cert, same type, different valid_to_date — should work
        NotificationLog.objects.create(
            certificate=self.cert,
            notification_type='expiry_2m',
            valid_to_date=date(2028, 3, 26),
            recipients='a@b.com',
        )
        self.assertEqual(
            NotificationLog.objects.filter(certificate=self.cert).count(), 2
        )
