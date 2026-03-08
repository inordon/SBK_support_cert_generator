"""
Тесты для cert_manager.
Запуск: python manage.py test cert_manager --settings=web_generator.test_settings
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, Client, override_settings
from django.urls import reverse, resolve
from django.utils import timezone

from .decorators import admin_required
from .forms import CertificateCreateForm, CertificateEditDatesForm, CertificateSearchForm
from .generator import CertificateIDGenerator
from .models import Certificate, CertificateHistory, NotificationLog
from .services import send_certificate_notification, send_expiry_notification
from .templatetags.cert_tags import status_badge
from .validators import validate_domain, validate_inn


# ==========================================
# Helpers
# ==========================================

def _make_cert(user, **kwargs):
    """Хелпер для быстрого создания сертификата."""
    today = timezone.now().date()
    defaults = {
        'certificate_id': 'AAAAA-BBBBB-CCCCC-D0326',
        'domain': 'test.com',
        'inn': '7707083893',
        'valid_from': today,
        'valid_to': today + timedelta(days=365),
        'users_count': 10,
        'created_by': user,
    }
    defaults.update(kwargs)
    return Certificate.objects.create(**defaults)


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
        last_block = cert_id.split('-')[-1]
        self.assertEqual(last_block[1:], '0525')

    def test_generate_embeds_date_january(self):
        cert_id = self.gen.generate(date(2030, 1, 1))
        last_block = cert_id.split('-')[-1]
        self.assertEqual(last_block[1:], '0130')

    def test_generate_embeds_date_december(self):
        cert_id = self.gen.generate(date(2028, 12, 31))
        last_block = cert_id.split('-')[-1]
        self.assertEqual(last_block[1:], '1228')

    def test_generate_uniqueness(self):
        existing = set()
        for _ in range(50):
            cert_id = self.gen.generate(date(2025, 12, 31), existing)
            self.assertNotIn(cert_id, existing)
            existing.add(cert_id)

    def test_generate_with_existing_ids_avoids_collisions(self):
        """Генератор не выдаёт ID из множества existing_ids."""
        existing = set()
        for _ in range(100):
            cert_id = self.gen.generate(date(2025, 6, 1), existing)
            existing.add(cert_id)
        self.assertEqual(len(existing), 100)

    def test_validate_format_valid(self):
        cert_id = self.gen.generate(date(2025, 6, 1))
        self.assertTrue(self.gen.validate_format(cert_id))

    def test_validate_format_invalid(self):
        self.assertFalse(self.gen.validate_format(''))
        self.assertFalse(self.gen.validate_format('INVALID'))
        self.assertFalse(self.gen.validate_format('ABC-DEF-GHI-JKL'))

    def test_validate_format_wrong_length(self):
        self.assertFalse(self.gen.validate_format('A' * 22))
        self.assertFalse(self.gen.validate_format('A' * 24))

    def test_validate_format_lowercase_rejected(self):
        self.assertFalse(self.gen.validate_format('aaaaa-BBBBB-CCCCC-DDDDD'))

    def test_validate_format_special_chars_rejected(self):
        self.assertFalse(self.gen.validate_format('AAAA!-BBBBB-CCCCC-DDDDD'))

    def test_validate_format_none(self):
        self.assertFalse(self.gen.validate_format(None))

    def test_extract_expiry(self):
        cert_id = self.gen.generate(date(2026, 3, 1))
        month, year = self.gen.extract_expiry(cert_id)
        self.assertEqual(month, 3)
        self.assertEqual(year, 2026)

    def test_extract_expiry_december(self):
        cert_id = self.gen.generate(date(2030, 12, 15))
        month, year = self.gen.extract_expiry(cert_id)
        self.assertEqual(month, 12)
        self.assertEqual(year, 2030)

    def test_characters_are_uppercase_and_digits(self):
        """Все символы в ID — заглавные буквы или цифры."""
        cert_id = self.gen.generate(date(2025, 6, 1))
        for char in cert_id.replace('-', ''):
            self.assertTrue(char.isupper() or char.isdigit())


# ==========================================
# Unit: Валидаторы
# ==========================================

class ValidateDomainTest(TestCase):
    def test_valid_domains(self):
        for d in ['example.com', 'sub.example.com', '*.example.com',
                   'a-b.example.com', 'test.co.uk', 'my-site.example.org']:
            validate_domain(d)  # Should not raise

    def test_invalid_empty(self):
        with self.assertRaises(ValidationError):
            validate_domain('')

    def test_invalid_none(self):
        with self.assertRaises(ValidationError):
            validate_domain(None)

    def test_invalid_single_part(self):
        with self.assertRaises(ValidationError):
            validate_domain('example')

    def test_invalid_starts_with_dash(self):
        with self.assertRaises(ValidationError):
            validate_domain('-example.com')

    def test_invalid_spaces(self):
        with self.assertRaises(ValidationError):
            validate_domain('ex ample.com')

    def test_invalid_too_long(self):
        with self.assertRaises(ValidationError):
            validate_domain('a' * 256)

    def test_invalid_part_too_long(self):
        with self.assertRaises(ValidationError):
            validate_domain('a' * 64 + '.com')

    def test_wildcard_valid(self):
        validate_domain('*.example.com')

    def test_wildcard_only_prefix(self):
        """Wildcard только в начале: *.domain.com — ОК."""
        validate_domain('*.sub.example.com')

    def test_invalid_double_dot(self):
        with self.assertRaises(ValidationError):
            validate_domain('example..com')

    def test_valid_single_char_parts(self):
        validate_domain('a.b.com')


class ValidateINNTest(TestCase):
    def test_valid_inn_10(self):
        validate_inn('7707083893')

    def test_invalid_inn_wrong_length(self):
        with self.assertRaises(ValidationError):
            validate_inn('123')

    def test_invalid_inn_not_digits(self):
        with self.assertRaises(ValidationError):
            validate_inn('12345abcde')

    def test_invalid_inn_empty(self):
        with self.assertRaises(ValidationError):
            validate_inn('')

    def test_invalid_inn_none(self):
        with self.assertRaises(ValidationError):
            validate_inn(None)

    def test_invalid_inn_10_wrong_checksum(self):
        with self.assertRaises(ValidationError):
            validate_inn('7707083890')

    def test_valid_inn_12_russian(self):
        """12-значный российский ИНН с корректной контрольной суммой."""
        validate_inn('500100732259')

    def test_valid_bin_12_kazakhstan(self):
        """12-значный БИН Казахстана с корректным месяцем."""
        validate_inn('990140000385')

    def test_invalid_inn_12_bad_checksum_and_month(self):
        """12-значный ИНН с неверной контрольной суммой и невалидным месяцем для БИН."""
        with self.assertRaises(ValidationError):
            validate_inn('123456789010')

    def test_invalid_inn_7_digits(self):
        with self.assertRaises(ValidationError):
            validate_inn('1234567')

    def test_invalid_inn_15_digits(self):
        with self.assertRaises(ValidationError):
            validate_inn('123456789012345')


# ==========================================
# Unit: Модели
# ==========================================

class CertificateModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='pass')

    def test_str(self):
        cert = _make_cert(self.user)
        self.assertEqual(str(cert), 'AAAAA-BBBBB-CCCCC-D0326 — test.com')

    def test_validity_period(self):
        cert = _make_cert(self.user,
                          valid_from=date(2025, 1, 15),
                          valid_to=date(2026, 1, 15))
        self.assertEqual(cert.validity_period, '15.01.2025 — 15.01.2026')

    def test_days_left_active(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=10),
                          valid_to=today + timedelta(days=100))
        self.assertEqual(cert.days_left, 100)

    def test_days_left_expired(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=400),
                          valid_to=today - timedelta(days=10))
        self.assertEqual(cert.days_left, 0)

    def test_days_left_not_started(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today + timedelta(days=10),
                          valid_to=today + timedelta(days=400))
        self.assertEqual(cert.days_left, 0)

    def test_status_inactive(self):
        cert = _make_cert(self.user, is_active=False)
        self.assertEqual(cert.status, 'inactive')

    def test_status_not_started(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today + timedelta(days=30),
                          valid_to=today + timedelta(days=400))
        self.assertEqual(cert.status, 'not_started')

    def test_status_expired(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=400),
                          valid_to=today - timedelta(days=1))
        self.assertEqual(cert.status, 'expired')

    def test_status_expiring_critical(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=100),
                          valid_to=today + timedelta(days=5))
        self.assertEqual(cert.status, 'expiring_critical')

    def test_status_expiring_soon(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=100),
                          valid_to=today + timedelta(days=20))
        self.assertEqual(cert.status, 'expiring_soon')

    def test_status_expiring_warning(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=100),
                          valid_to=today + timedelta(days=45))
        self.assertEqual(cert.status, 'expiring_warning')

    def test_status_active(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=10),
                          valid_to=today + timedelta(days=200))
        self.assertEqual(cert.status, 'active')

    def test_status_display_returns_tuple(self):
        cert = _make_cert(self.user)
        text, badge = cert.status_display
        self.assertIsInstance(text, str)
        self.assertIn(badge, ['success', 'warning', 'danger', 'secondary'])

    def test_status_display_inactive(self):
        cert = _make_cert(self.user, is_active=False)
        text, badge = cert.status_display
        self.assertEqual(badge, 'danger')
        self.assertIn('Деактивирован', text)

    def test_default_is_active_true(self):
        cert = _make_cert(self.user)
        self.assertTrue(cert.is_active)

    def test_default_contacts_empty_list(self):
        cert = _make_cert(self.user)
        self.assertEqual(cert.contacts, [])

    def test_ordering_by_created_at_desc(self):
        c1 = _make_cert(self.user, certificate_id='AAAAA-BBBBB-CCCCC-A0326')
        c2 = _make_cert(self.user, certificate_id='AAAAA-BBBBB-CCCCC-B0326')
        certs = list(Certificate.objects.all())
        self.assertEqual(certs[0], c2)
        self.assertEqual(certs[1], c1)


class CertificateHistoryModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('admin', password='pass', is_staff=True)
        self.cert = _make_cert(self.user)

    def test_str(self):
        h = CertificateHistory.objects.create(
            certificate=self.cert, action='created', performed_by=self.user)
        self.assertIn('Создан', str(h))

    def test_history_linked_to_cert(self):
        CertificateHistory.objects.create(
            certificate=self.cert, action='created', performed_by=self.user)
        self.assertEqual(self.cert.history.count(), 1)

    def test_details_json(self):
        h = CertificateHistory.objects.create(
            certificate=self.cert, action='dates_updated',
            performed_by=self.user,
            details={'old_valid_from': '2025-01-01', 'new_valid_from': '2025-02-01'})
        h.refresh_from_db()
        self.assertEqual(h.details['old_valid_from'], '2025-01-01')


class NotificationLogModelTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pass', is_staff=True)
        self.cert = _make_cert(self.admin)

    def test_can_create_same_type_different_valid_to(self):
        NotificationLog.objects.create(
            certificate=self.cert, notification_type='expiry_2m',
            valid_to_date=date(2027, 3, 26), recipients='a@b.com')
        NotificationLog.objects.create(
            certificate=self.cert, notification_type='expiry_2m',
            valid_to_date=date(2028, 3, 26), recipients='a@b.com')
        self.assertEqual(
            NotificationLog.objects.filter(certificate=self.cert).count(), 2)

    def test_unique_constraint_same_cert_type_date(self):
        NotificationLog.objects.create(
            certificate=self.cert, notification_type='expiry_1m',
            valid_to_date=date(2027, 3, 26), recipients='a@b.com')
        with self.assertRaises(IntegrityError):
            NotificationLog.objects.create(
                certificate=self.cert, notification_type='expiry_1m',
                valid_to_date=date(2027, 3, 26), recipients='a@b.com')

    def test_str(self):
        log = NotificationLog.objects.create(
            certificate=self.cert, notification_type='created',
            recipients='a@b.com')
        self.assertIn('Создание', str(log))

    def test_different_types_same_date_allowed(self):
        NotificationLog.objects.create(
            certificate=self.cert, notification_type='expiry_2m',
            valid_to_date=date(2027, 3, 26), recipients='a@b.com')
        NotificationLog.objects.create(
            certificate=self.cert, notification_type='expiry_1m',
            valid_to_date=date(2027, 3, 26), recipients='a@b.com')
        self.assertEqual(
            NotificationLog.objects.filter(certificate=self.cert).count(), 2)


# ==========================================
# Unit: Формы
# ==========================================

class CertificateCreateFormTest(TestCase):
    def _form_data(self, **overrides):
        today = timezone.now().date()
        data = {
            'domain': 'example.com',
            'inn': '7707083893',
            'valid_from': str(today),
            'valid_to': str(today + timedelta(days=365)),
            'users_count': 100,
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = CertificateCreateForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_domain(self):
        form = CertificateCreateForm(data=self._form_data(domain='bad'))
        self.assertFalse(form.is_valid())
        self.assertIn('domain', form.errors)

    def test_invalid_inn(self):
        form = CertificateCreateForm(data=self._form_data(inn='7707083890'))
        self.assertFalse(form.is_valid())
        self.assertIn('inn', form.errors)

    def test_valid_to_before_valid_from(self):
        today = timezone.now().date()
        form = CertificateCreateForm(data=self._form_data(
            valid_from=str(today),
            valid_to=str(today - timedelta(days=1))))
        self.assertFalse(form.is_valid())

    def test_period_exceeds_5_years(self):
        today = timezone.now().date()
        form = CertificateCreateForm(data=self._form_data(
            valid_to=str(today + timedelta(days=365 * 6))))
        self.assertFalse(form.is_valid())

    def test_valid_from_in_past(self):
        today = timezone.now().date()
        form = CertificateCreateForm(data=self._form_data(
            valid_from=str(today - timedelta(days=1)),
            valid_to=str(today + timedelta(days=365))))
        self.assertFalse(form.is_valid())

    def test_users_count_zero(self):
        form = CertificateCreateForm(data=self._form_data(users_count=0))
        self.assertFalse(form.is_valid())
        self.assertIn('users_count', form.errors)

    def test_users_count_negative(self):
        form = CertificateCreateForm(data=self._form_data(users_count=-5))
        self.assertFalse(form.is_valid())

    def test_optional_request_email(self):
        form = CertificateCreateForm(data=self._form_data(
            request_email='admin@test.com'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_request_email(self):
        form = CertificateCreateForm(data=self._form_data(
            request_email='not-an-email'))
        self.assertFalse(form.is_valid())

    def test_wildcard_domain_valid(self):
        form = CertificateCreateForm(data=self._form_data(domain='*.example.com'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_same_valid_from_and_to(self):
        today = timezone.now().date()
        form = CertificateCreateForm(data=self._form_data(
            valid_from=str(today), valid_to=str(today)))
        self.assertFalse(form.is_valid())


class CertificateEditDatesFormTest(TestCase):
    def test_valid_form(self):
        today = timezone.now().date()
        form = CertificateEditDatesForm(data={
            'new_valid_from': str(today),
            'new_valid_to': str(today + timedelta(days=365)),
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_to_before_from(self):
        today = timezone.now().date()
        form = CertificateEditDatesForm(data={
            'new_valid_from': str(today),
            'new_valid_to': str(today - timedelta(days=1)),
        })
        self.assertFalse(form.is_valid())

    def test_period_exceeds_5_years(self):
        today = timezone.now().date()
        form = CertificateEditDatesForm(data={
            'new_valid_from': str(today),
            'new_valid_to': str(today + timedelta(days=365 * 6)),
        })
        self.assertFalse(form.is_valid())

    def test_edit_reason_optional(self):
        today = timezone.now().date()
        form = CertificateEditDatesForm(data={
            'new_valid_from': str(today),
            'new_valid_to': str(today + timedelta(days=365)),
            'edit_reason': 'Продление по запросу клиента',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['edit_reason'],
                         'Продление по запросу клиента')

    def test_missing_valid_from(self):
        today = timezone.now().date()
        form = CertificateEditDatesForm(data={
            'new_valid_to': str(today + timedelta(days=365)),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('new_valid_from', form.errors)


class CertificateSearchFormTest(TestCase):
    def test_valid_empty(self):
        form = CertificateSearchForm(data={})
        self.assertTrue(form.is_valid())

    def test_valid_with_query(self):
        form = CertificateSearchForm(data={'q': 'example.com'})
        self.assertTrue(form.is_valid())

    def test_valid_status_choices(self):
        for status in ['', 'active', 'expiring', 'expired', 'inactive']:
            form = CertificateSearchForm(data={'status': status})
            self.assertTrue(form.is_valid(), f'Failed for status={status}')

    def test_invalid_status(self):
        form = CertificateSearchForm(data={'status': 'bogus'})
        self.assertFalse(form.is_valid())


# ==========================================
# Smoke + Integration: Views
# ==========================================

class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')

    def test_login_page_accessible(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 200)

    def test_login_success_redirects_to_dashboard(self):
        resp = self.client.post(reverse('login'), {
            'username': 'testuser', 'password': 'testpass123'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/', resp.url)

    def test_login_failure_shows_form(self):
        resp = self.client.post(reverse('login'), {
            'username': 'testuser', 'password': 'wrongpass'})
        self.assertEqual(resp.status_code, 200)

    def test_login_redirect_next(self):
        resp = self.client.post(
            reverse('login') + '?next=/certificates/',
            {'username': 'testuser', 'password': 'testpass123'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/certificates/', resp.url)

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 302)


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')

    def test_logout_redirects_to_login(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)

    def test_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_accessible_after_login(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_context_contains_stats(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        for key in ['total', 'active', 'expiring', 'expired', 'inactive']:
            self.assertIn(key, resp.context)

    def test_context_contains_recent_certs(self):
        self.client.login(username='admin', password='adminpass123')
        _make_cert(self.admin)
        resp = self.client.get(reverse('dashboard'))
        self.assertIn('recent_certs', resp.context)
        self.assertEqual(len(resp.context['recent_certs']), 1)

    def test_context_contains_recent_history(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertIn('recent_history', resp.context)


class CertificateListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)
        self.client.login(username='testuser', password='testpass123')

    def test_accessible(self):
        resp = self.client.get(reverse('certificate_list'))
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('certificate_list'))
        self.assertEqual(resp.status_code, 302)

    def test_empty_list(self):
        resp = self.client.get(reverse('certificate_list'))
        self.assertEqual(resp.status_code, 200)

    def test_search_by_domain(self):
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-A0326',
                   domain='findme.com')
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-B0326',
                   domain='other.com')
        resp = self.client.get(reverse('certificate_list'), {'q': 'findme'})
        self.assertEqual(len(resp.context['page_obj']), 1)

    def test_search_by_inn(self):
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-A0326',
                   inn='7707083893')
        resp = self.client.get(reverse('certificate_list'), {'q': '7707083893'})
        self.assertEqual(len(resp.context['page_obj']), 1)

    def test_search_by_certificate_id(self):
        _make_cert(self.admin, certificate_id='XXXXX-YYYYY-ZZZZZ-A0326')
        resp = self.client.get(reverse('certificate_list'), {'q': 'XXXXX'})
        self.assertEqual(len(resp.context['page_obj']), 1)

    def test_filter_active(self):
        today = timezone.now().date()
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-A0326',
                   valid_from=today - timedelta(days=10),
                   valid_to=today + timedelta(days=200))
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-B0326',
                   is_active=False)
        resp = self.client.get(reverse('certificate_list'), {'status': 'active'})
        self.assertEqual(len(resp.context['page_obj']), 1)

    def test_filter_inactive(self):
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-A0326')
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-B0326',
                   is_active=False)
        resp = self.client.get(reverse('certificate_list'), {'status': 'inactive'})
        self.assertEqual(len(resp.context['page_obj']), 1)

    def test_filter_expired(self):
        today = timezone.now().date()
        _make_cert(self.admin, certificate_id='AAAAA-BBBBB-CCCCC-A0326',
                   valid_from=today - timedelta(days=400),
                   valid_to=today - timedelta(days=1))
        resp = self.client.get(reverse('certificate_list'), {'status': 'expired'})
        self.assertEqual(len(resp.context['page_obj']), 1)

    def test_pagination(self):
        for i in range(30):
            _make_cert(self.admin,
                       certificate_id=f'AAA{i:02d}-BBBBB-CCCCC-D0326')
        resp = self.client.get(reverse('certificate_list'))
        self.assertEqual(len(resp.context['page_obj']), 25)  # CERTS_PER_PAGE
        resp2 = self.client.get(reverse('certificate_list'), {'page': 2})
        self.assertEqual(len(resp2.context['page_obj']), 5)


class CertificateCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)
        self.user = User.objects.create_user(
            'testuser', password='testpass123')

    def _post_create(self, **overrides):
        self.client.login(username='admin', password='adminpass123')
        today = timezone.now().date()
        data = {
            'domain': 'example.com',
            'inn': '7707083893',
            'valid_from': str(today),
            'valid_to': str(today + timedelta(days=365)),
            'users_count': 100,
        }
        data.update(overrides)
        return self.client.post(reverse('certificate_create'), data)

    def test_create_success(self):
        resp = self._post_create()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Certificate.objects.count(), 1)
        cert = Certificate.objects.first()
        self.assertEqual(cert.domain, 'example.com')
        self.assertEqual(cert.created_by, self.admin)

    def test_create_creates_history(self):
        self._post_create()
        cert = Certificate.objects.first()
        self.assertEqual(cert.history.count(), 1)
        self.assertEqual(cert.history.first().action, 'created')

    def test_create_invalid_inn(self):
        resp = self._post_create(inn='7707083890')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Certificate.objects.count(), 0)

    def test_create_invalid_domain(self):
        resp = self._post_create(domain='bad')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Certificate.objects.count(), 0)

    def test_requires_staff(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 403)

    def test_requires_login(self):
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 302)

    def test_get_shows_form(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 200)

    @patch('cert_manager.views.send_certificate_notification_task')
    def test_create_triggers_notification(self, mock_task):
        self._post_create()
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args[0]
        cert = Certificate.objects.first()
        self.assertEqual(args[0], str(cert.pk))
        self.assertEqual(args[1], 'created')


class CertificateDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)
        self.user = User.objects.create_user(
            'testuser', password='testpass123')
        self.cert = _make_cert(self.admin)

    def test_accessible_by_user(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(
            reverse('certificate_detail', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)

    def test_accessible_by_admin(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.get(
            reverse('certificate_detail', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)

    def test_context_contains_certificate(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(
            reverse('certificate_detail', args=[self.cert.certificate_id]))
        self.assertEqual(resp.context['certificate'], self.cert)

    def test_context_contains_history(self):
        self.client.login(username='testuser', password='testpass123')
        CertificateHistory.objects.create(
            certificate=self.cert, action='created', performed_by=self.admin)
        resp = self.client.get(
            reverse('certificate_detail', args=[self.cert.certificate_id]))
        self.assertEqual(len(resp.context['history']), 1)

    def test_404_for_nonexistent(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(
            reverse('certificate_detail', args=['XXXXX-XXXXX-XXXXX-XXXXX']))
        self.assertEqual(resp.status_code, 404)

    def test_requires_login(self):
        resp = self.client.get(
            reverse('certificate_detail', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 302)


class CertificateEditDatesViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)
        self.user = User.objects.create_user(
            'testuser', password='testpass123')
        self.cert = _make_cert(self.admin)

    def test_get_shows_form(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.get(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)

    def test_requires_staff(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 403)

    @patch('cert_manager.views.send_certificate_notification_task')
    def test_post_updates_dates(self, mock_task):
        self.client.login(username='admin', password='adminpass123')
        today = timezone.now().date()
        new_from = today + timedelta(days=1)
        new_to = today + timedelta(days=500)
        resp = self.client.post(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id]),
            {'new_valid_from': str(new_from), 'new_valid_to': str(new_to)})
        self.assertEqual(resp.status_code, 302)
        self.cert.refresh_from_db()
        self.assertEqual(self.cert.valid_from, new_from)
        self.assertEqual(self.cert.valid_to, new_to)

    @patch('cert_manager.views.send_certificate_notification_task')
    def test_post_creates_history(self, mock_task):
        self.client.login(username='admin', password='adminpass123')
        today = timezone.now().date()
        self.client.post(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id]),
            {'new_valid_from': str(today),
             'new_valid_to': str(today + timedelta(days=500))})
        history = self.cert.history.filter(action='dates_updated')
        self.assertEqual(history.count(), 1)

    @patch('cert_manager.views.send_certificate_notification_task')
    def test_post_triggers_notification(self, mock_task):
        self.client.login(username='admin', password='adminpass123')
        today = timezone.now().date()
        self.client.post(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id]),
            {'new_valid_from': str(today),
             'new_valid_to': str(today + timedelta(days=500))})
        mock_task.delay.assert_called_once()

    def test_post_invalid_data(self):
        self.client.login(username='admin', password='adminpass123')
        today = timezone.now().date()
        resp = self.client.post(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id]),
            {'new_valid_from': str(today),
             'new_valid_to': str(today - timedelta(days=1))})
        self.assertEqual(resp.status_code, 200)  # re-renders form

    def test_404_for_nonexistent(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.get(
            reverse('certificate_edit_dates', args=['XXXXX-XXXXX-XXXXX-XXXXX']))
        self.assertEqual(resp.status_code, 404)


class CertificateDeactivateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)
        self.user = User.objects.create_user(
            'testuser', password='testpass123')
        self.cert = _make_cert(self.admin)

    def test_get_shows_confirmation(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.get(
            reverse('certificate_deactivate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)

    def test_post_deactivates(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 302)
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.is_active)

    def test_post_creates_history(self):
        self.client.login(username='admin', password='adminpass123')
        self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id]))
        history = self.cert.history.filter(action='deactivated')
        self.assertEqual(history.count(), 1)

    def test_requires_staff(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 403)

    def test_requires_login(self):
        resp = self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 302)


class CertificateActivateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)
        self.user = User.objects.create_user(
            'testuser', password='testpass123')
        self.cert = _make_cert(self.admin, is_active=False)

    def test_get_shows_confirmation(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.get(
            reverse('certificate_activate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Активация сертификата')

    def test_post_activates(self):
        self.client.login(username='admin', password='adminpass123')
        resp = self.client.post(
            reverse('certificate_activate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 302)
        self.cert.refresh_from_db()
        self.assertTrue(self.cert.is_active)

    def test_post_creates_history(self):
        self.client.login(username='admin', password='adminpass123')
        self.client.post(
            reverse('certificate_activate', args=[self.cert.certificate_id]))
        history = self.cert.history.filter(action='activated')
        self.assertEqual(history.count(), 1)

    def test_requires_staff(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.post(
            reverse('certificate_activate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 403)


class NotificationLogViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.admin = User.objects.create_user(
            'admin', password='adminpass123', is_staff=True)

    def test_accessible(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('notification_log'))
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        resp = self.client.get(reverse('notification_log'))
        self.assertEqual(resp.status_code, 302)

    def test_shows_logs(self):
        self.client.login(username='testuser', password='testpass123')
        cert = _make_cert(self.admin)
        NotificationLog.objects.create(
            certificate=cert, notification_type='created',
            recipients='a@b.com')
        resp = self.client.get(reverse('notification_log'))
        self.assertEqual(len(resp.context['page_obj']), 1)


# ==========================================
# RBAC тесты
# ==========================================

class CertificateRBACTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('operator', password='pass123')
        self.admin = User.objects.create_user(
            'admin', password='pass123', is_staff=True)
        self.cert = _make_cert(self.admin)

    def test_operator_can_view_detail(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.get(
            reverse('certificate_detail', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)

    def test_operator_cannot_create(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 403)

    def test_operator_cannot_deactivate(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 403)

    def test_operator_cannot_edit_dates(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.get(
            reverse('certificate_edit_dates', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 403)

    def test_operator_cannot_activate(self):
        self.client.login(username='operator', password='pass123')
        self.cert.is_active = False
        self.cert.save()
        resp = self.client.post(
            reverse('certificate_activate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 403)

    def test_operator_can_view_list(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.get(reverse('certificate_list'))
        self.assertEqual(resp.status_code, 200)

    def test_operator_can_view_notifications(self):
        self.client.login(username='operator', password='pass123')
        resp = self.client.get(reverse('notification_log'))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_deactivate(self):
        self.client.login(username='admin', password='pass123')
        resp = self.client.post(
            reverse('certificate_deactivate', args=[self.cert.certificate_id]))
        self.assertEqual(resp.status_code, 302)
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.is_active)


# ==========================================
# Unit: Services (email с мок)
# ==========================================

@override_settings(
    CERT_NOTIFICATION_RECIPIENTS=['admin@example.com'],
    DEFAULT_FROM_EMAIL='certs@example.com',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class SendCertificateNotificationTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            'admin', password='pass', is_staff=True)
        self.cert = _make_cert(self.admin)

    def test_sends_email_on_created(self):
        send_certificate_notification(self.cert, 'created', self.admin)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.cert.certificate_id, mail.outbox[0].subject)

    def test_sends_email_on_updated(self):
        send_certificate_notification(self.cert, 'updated', self.admin)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Изменён', mail.outbox[0].subject)

    def test_creates_notification_log_on_success(self):
        send_certificate_notification(self.cert, 'created', self.admin)
        log = NotificationLog.objects.filter(certificate=self.cert)
        self.assertEqual(log.count(), 1)
        self.assertTrue(log.first().success)

    def test_includes_request_email_in_recipients(self):
        self.cert.request_email = 'client@example.com'
        self.cert.save()
        send_certificate_notification(self.cert, 'created', self.admin)
        self.assertIn('client@example.com', mail.outbox[0].to)

    @override_settings(CERT_NOTIFICATION_RECIPIENTS=[])
    def test_no_recipients_no_email(self):
        self.cert.request_email = ''
        self.cert.save()
        send_certificate_notification(self.cert, 'created', self.admin)
        self.assertEqual(len(mail.outbox), 0)

    @patch('cert_manager.services.send_mail', side_effect=Exception('SMTP error'))
    def test_logs_error_on_failure(self, mock_send):
        send_certificate_notification(self.cert, 'created', self.admin)
        log = NotificationLog.objects.filter(certificate=self.cert).first()
        self.assertFalse(log.success)
        self.assertIn('SMTP error', log.error_message)


@override_settings(
    CERT_NOTIFICATION_RECIPIENTS=['admin@example.com'],
    DEFAULT_FROM_EMAIL='certs@example.com',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class SendExpiryNotificationTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            'admin', password='pass', is_staff=True)
        self.cert = _make_cert(self.admin)

    def test_sends_expiry_email(self):
        send_expiry_notification(self.cert, months_left=2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('2 месяца', mail.outbox[0].subject)

    def test_sends_1_month_email(self):
        send_expiry_notification(self.cert, months_left=1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('1 месяц', mail.outbox[0].subject)

    def test_does_not_send_duplicate(self):
        send_expiry_notification(self.cert, months_left=2)
        self.assertEqual(len(mail.outbox), 1)
        # Second call — should be skipped
        send_expiry_notification(self.cert, months_left=2)
        self.assertEqual(len(mail.outbox), 1)

    def test_sends_after_renewal(self):
        """После продления (изменения valid_to) уведомление отправляется снова."""
        send_expiry_notification(self.cert, months_left=2)
        self.assertEqual(len(mail.outbox), 1)

        # "Renew" the certificate
        self.cert.valid_to = self.cert.valid_to + timedelta(days=365)
        self.cert.save()

        send_expiry_notification(self.cert, months_left=2)
        self.assertEqual(len(mail.outbox), 2)

    def test_creates_log_entry(self):
        send_expiry_notification(self.cert, months_left=2)
        log = NotificationLog.objects.filter(
            certificate=self.cert, notification_type='expiry_2m')
        self.assertEqual(log.count(), 1)

    @override_settings(CERT_NOTIFICATION_RECIPIENTS=[])
    def test_no_recipients_no_email(self):
        self.cert.request_email = ''
        self.cert.save()
        send_expiry_notification(self.cert, months_left=2)
        self.assertEqual(len(mail.outbox), 0)

    @patch('cert_manager.services.send_mail', side_effect=Exception('SMTP error'))
    def test_logs_error_on_failure(self, mock_send):
        send_expiry_notification(self.cert, months_left=2)
        log = NotificationLog.objects.filter(certificate=self.cert).first()
        self.assertFalse(log.success)


# ==========================================
# Unit: Tasks (Celery)
# ==========================================

class SendCertificateNotificationTaskTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            'admin', password='pass', is_staff=True)
        self.cert = _make_cert(self.admin)

    @patch('cert_manager.services.send_certificate_notification')
    def test_calls_service(self, mock_service):
        from .tasks import send_certificate_notification_task
        send_certificate_notification_task(str(self.cert.pk), 'created', self.admin.pk)
        mock_service.assert_called_once_with(self.cert, 'created', self.admin)

    @patch('cert_manager.services.send_certificate_notification')
    def test_handles_missing_certificate(self, mock_service):
        from .tasks import send_certificate_notification_task
        import uuid
        send_certificate_notification_task(str(uuid.uuid4()), 'created')
        mock_service.assert_not_called()

    @patch('cert_manager.services.send_certificate_notification')
    def test_handles_missing_user(self, mock_service):
        from .tasks import send_certificate_notification_task
        send_certificate_notification_task(str(self.cert.pk), 'created', 99999)
        mock_service.assert_called_once_with(self.cert, 'created', None)

    @patch('cert_manager.services.send_certificate_notification')
    def test_handles_no_user_pk(self, mock_service):
        from .tasks import send_certificate_notification_task
        send_certificate_notification_task(str(self.cert.pk), 'updated')
        mock_service.assert_called_once_with(self.cert, 'updated', None)


class CheckExpiringCertificatesTaskTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            'admin', password='pass', is_staff=True)

    @patch('cert_manager.services.send_expiry_notification')
    def test_finds_2_month_expiring_certs(self, mock_notify):
        today = timezone.now().date()
        cert = _make_cert(self.admin,
                          valid_from=today - timedelta(days=300),
                          valid_to=today + timedelta(days=60))
        from .tasks import check_expiring_certificates
        result = check_expiring_certificates()
        self.assertGreaterEqual(result['2_months'], 1)
        mock_notify.assert_any_call(cert, months_left=2)

    @patch('cert_manager.services.send_expiry_notification')
    def test_finds_1_month_expiring_certs(self, mock_notify):
        today = timezone.now().date()
        cert = _make_cert(self.admin,
                          valid_from=today - timedelta(days=335),
                          valid_to=today + timedelta(days=30))
        from .tasks import check_expiring_certificates
        result = check_expiring_certificates()
        self.assertGreaterEqual(result['1_month'], 1)
        mock_notify.assert_any_call(cert, months_left=1)

    @patch('cert_manager.services.send_expiry_notification')
    def test_skips_inactive_certs(self, mock_notify):
        today = timezone.now().date()
        _make_cert(self.admin,
                   valid_from=today - timedelta(days=300),
                   valid_to=today + timedelta(days=60),
                   is_active=False)
        from .tasks import check_expiring_certificates
        result = check_expiring_certificates()
        self.assertEqual(result['2_months'], 0)

    @patch('cert_manager.services.send_expiry_notification')
    def test_no_expiring_certs(self, mock_notify):
        today = timezone.now().date()
        _make_cert(self.admin,
                   valid_from=today,
                   valid_to=today + timedelta(days=365))
        from .tasks import check_expiring_certificates
        result = check_expiring_certificates()
        self.assertEqual(result['2_months'], 0)
        self.assertEqual(result['1_month'], 0)


# ==========================================
# Unit: Декораторы
# ==========================================

class AdminRequiredDecoratorTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('user', password='pass')
        self.admin = User.objects.create_user(
            'admin', password='pass', is_staff=True)

    def test_anonymous_redirected(self):
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_regular_user_gets_403(self):
        self.client.login(username='user', password='pass')
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 403)

    def test_staff_user_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('certificate_create'))
        self.assertEqual(resp.status_code, 200)


# ==========================================
# Unit: Template Tags
# ==========================================

class StatusBadgeTagTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('admin', password='pass', is_staff=True)

    def test_active_badge(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=10),
                          valid_to=today + timedelta(days=200))
        html = status_badge(cert)
        self.assertIn('badge', html)
        self.assertIn('bg-success', html)

    def test_inactive_badge(self):
        cert = _make_cert(self.user, is_active=False)
        html = status_badge(cert)
        self.assertIn('bg-danger', html)
        self.assertIn('Деактивирован', html)

    def test_expired_badge(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=400),
                          valid_to=today - timedelta(days=1))
        html = status_badge(cert)
        self.assertIn('bg-danger', html)
        self.assertIn('Просрочен', html)

    def test_expiring_warning_badge(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=100),
                          valid_to=today + timedelta(days=45))
        html = status_badge(cert)
        self.assertIn('bg-warning', html)

    def test_expiring_critical_badge(self):
        today = timezone.now().date()
        cert = _make_cert(self.user,
                          valid_from=today - timedelta(days=100),
                          valid_to=today + timedelta(days=5))
        html = status_badge(cert)
        self.assertIn('bg-danger', html)


# ==========================================
# URL Routing
# ==========================================

class URLRoutingTest(TestCase):
    def test_login_url(self):
        self.assertEqual(reverse('login'), '/login/')

    def test_logout_url(self):
        self.assertEqual(reverse('logout'), '/logout/')

    def test_dashboard_url(self):
        self.assertEqual(reverse('dashboard'), '/')

    def test_certificate_list_url(self):
        self.assertEqual(reverse('certificate_list'), '/certificates/')

    def test_certificate_create_url(self):
        self.assertEqual(reverse('certificate_create'), '/certificates/create/')

    def test_certificate_detail_url(self):
        url = reverse('certificate_detail', args=['AAAAA-BBBBB-CCCCC-DDDDD'])
        self.assertEqual(url, '/certificates/AAAAA-BBBBB-CCCCC-DDDDD/')

    def test_certificate_edit_dates_url(self):
        url = reverse('certificate_edit_dates', args=['AAAAA-BBBBB-CCCCC-DDDDD'])
        self.assertEqual(url, '/certificates/AAAAA-BBBBB-CCCCC-DDDDD/edit-dates/')

    def test_certificate_deactivate_url(self):
        url = reverse('certificate_deactivate', args=['AAAAA-BBBBB-CCCCC-DDDDD'])
        self.assertEqual(url, '/certificates/AAAAA-BBBBB-CCCCC-DDDDD/deactivate/')

    def test_certificate_activate_url(self):
        url = reverse('certificate_activate', args=['AAAAA-BBBBB-CCCCC-DDDDD'])
        self.assertEqual(url, '/certificates/AAAAA-BBBBB-CCCCC-DDDDD/activate/')

    def test_notification_log_url(self):
        self.assertEqual(reverse('notification_log'), '/notifications/')

    def test_all_urls_resolve(self):
        """Все URL резолвятся к корректным view-функциям."""
        from . import views
        self.assertEqual(resolve('/login/').func, views.login_view)
        self.assertEqual(resolve('/logout/').func, views.logout_view)
        self.assertEqual(resolve('/').func, views.dashboard)
        self.assertEqual(resolve('/certificates/').func, views.certificate_list)
        self.assertEqual(resolve('/certificates/create/').func, views.certificate_create)
        self.assertEqual(resolve('/notifications/').func, views.notification_log)


# ==========================================
# Admin
# ==========================================

class AdminSiteTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'superadmin', 'admin@test.com', 'pass')
        self.client = Client()
        self.client.login(username='superadmin', password='pass')

    def test_certificate_admin_accessible(self):
        resp = self.client.get('/admin/cert_manager/certificate/')
        self.assertEqual(resp.status_code, 200)

    def test_certificate_history_admin_accessible(self):
        resp = self.client.get('/admin/cert_manager/certificatehistory/')
        self.assertEqual(resp.status_code, 200)

    def test_notification_log_admin_accessible(self):
        resp = self.client.get('/admin/cert_manager/notificationlog/')
        self.assertEqual(resp.status_code, 200)

    def test_certificate_admin_search(self):
        admin_user = User.objects.create_user(
            'admin2', password='pass', is_staff=True)
        _make_cert(admin_user)
        resp = self.client.get('/admin/cert_manager/certificate/?q=test.com')
        self.assertEqual(resp.status_code, 200)
