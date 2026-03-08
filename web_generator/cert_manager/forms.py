from django import forms
from django.utils import timezone
from .models import Certificate
from .validators import validate_domain, validate_inn


class CertificateCreateForm(forms.ModelForm):
    """Форма создания сертификата."""

    domain = forms.CharField(
        label='Домен', max_length=255,
        validators=[validate_domain],
        widget=forms.TextInput(attrs={
            'placeholder': 'example.com или *.example.com',
            'class': 'form-control'
        })
    )
    inn = forms.CharField(
        label='ИНН / БИН', min_length=10, max_length=12,
        validators=[validate_inn],
        widget=forms.TextInput(attrs={
            'placeholder': '10 или 12 цифр', 'class': 'form-control'
        })
    )
    valid_from = forms.DateField(
        label='Действует с',
        widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'form-control'
        })
    )
    valid_to = forms.DateField(
        label='Действует до',
        widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'form-control'
        })
    )
    users_count = forms.IntegerField(
        label='Количество пользователей', min_value=1,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Минимум 1', 'class': 'form-control'
        })
    )
    request_email = forms.EmailField(
        label='Email для запросов', required=False,
        widget=forms.EmailInput(attrs={
            'placeholder': 'support@example.com', 'class': 'form-control'
        })
    )

    class Meta:
        model = Certificate
        fields = ['domain', 'inn', 'valid_from', 'valid_to',
                  'users_count', 'request_email']

    def clean(self):
        cleaned = super().clean()
        vf = cleaned.get('valid_from')
        vt = cleaned.get('valid_to')

        if vf and vt:
            if vt <= vf:
                raise forms.ValidationError(
                    'Дата окончания должна быть позже даты начала.'
                )
            years = (vt - vf).days / 365.25
            if years > 5:
                raise forms.ValidationError(
                    'Период действия не может превышать 5 лет.'
                )
            if vf < timezone.now().date():
                raise forms.ValidationError(
                    'Дата начала не может быть в прошлом.'
                )
        return cleaned


class CertificateEditDatesForm(forms.Form):
    """Форма редактирования дат сертификата.

    Намеренно разрешает valid_from в прошлом — для корректировки ошибочно
    введённых дат. В отличие от CertificateCreateForm, здесь нет запрета
    на прошлые даты.
    """

    new_valid_from = forms.DateField(
        label='Новая дата начала',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    new_valid_to = forms.DateField(
        label='Новая дата окончания',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    edit_reason = forms.CharField(
        label='Причина изменения', required=False,
        widget=forms.Textarea(attrs={
            'rows': 2, 'class': 'form-control',
            'placeholder': 'Укажите причину изменения дат'
        })
    )

    def clean(self):
        cleaned = super().clean()
        vf = cleaned.get('new_valid_from')
        vt = cleaned.get('new_valid_to')

        if vf and vt:
            if vt <= vf:
                raise forms.ValidationError(
                    'Дата окончания должна быть позже даты начала.'
                )
            years = (vt - vf).days / 365.25
            if years > 5:
                raise forms.ValidationError(
                    'Период действия не может превышать 5 лет.'
                )
        return cleaned


class CertificateSearchForm(forms.Form):
    """Форма поиска сертификатов."""

    q = forms.CharField(
        label='Поиск', required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Домен, ИНН или ID сертификата',
            'class': 'form-control'
        })
    )
    status = forms.ChoiceField(
        label='Статус', required=False,
        choices=[
            ('', 'Все'),
            ('active', 'Активные'),
            ('expiring', 'Истекающие'),
            ('expired', 'Просроченные'),
            ('inactive', 'Деактивированные'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
