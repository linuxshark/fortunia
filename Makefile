.DEFAULT_GOAL := help
COMPOSE := docker compose
WORKER_URL := http://localhost:8002
DASHBOARD_URL := http://localhost:8001

# ── bootstrap ─────────────────────────────────────────────────────────────────

.env:
	@cp .env.example .env
	@echo "⚠  .env creado desde .env.example — edita POSTGRES_PASSWORD y GEMINI_API_KEY antes de continuar"

## deploy: build + start all services (postgres first, then worker)
.PHONY: deploy
deploy: .env
	$(COMPOSE) up -d --build
	@$(MAKE) --no-print-directory wait-ready
	@$(MAKE) --no-print-directory fund

## up: start services without rebuilding
.PHONY: up
up: .env
	$(COMPOSE) up -d
	@$(MAKE) --no-print-directory wait-ready
	@$(MAKE) --no-print-directory fund

## build: rebuild worker image only
.PHONY: build
build:
	$(COMPOSE) build worker

## rebuild: full clean rebuild (no cache)
.PHONY: rebuild
rebuild:
	$(COMPOSE) build --no-cache worker
	$(COMPOSE) up -d
	@$(MAKE) --no-print-directory wait-ready

## dashboard: build + (re)start sólo el dashboard web (:8001)
.PHONY: dashboard
dashboard: .env
	$(COMPOSE) up -d --build dashboard
	@$(MAKE) --no-print-directory wait-dashboard

## ro-role: crea/actualiza el rol de solo-lectura en la DB existente (idempotente)
.PHONY: ro-role
ro-role:
	@set -a; . ./.env; set +a; \
	$(COMPOSE) exec -T -e POSTGRES_RO_USER="$$POSTGRES_RO_USER" -e POSTGRES_RO_PASSWORD="$$POSTGRES_RO_PASSWORD" \
		postgres bash /docker-entrypoint-initdb.d/03_ro_role.sh

# ── lifecycle ─────────────────────────────────────────────────────────────────

## stop: stop all services (keep data)
.PHONY: stop
stop:
	$(COMPOSE) stop

## down: stop + remove containers (keep volumes)
.PHONY: down
down:
	$(COMPOSE) down

