#!/usr/bin/env python3
"""
Точка входа для запуска Telegram бота управления сертификатами.
"""

import sys
import logging
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

from bot.main import run_bot
from config.settings import get_settings, validate_settings, create_env_example


def main():
    """Основная функция запуска."""
    print("🚀 Запуск системы управления сертификатами")
    print("=" * 50)

    # Проверяем наличие файла конфигурации
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ Файл .env не найден!")
        print("📝 Создаю пример конфигурации...")
        create_env_example()
        print("✅ Создан файл .env.example")
        print("\n📋 Выполните следующие шаги:")
        print("1. Скопируйте .env.example в .env:")
        print("   cp .env.example .env")
        print("2. Отредактируйте .env файл с вашими настройками")
        print("3. Запустите бота снова")
        sys.exit(1)

    # Валидируем настройки
    print("🔧 Проверка конфигурации...")
    if not validate_settings():
        print("❌ Ошибка конфигурации! Проверьте файл .env")
        sys.exit(1)

    settings = get_settings()
    print("✅ Конфигурация корректна")
    print(f"📊 Администраторов: {len(settings.admin_users_set)}")
    print(f"👥 Пользователей для проверки: {len(settings.verify_users_set)}")
    print(f"📁 Директория сертификатов: {settings.certificates_path}")

    # Создаем необходимые директории
    settings.create_directories()

    # Запускаем бота
    print("\n🤖 Запуск Telegram бота...")
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n⛔ Остановка по требованию пользователя")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        logging.exception("Критическая ошибка при запуске бота")
        sys.exit(1)


if __name__ == "__main__":
    main()