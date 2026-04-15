# Usa imagem oficial do Playwright que já tem Chromium + deps instalados
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copia código
COPY . .

# Cria diretório de runs
RUN mkdir -p /app/runs

EXPOSE 5050

# gunicorn garante host 0.0.0.0 independente do run.py
CMD gunicorn "app:create_app()" --bind 0.0.0.0:${PORT:-5050} --workers 2 --timeout 120