## destroy: remove containers, volumes, images, networks (FULL WIPE)
.PHONY: destroy
destroy:
	@echo "⚠️  DESTRUCCIÓN COMPLETA:"
	@echo "  • Containers"
	@echo "  • Volúmenes (BD, datos de Postgres)"
	@echo "  • Imágenes Docker (fortunia-worker, fortunia-dashboard)"
	@echo "  • Redes Docker"
	@echo ""
	@read -p "¿Continuar? Escribe 'si' para confirmar: " ans && [ "$$ans" = "si" ]
	@$(COMPOSE) down -v --rmi all
	@echo ""
	@echo "✓ Containers, volúmenes, imágenes y redes eliminados"
	@echo ""
	@read -p "¿Borrar también datos locales (fotos + backups)? [s/N]: " ans && if [ "$$ans" = "s" ]; then \
		rm -rf ./data/images/* ./backups/*; \
		echo "✓ Datos locales eliminados (./data/images y ./backups)"; \
	fi
	@echo ""
	@echo "Listo. Ejecuta 'make deploy' para empezar desde cero."

## restart: restart worker only (without rebuild)
.PHONY: restart
restart:
	$(COMPOSE) restart worker

# ── health & status ───────────────────────────────────────────────────────────

## wait-ready: espera hasta que worker responde /health
.PHONY: wait-ready
wait-ready:
	@echo "Esperando worker..."
	@for i in $$(seq 1 30); do \
		if curl -sf $(WORKER_URL)/health > /dev/null 2>&1; then \
			echo "✓ Worker listo: $$(curl -s $(WORKER_URL)/health)"; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "✗ Worker no respondió en 60s. Ver: make logs-worker" && exit 1

## wait-dashboard: espera hasta que el dashboard responde /health
.PHONY: wait-dashboard
wait-dashboard:
	@echo "Esperando dashboard..."
	@for i in $$(seq 1 30); do \
		if curl -sf $(DASHBOARD_URL)/health > /dev/null 2>&1; then \
			echo "✓ Dashboard listo: $$(curl -s $(DASHBOARD_URL)/health)"; \
			echo "  Abrir: $(DASHBOARD_URL)/"; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "✗ Dashboard no respondió en 60s. Ver: make logs-dashboard" && exit 1

## health: consulta /health del worker
.PHONY: health
health:
	@curl -s $(WORKER_URL)/health | python3 -m json.tool

## health-dashboard: consulta /health del dashboard
.PHONY: health-dashboard
health-dashboard:
	@curl -s $(DASHBOARD_URL)/health | python3 -m json.tool

## status: estado de todos los containers
.PHONY: status
status:
	$(COMPOSE) ps

# ── logs ──────────────────────────────────────────────────────────────────────

## logs: logs de todos los servicios (últimas 50 líneas)
.PHONY: logs
logs:
	$(COMPOSE) logs --tail=50 -f

## logs-worker: logs del worker OCR
.PHONY: logs-worker
logs-worker:
	$(COMPOSE) logs --tail=100 -f worker

## logs-dashboard: logs del dashboard web
.PHONY: logs-dashboard
logs-dashboard:
	$(COMPOSE) logs --tail=100 -f dashboard

## logs-db: logs de postgres
.PHONY: logs-db
logs-db:
	$(COMPOSE) logs --tail=50 -f postgres

# ── test & scan ───────────────────────────────────────────────────────────────

## scan: escanear una boleta  →  make scan FILE=/ruta/boleta.jpg
.PHONY: scan
scan:
	@[ -n "$(FILE)" ] || (echo "Uso: make scan FILE=/ruta/boleta.jpg" && exit 1)
	@curl -s -X POST $(WORKER_URL)/ocr -F "image=@$(FILE)" | python3 -m json.tool

## scan-test: escanea la imagen de prueba del repo (si existe)
.PHONY: scan-test
scan-test:
	@TESTIMG=$$(ls data/images/*.bin 2>/dev/null | head -1); \
	if [ -z "$$TESTIMG" ]; then \
		echo "No hay imagen de prueba en data/images/. Usa: make scan FILE=<foto>"; \
	else \
		echo "Escaneando $$TESTIMG..."; \
		curl -s -X POST $(WORKER_URL)/ocr \
			-F "image=@$$TESTIMG" | python3 -m json.tool; \
	fi

# ── database ──────────────────────────────────────────────────────────────────

## psql: abre consola psql en el container postgres
.PHONY: psql
psql:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas}

## receipts: muestra últimas 20 boletas registradas
.PHONY: receipts
receipts:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} -c \
		"SELECT r.id, r.issued_date, m.name AS merchant, r.total, r.items_count, r.validation_status, r.ocr_engine \
		 FROM receipts r LEFT JOIN merchants m ON m.id = r.merchant_id \
		 ORDER BY r.id DESC LIMIT 20;"

## items: muestra ítems de la última boleta
.PHONY: items
items:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} -c \
		"SELECT li.line_no, li.normalized_name, li.qty, li.unit_price, li.line_total \
		 FROM line_items li \
		 WHERE li.receipt_id = (SELECT MAX(id) FROM receipts) \
		 ORDER BY li.line_no;"

## spend: gasto mensual por categoría
.PHONY: spend
spend:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} -c \
		"SELECT * FROM v_monthly_spend_by_category ORDER BY month DESC, total_spent DESC LIMIT 30;"

## uncategorized: ítems sin categoría (para poblar item_aliases)
.PHONY: uncategorized
uncategorized:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} -c \
		"SELECT * FROM v_uncategorized_items LIMIT 30;"

## backup: fuerza un pg_dump ahora (sin esperar el cron nocturno)
.PHONY: backup
backup:
	@mkdir -p backups
	$(COMPOSE) exec -e PGPASSWORD=$${POSTGRES_PASSWORD} postgres \
		pg_dump -U $${POSTGRES_USER:-boleta} $${POSTGRES_DB:-boletas} \
		| gzip > backups/manual-$$(date +%Y%m%d-%H%M%S).sql.gz
	@echo "Backup guardado en backups/"

## fund: aplica el DDL del fondo (06_fund.sql) a la DB en marcha (idempotente)
.PHONY: fund
fund:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} < db/06_fund.sql
	@$(MAKE) --no-print-directory ro-role
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} \
		-c "GRANT SELECT, INSERT, UPDATE ON fund_monthly TO $${POSTGRES_RO_USER:-fortunia_ro};"
	@echo "✓ Fondo Común aplicado (schema + grant RW acotado)"

## test: unit + DB-integration del worker (requiere `make deploy` para los DB)
.PHONY: test
test:
	cd worker && pytest -v

## e2e: instala Playwright (si falta) y corre los tests E2E del dashboard
.PHONY: e2e
e2e:
	cd e2e && pip install -q -r requirements.txt && python -m playwright install --with-deps chromium
	cd e2e && pytest -v

# ── help ──────────────────────────────────────────────────────────────────────

## help: lista todos los comandos disponibles
.PHONY: help
help:
	@echo "fortunia — boleta scanner"
	@echo ""
	@echo "Uso: make <comando>"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | column -t -s ':'
