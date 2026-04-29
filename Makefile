.PHONY: help install start stop restart logs status \
        build build-dashboard build-api \
        reset reset-db reset-uploads reset-backups restart-scratch \
        backup shell-db add-user \
        _start-fresh _confirm-reset _confirm-reset-db

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
COMPOSE  := docker compose
DB_USER  := fortunia
DB_NAME  := fortunia

# ──────────────────────────────────────────────────────────────────────────────
# Default
# ──────────────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Fortunia — comandos disponibles"
	@echo ""
	@echo "  Servicios"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make install          Instala y levanta todo (primera vez)"
	@echo "  make start            Levanta los servicios"
	@echo "  make stop             Detiene los servicios"
	@echo "  make restart          Reinicia los servicios"
	@echo "  make logs             Muestra logs en tiempo real"
	@echo "  make status           Estado de los contenedores"
	@echo ""
	@echo "  Build (tras cambios de código)"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make build            Reconstruye todas las imágenes"
	@echo "  make build-dashboard  Reconstruye solo el dashboard"
	@echo "  make build-api        Reconstruye solo la API"
	@echo ""
	@echo "  Base de datos"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make backup         Crea un backup manual ahora"
	@echo "  make shell-db       Abre psql interactivo"
	@echo "  make add-user TELEGRAM_ID=123 NAME=\"Nombre\" KEY=123"
	@echo "                      Registra un usuario en el filtro del dashboard"
	@echo ""
	@echo "  Reset  ⚠️  IRREVERSIBLE"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make reset            Borra TODO (db + uploads + backups) y reinicia"
	@echo "  make restart-scratch  Igual que reset pero sin confirmación interactiva"
	@echo "  make reset-db         Borra solo la base de datos y reinicia"
	@echo "  make reset-uploads    Borra solo los archivos subidos"
	@echo "  make reset-backups    Borra solo los backups automáticos"
	@echo ""

# ──────────────────────────────────────────────────────────────────────────────
# Servicios
# ──────────────────────────────────────────────────────────────────────────────
install:
	@bash install.sh

build:
	$(COMPOSE) build fortunia-api ocr-service dashboard
	$(COMPOSE) up -d

build-dashboard:
	$(COMPOSE) build dashboard
	$(COMPOSE) up -d dashboard

build-api:
	$(COMPOSE) build fortunia-api
	$(COMPOSE) up -d fortunia-api

start:
	$(COMPOSE) up -d

stop:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f

status:
	$(COMPOSE) ps

# ──────────────────────────────────────────────────────────────────────────────
# Base de datos
# ──────────────────────────────────────────────────────────────────────────────
backup:
	@mkdir -p data/backups
	@file="data/backups/manual_$$(date +%Y%m%d_%H%M%S).sql.gz"; \
	 $(COMPOSE) exec db pg_dump -U $(DB_USER) $(DB_NAME) | gzip > "$$file"; \
	 echo "✓ Backup guardado en $$file"

shell-db:
	$(COMPOSE) exec db psql -U $(DB_USER) -d $(DB_NAME)

# Registrar un usuario  →  make add-user TELEGRAM_ID=757348065 NAME="Raúl Linares" KEY=757348065
add-user:
	@[ -n "$(TELEGRAM_ID)" ] || { echo "Uso: make add-user TELEGRAM_ID=<id> NAME=\"<nombre>\" KEY=<user_key>"; exit 1; }
	@$(COMPOSE) exec db psql -U $(DB_USER) -d $(DB_NAME) -c \
	  "INSERT INTO users (telegram_id, display_name, user_key) \
	   VALUES ($(TELEGRAM_ID), '$(NAME)', '$(KEY)') \
	   ON CONFLICT (telegram_id) DO UPDATE SET display_name = EXCLUDED.display_name, user_key = EXCLUDED.user_key, is_active = true;" && \
	 echo "✓ Usuario '$(NAME)' registrado (telegram_id=$(TELEGRAM_ID))"

