# Usa imagem oficial do Playwright que já tem Chromium + deps instalados
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Cache bust: 20260415-v5
ARG CACHEBUST=20260415-v5

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copia código
COPY . .

# Cria diretório de runs
RUN mkdir -p /app/runs

EXPOSE 5050

# IMPORTANTE: gunicorn garante 0.0.0.0 — NÃO usar python run.py (escuta 127.0.0.1)
CMD ["sh", "-c", "gunicorn 'app:create_app()' --bind 0.0.0.0:${PORT:-5050} --workers 2 --timeout 120"]
