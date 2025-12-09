# Dockerfile minimal para FastAPI app (WOT Clan Dashboard)
FROM python:3.11-slim

# cria diretório de trabalho
WORKDIR /app

# instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# copia requirements e instala
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copia a aplicação
COPY . /app

ENV PYTHONUNBUFFERED=1

# expõe porta do uvicorn
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]