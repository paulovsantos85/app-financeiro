# Usa uma imagem leve do Python 3.12 (Linux)
FROM python:3.12-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Variáveis de ambiente para evitar arquivos .pyc e logs em buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Instala dependências do sistema necessárias para o Flet e PostgreSQL
# libpq-dev é necessário para o driver do banco
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para dentro do container
COPY . .

# Expõe a porta que o Flet vai usar (definida no main.py)
EXPOSE 8080

# Comando para iniciar a aplicação
CMD ["python", "main.py"]