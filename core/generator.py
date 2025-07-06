"""
Генератор уникальных номеров сертификатов.
"""

import random
import string
from datetime import date
from typing import Set
from .exceptions import GenerationError


class CertificateIDGenerator:
    """Генератор уникальных ID сертификатов."""

    def __init__(self):
        # Символы для генерации ID (латинские буквы в верхнем регистре + цифры)
        self.characters = string.ascii_uppercase + string.digits
        self.max_attempts = 1000  # Максимальное количество попыток генерации уникального ID

    def generate(self, valid_to: date, existing_ids: Set[str] = None) -> str:
        """
        Генерирует уникальный ID сертификата.

        Формат: XXXXX-XXXXX-XXXXX-XXXXX
        Последние 4 символа содержат месяц и год окончания действия (MMYY)

        Args:
            valid_to: Дата окончания действия сертификата
            existing_ids: Множество существующих ID для проверки уникальности

        Returns:
            str: Уникальный ID сертификата

        Raises:
            GenerationError: Если не удалось сгенерировать уникальный ID
        """
        if existing_ids is None:
            existing_ids = set()

        # Формируем окончание ID на основе даты окончания
        month_year_suffix = self._format_month_year(valid_to)

        # Пытаемся сгенерировать уникальный ID
        for attempt in range(self.max_attempts):
            certificate_id = self._generate_id_with_suffix(month_year_suffix)

            # Проверяем уникальность
            if certificate_id not in existing_ids:
                return certificate_id

        raise GenerationError(
            f"Не удалось сгенерировать уникальный ID сертификата за {self.max_attempts} попыток"
        )

    def _format_month_year(self, valid_to: date) -> str:
        """
        Форматирует месяц и год в 4-символьную строку.

        Args:
            valid_to: Дата окончания действия

        Returns:
            str: Строка формата MMYY
        """
        month = f"{valid_to.month:02d}"  # Месяц с ведущим нулем
        year = f"{valid_to.year % 100:02d}"  # Последние 2 цифры года
        return month + year

    def _generate_id_with_suffix(self, suffix: str) -> str:
        """
        Генерирует ID с заданным суффиксом.

        Args:
            suffix: 4-символьный суффикс (MMYY)

        Returns:
            str: ID сертификата формата XXXXX-XXXXX-XXXXX-XXXXX
        """
        # Генерируем первые 3 блока (15 символов)
        first_block = self._generate_block()
        second_block = self._generate_block()
        third_block = self._generate_block()

        # Генерируем первые 2 символа последнего блока
        last_block_prefix = ''.join(random.choices(self.characters, k=2))

        # Формируем последний блок: 2 случайных символа + суффикс
        last_block = last_block_prefix + suffix

        # Собираем полный ID
        return f"{first_block}-{second_block}-{third_block}-{last_block}"

    def _generate_block(self) -> str:
        """
        Генерирует блок из 5 случайных символов.

        Returns:
            str: Блок из 5 символов
        """
        return ''.join(random.choices(self.characters, k=5))

    def extract_expiry_date(self, certificate_id: str) -> tuple[int, int]:
        """
        Извлекает месяц и год окончания из ID сертификата.

        Args:
            certificate_id: ID сертификата

        Returns:
            tuple[int, int]: Кортеж (месяц, год)

        Raises:
            GenerationError: Если ID имеет неверный формат
        """
        if len(certificate_id) != 23 or certificate_id.count('-') != 3:
            raise GenerationError(f"Неверный формат ID сертификата: {certificate_id}")

        # Извлекаем последние 4 символа
        suffix = certificate_id[-4:]

        try:
            month = int(suffix[:2])
            year_short = int(suffix[2:])

            # Конвертируем 2-значный год в 4-значный
            # Предполагаем, что все годы относятся к 21 веку
            current_year = date.today().year
            if year_short <= (current_year % 100):
                year = 2000 + year_short
            else:
                year = 1900 + year_short

            # Проверяем корректность месяца
            if not (1 <= month <= 12):
                raise GenerationError(f"Некорректный месяц в ID сертификата: {month}")

            return month, year

        except ValueError as e:
            raise GenerationError(f"Не удалось извлечь дату из ID сертификата: {e}")

    def validate_id_format(self, certificate_id: str) -> bool:
        """
        Проверяет корректность формата ID сертификата.

        Args:
            certificate_id: ID для проверки

        Returns:
            bool: True если формат корректен, False иначе
        """
        if not certificate_id or len(certificate_id) != 23:
            return False

        # Проверяем формат XXXXX-XXXXX-XXXXX-XXXXX
        parts = certificate_id.split('-')
        if len(parts) != 4:
            return False

        # Каждая часть должна содержать 5 символов
        for part in parts:
            if len(part) != 5:
                return False

            # Все символы должны быть из допустимого набора
            if not all(c in self.characters for c in part):
                return False

        return True

    def generate_examples(self, count: int = 5) -> list[str]:
        """
        Генерирует примеры ID сертификатов для демонстрации.

        Args:
            count: Количество примеров

        Returns:
            list[str]: Список примеров ID
        """
        examples = []
        valid_to = date.today().replace(month=12, day=31)  # Конец текущего года

        for _ in range(count):
            example_id = self.generate(valid_to, set(examples))
            examples.append(example_id)

        return examples


def main():
    """Демонстрация работы генератора."""
    generator = CertificateIDGenerator()

    # Генерируем примеры
    examples = generator.generate_examples(3)
    print("Примеры сгенерированных ID сертификатов:")
    for example in examples:
        print(f"  {example}")

    # Демонстрируем извлечение даты
    for example in examples[:1]:
        try:
            month, year = generator.extract_expiry_date(example)
            print(f"\nИз ID {example} извлечена дата окончания: {month:02d}.{year}")
        except GenerationError as e:
            print(f"Ошибка: {e}")


if __name__ == "__main__":
    main()