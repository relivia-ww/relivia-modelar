# Usa imagem oficial do Playwright que já tem Chromium + deps instalados
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Cache bust: 20260415-v7
ARG CACHEBUST=20260415-v7

WORKDIR /app

# Instala dependências Python + supervisor
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn && \
    apt-get update && apt-get install -y supervisor && \
    rm -rf /var/lib/apt/lists/*

# Copia código
COPY . .

# Cria diretório de runs
RUN mkdir -p /app/runs

EXPOSE 5050

# supervisord roda gunicorn + celery no mesmo container
CMD ["supervisord", "-c", "/app/supervisord.conf"]
