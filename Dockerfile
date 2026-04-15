# Usa imagem oficial do Playwright que já tem Chromium + deps instalados
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Cache bust: 20260415-v6
ARG CACHEBUST=20260415-v6

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copia código
COPY . .

# Cria diretório de runs e torna entrypoint executável
RUN mkdir -p /app/runs && chmod +x /app/entrypoint.sh

EXPOSE 5050

# entrypoint.sh decide: SERVICE_TYPE=worker → Celery, senão → gunicorn
ENTRYPOINT ["/app/entrypoint.sh"]
