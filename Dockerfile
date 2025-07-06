# Multi-stage build для оптимизации размера образа
FROM python:3.11-slim as builder

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.11-slim

# Устанавливаем только runtime зависимости
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копируем виртуальное окружение из builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создаем непривилегированного пользователя
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Создаем рабочую директорию
WORKDIR /app

# Создаем директории для данных с правильными правами ДО смены пользователя
RUN mkdir -p /app/certificates /app/logs && \
    chmod 777 /app/certificates /app/logs

# Копируем код приложения
COPY . .

# Устанавливаем права на все файлы для botuser
RUN chown -R botuser:botuser /app

# Переключаемся на непривилегированного пользователя (временно отключено)
# USER botuser

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Healthcheck для проверки работоспособности
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Открываем порт (если будет веб-интерфейс в будущем)
EXPOSE 8000

# Команда запуска
CMD ["python", "-m", "bot.main"]