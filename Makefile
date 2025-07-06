# Makefile for Certificate Management Bot

.PHONY: help install setup run test clean docker-build docker-up docker-down backup

# Variables
PYTHON = python3
PIP = pip3
DOCKER_COMPOSE = docker-compose
PROJECT_NAME = certificate_bot

# Default target
help:
	@echo "Certificate Management Bot - Available commands:"
	@echo "  setup          - Initial project setup"
	@echo "  install        - Install Python dependencies"
	@echo "  run            - Run the bot locally"
	@echo "  test           - Run tests"
	@echo "  test-coverage  - Run tests with coverage"
	@echo "  lint           - Run code linting"
	@echo "  format         - Format code with black"
	@echo "  clean          - Clean temporary files"
	@echo ""
	@echo "Docker commands:"
	@echo "  docker-build   - Build Docker images"
	@echo "  docker-up      - Start services with Docker"
	@echo "  docker-down    - Stop Docker services"
	@echo "  docker-logs    - Show Docker logs"
	@echo "  docker-shell   - Open shell in bot container"
	@echo ""
	@echo "Database commands:"
	@echo "  db-migrate     - Run database migrations"
	@echo "  db-upgrade     - Upgrade database to latest version"
	@echo "  db-reset       - Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Maintenance commands:"
	@echo "  backup         - Create database backup"
	@echo "  status         - Show system status"

# Setup and installation
setup: install create-dirs create-env
	@echo "✅ Project setup completed!"

install:
	@echo "📦 Installing Python dependencies..."
	$(PIP) install -r requirements.txt

create-dirs:
	@echo "📁 Creating necessary directories..."
	mkdir -p data/{postgres,certificates,logs,backups}
	mkdir -p logs

create-env:
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env file from template..."; \
		cp .env.example .env; \
		echo "⚠️  Edit .env file with your configuration"; \
	else \
		echo "✅ .env file already exists"; \
	fi

# Running and testing
run:
	@echo "🚀 Starting Certificate Bot..."
	$(PYTHON) run.py

test:
	@echo "🧪 Running tests..."
	$(PYTHON) -m pytest tests/ -v

test-coverage:
	@echo "🧪 Running tests with coverage..."
	$(PYTHON) -m pytest tests/ --cov=core --cov=bot --cov-report=html --cov-report=term

lint:
	@echo "🔍 Running code linting..."
	flake8 core/ bot/ --max-line-length=100 --exclude=__pycache__,migrations
	mypy core/ bot/ --ignore-missing-imports

format:
	@echo "🎨 Formatting code..."
	black core/ bot/ tests/ --line-length=100
	isort core/ bot/ tests/

# Docker commands
docker-build:
	@echo "🐳 Building Docker images..."
	$(DOCKER_COMPOSE) build

docker-up:
	@echo "🐳 Starting Docker services..."
	$(DOCKER_COMPOSE) up -d
	@echo "✅ Services started. Use 'make docker-logs' to view logs"

docker-up-build:
	@echo "🐳 Building and starting Docker services..."
	$(DOCKER_COMPOSE) up -d --build

docker-down:
	@echo "🐳 Stopping Docker services..."
	$(DOCKER_COMPOSE) down

docker-logs:
	@echo "📋 Showing Docker logs..."
	$(DOCKER_COMPOSE) logs -f certificate_bot

docker-shell:
	@echo "🐚 Opening shell in bot container..."
	$(DOCKER_COMPOSE) exec certificate_bot /bin/bash

docker-clean:
	@echo "🧹 Cleaning Docker containers and images..."
	$(DOCKER_COMPOSE) down -v --rmi local
	docker system prune -f

# Database commands
db-migrate:
	@echo "🗄️ Creating new database migration..."
	alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	@echo "🗄️ Upgrading database..."
	alembic upgrade head

db-reset:
	@echo "⚠️  Resetting database (this will delete all data)..."
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) exec postgres psql -U certificates_user -d certificates_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"; \
		alembic upgrade head; \
		echo "✅ Database reset completed"; \
	else \
		echo "❌ Operation cancelled"; \
	fi

db-shell:
	@echo "🗄️ Opening database shell..."
	$(DOCKER_COMPOSE) exec postgres psql -U certificates_user -d certificates_db

# Maintenance
backup:
	@echo "💾 Creating database backup..."
	$(DOCKER_COMPOSE) --profile backup run --rm backup

status:
	@echo "📊 System Status:"
	@echo "=================="
	@echo "Docker Services:"
	$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Database Connection:"
	@$(DOCKER_COMPOSE) exec postgres pg_isready -U certificates_user -d certificates_db && echo "✅ Database OK" || echo "❌ Database Error"
	@echo ""
	@echo "Bot Status:"
	@$(DOCKER_COMPOSE) exec certificate_bot python -c "import requests; print('✅ Bot OK' if requests.get('https://api.telegram.org/bot${BOT_TOKEN}/getMe').status_code == 200 else '❌ Bot Error')" 2>/dev/null || echo "❌ Bot Not Running"

# Development helpers
dev-setup: setup
	@echo "🔧 Setting up development environment..."
	$(PIP) install pytest pytest-cov black flake8 isort mypy
	@echo "✅ Development environment ready!"

dev-run:
	@echo "🔧 Running in development mode..."
	DEBUG=true $(PYTHON) run.py

# Cleaning
clean:
	@echo "🧹 Cleaning temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
	@echo "✅ Cleanup completed"

# Production deployment
prod-deploy:
	@echo "🚀 Deploying to production..."
	@echo "⚠️  Make sure you have configured production .env file!"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d --build
	@echo "✅ Production deployment completed"

prod-logs:
	@echo "📋 Production logs..."
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Health checks
health-check:
	@echo "🏥 Running health checks..."
	@echo "1. Database connection:"
	@$(DOCKER_COMPOSE) exec postgres pg_isready && echo "✅ Database OK" || echo "❌ Database Failed"
	@echo "2. Bot API connection:"
	@$(DOCKER_COMPOSE) exec certificate_bot python -c "import requests; requests.get('https://api.telegram.org/bot${BOT_TOKEN}/getMe').raise_for_status(); print('✅ Bot API OK')" || echo "❌ Bot API Failed"
	@echo "3. File system permissions:"
	@$(DOCKER_COMPOSE) exec certificate_bot test -w /app/certificates && echo "✅ File permissions OK" || echo "❌ File permissions Failed"

# Monitoring
monitor:
	@echo "📊 Starting monitoring dashboard..."
	$(DOCKER_COMPOSE) --profile admin up -d adminer
	@echo "🌐 Adminer available at http://localhost:8080"
	@echo "📋 Logs:"
	$(DOCKER_COMPOSE) logs -f certificate_bot

# Quick commands for daily use
start: docker-up
stop: docker-down
restart: docker-down docker-up
logs: docker-logs

# Installation verification
verify:
	@echo "🔍 Verifying installation..."
	@$(PYTHON) --version
	@$(PIP) --version
	@$(DOCKER_COMPOSE) --version
	@test -f .env && echo "✅ .env file exists" || echo "❌ .env file missing"
	@test -d data && echo "✅ data directory exists" || echo "❌ data directory missing"
	@echo "✅ Verification completed"