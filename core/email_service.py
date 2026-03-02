"""
Сервис для работы с email: отправка уведомлений и приём запросов на сертификаты.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict
from config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Сервис для отправки email-уведомлений о сертификатах."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        """Проверяет, настроен ли email."""
        return (
            self.settings.email_enabled
            and bool(self.settings.email_smtp_host)
            and bool(self.settings.email_smtp_user)
            and bool(self.settings.email_smtp_password)
        )

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """Создает SMTP-соединение."""
        smtp = smtplib.SMTP(self.settings.email_smtp_host, self.settings.email_smtp_port)
        smtp.starttls()
        smtp.login(self.settings.email_smtp_user, self.settings.email_smtp_password)
        return smtp

    def send_certificate_notification(self, certificate_data: dict, recipient: Optional[str] = None) -> bool:
        """
        Отправляет уведомление о созданном сертификате.

        Args:
            certificate_data: Данные сертификата
            recipient: Адрес получателя (по умолчанию email_request_to)

        Returns:
            bool: True если отправлено успешно
        """
        if not self.is_configured:
            logger.debug("Email не настроен, пропускаем отправку")
            return False

        to_email = recipient or self.settings.email_request_to
        if not to_email:
            logger.warning("Не указан адрес получателя для email")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Новый сертификат: {certificate_data.get('certificate_id', 'N/A')}"
            msg['From'] = self.settings.email_from
            msg['To'] = to_email

            text_body = self._format_certificate_text(certificate_data)
            html_body = self._format_certificate_html(certificate_data)

            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            with self._create_smtp_connection() as smtp:
                smtp.send_message(msg)

            logger.info(f"Email-уведомление отправлено на {to_email}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки email на {to_email}: {e}")
            return False

    def send_certificate_request(self, request_data: dict, sender_name: str, sender_email: str) -> bool:
        """
        Отправляет запрос на создание сертификата по email.

        Args:
            request_data: Данные запроса (domain, inn, period, users_count)
            sender_name: Имя отправителя
            sender_email: Email отправителя

        Returns:
            bool: True если отправлено успешно
        """
        if not self.is_configured:
            return False

        if not self.settings.email_request_to:
            logger.warning("Не указан адрес для запросов")
            return False

        # Проверяем, разрешен ли отправитель
        if not self.settings.is_email_sender_allowed(sender_email):
            logger.warning(f"Отправитель {sender_email} не в списке разрешенных")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Запрос на сертификат: {request_data.get('domain', 'N/A')}"
            msg['From'] = self.settings.email_from
            msg['To'] = self.settings.email_request_to
            msg['Reply-To'] = sender_email

            text_body = (
                f"Запрос на создание сертификата\n\n"
                f"От: {sender_name} <{sender_email}>\n\n"
                f"Домен: {request_data.get('domain', 'N/A')}\n"
                f"ИНН: {request_data.get('inn', 'N/A')}\n"
                f"Период: {request_data.get('valid_from', 'N/A')} - {request_data.get('valid_to', 'N/A')}\n"
                f"Количество пользователей: {request_data.get('users_count', 'N/A')}\n"
            )

            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))

            with self._create_smtp_connection() as smtp:
                smtp.send_message(msg)

            logger.info(f"Запрос на сертификат отправлен от {sender_email}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки запроса: {e}")
            return False

    def get_allowed_senders(self) -> List[Dict[str, str]]:
        """Возвращает список разрешенных отправителей."""
        return self.settings.email_allowed_senders_list

    def _format_certificate_text(self, data: dict) -> str:
        """Форматирует данные сертификата в текст."""
        return (
            f"Создан новый сертификат технической поддержки\n\n"
            f"ID: {data.get('certificate_id', 'N/A')}\n"
            f"Домен: {data.get('domain', 'N/A')}\n"
            f"ИНН: {data.get('inn', 'N/A')}\n"
            f"Период: {data.get('validity_period', 'N/A')}\n"
            f"Пользователей: {data.get('users_count', 'N/A')}\n"
            f"Статус: {data.get('status_text', 'N/A')}\n"
            f"Создатель: {data.get('created_by_name', 'N/A')}\n"
        )

    def _format_certificate_html(self, data: dict) -> str:
        """Форматирует данные сертификата в HTML."""
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Создан новый сертификат технической поддержки</h2>
            <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
                <tr style="background: #f5f5f5;">
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>ID сертификата</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd;"><code>{data.get('certificate_id', 'N/A')}</code></td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>Домен</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{data.get('domain', 'N/A')}</td>
                </tr>
                <tr style="background: #f5f5f5;">
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>ИНН</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{data.get('inn', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>Период</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{data.get('validity_period', 'N/A')}</td>
                </tr>
                <tr style="background: #f5f5f5;">
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>Пользователей</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{data.get('users_count', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>Статус</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{data.get('status_text', 'N/A')}</td>
                </tr>
            </table>
        </body>
        </html>
        """


# Глобальный экземпляр
_email_service = None


def get_email_service() -> EmailService:
    """Возвращает экземпляр email-сервиса."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
