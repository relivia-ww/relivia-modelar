FROM python:3.11-slim

WORKDIR /app

# Instala dependências Python primeiro (inclui playwright)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright instala o Chromium e todas as dependências do sistema automaticamente
RUN playwright install chromium --with-deps

# Copia código
COPY . .

# Cria diretório de runs
RUN mkdir -p /app/runs

EXPOSE 5050

CMD ["python", "run.py"]