# ──────────────────────────────────────────────────────────────────────────────
# Reset  ⚠️  IRREVERSIBLE
# ──────────────────────────────────────────────────────────────────────────────
reset: _confirm-reset
	@echo "→ Deteniendo servicios y eliminando volumen de BD..."
	@$(COMPOSE) down -v
	@echo "→ Eliminando archivos subidos..."
	@rm -rf data/uploads/*
	@echo "→ Eliminando backups..."
	@rm -rf data/backups/daily/* data/backups/weekly/* \
	         data/backups/monthly/* data/backups/last/* \
	         data/backups/manual_*.sql.gz 2>/dev/null; true
	@echo "→ Recreando directorios..."
	@mkdir -p data/{uploads,backups}
	@$(MAKE) -s _start-fresh
	@echo ""
	@echo "✓ Fortunia reiniciado desde cero."
	@echo ""
	@echo "  ⚠️  Recuerda volver a registrar los usuarios:"
	@echo "  make add-user TELEGRAM_ID=757348065 NAME=\"Raúl Linares\" KEY=757348065"

reset-db: _confirm-reset-db
	@echo "→ Deteniendo servicios y eliminando volumen de BD..."
	@$(COMPOSE) down -v
	@$(MAKE) -s _start-fresh
	@echo ""
	@echo "✓ Base de datos reiniciada. Uploads y backups intactos."
	@echo ""
	@echo "  ⚠️  Recuerda volver a registrar los usuarios:"
	@echo "  make add-user TELEGRAM_ID=757348065 NAME=\"Raúl Linares\" KEY=757348065"

restart-scratch:
	@echo "⚠️  Eliminando todos los datos y reiniciando Fortunia desde cero..."
	@$(COMPOSE) down -v
	@rm -rf data/uploads/*
	@rm -rf data/backups/daily/* data/backups/weekly/* \
	         data/backups/monthly/* data/backups/last/* \
	         data/backups/manual_*.sql.gz 2>/dev/null; true
	@mkdir -p data/{uploads,backups}
	@$(MAKE) -s _start-fresh
	@echo ""
	@echo "✓ Fortunia reiniciado desde cero."
	@echo ""
	@echo "  ⚠️  Recuerda volver a registrar los usuarios:"
	@echo "  make add-user TELEGRAM_ID=757348065 NAME=\"Raúl Linares\" KEY=757348065"

reset-uploads:
	@read -p "⚠️  Eliminar todos los archivos subidos? [s/N] " ans; \
	 [ "$$ans" = "s" ] || { echo "Cancelado."; exit 1; }
	@rm -rf data/uploads/*
	@echo "✓ Uploads eliminados."

reset-backups:
	@read -p "⚠️  Eliminar todos los backups? [s/N] " ans; \
	 [ "$$ans" = "s" ] || { echo "Cancelado."; exit 1; }
	@rm -rf data/backups/daily/* data/backups/weekly/* \
	         data/backups/monthly/* data/backups/last/* \
	         data/backups/manual_*.sql.gz 2>/dev/null; true
	@echo "✓ Backups eliminados."

# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

# Levanta db primero, espera a que esté healthy, luego el resto
_start-fresh:
	@echo "→ Iniciando base de datos..."
	@$(COMPOSE) up -d db
	@echo "→ Esperando a que Postgres inicialice y ejecute init.sql..."
	@retries=60; \
	 until $(COMPOSE) exec -T db pg_isready -U $(DB_USER) -d $(DB_NAME) -h 127.0.0.1 > /dev/null 2>&1; do \
	   retries=$$((retries - 1)); \
	   [ $$retries -eq 0 ] && { echo "✗ Postgres no respondió a tiempo."; exit 1; }; \
	   printf "."; sleep 2; \
	 done; echo " listo"
	@echo "→ Levantando resto de servicios..."
	@$(COMPOSE) up -d

_confirm-reset:
	@echo ""
	@echo "  ⚠️  ADVERTENCIA: esto eliminará TODOS los datos de Fortunia."
	@echo "  Base de datos, archivos subidos y backups serán borrados."
	@echo ""
	@read -p "  Escribe 'si' para confirmar: " ans; \
	 [ "$$ans" = "si" ] || { echo "Cancelado."; exit 1; }

_confirm-reset-db:
	@echo ""
	@echo "  ⚠️  ADVERTENCIA: esto eliminará la base de datos completa."
	@echo ""
	@read -p "  Escribe 'si' para confirmar: " ans; \
	 [ "$$ans" = "si" ] || { echo "Cancelado."; exit 1; }
