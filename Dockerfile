FROM python:3.12-slim

# Instala uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copia arquivos de dependências primeiro (cache de camadas)
COPY pyproject.toml ./

# Instala dependências sem criar venv (usa o Python do sistema no container)
RUN uv sync --no-dev --system

# Copia o restante da aplicação
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
