# Usa imagem oficial do Playwright que já tem Chromium + deps instalados
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Cria diretório de runs
RUN mkdir -p /app/runs

EXPOSE 5050

CMD ["python", "run.py"]
