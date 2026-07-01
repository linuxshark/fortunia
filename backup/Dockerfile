# Servicio de backup/restore. Necesita cliente Postgres 16 (>= server) y rsync.
FROM python:3.12-slim-bookworm

# Repo PGDG para postgresql-client-16 (bookworm trae 15, insuficiente para dump de 16)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg rsync \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
         -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV IMAGE_STORE=/app/data/images
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
