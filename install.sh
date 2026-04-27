#!/usr/bin/env bash
set -euo pipefail

echo "=== Fortunia Installation Script ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

# Returns the raw value of a key in a .env file (strips inline comments/spaces)
env_value() {
    local file="$1" key="$2"
    grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- \
        | sed 's/[[:space:]]*#.*//' \
        | sed 's/^[[:space:]]*//' \
        | sed 's/[[:space:]]*$//'
}

# True if the key is missing or its value is empty
env_empty() {
    local val
    val=$(env_value "$1" "$2")
    [ -z "$val" ]
}

# Set (or replace) a key=value in a .env file, preserving the rest of the file
env_set() {
    local file="$1" key="$2" value="$3"
    if grep -qE "^${key}=" "$file" 2>/dev/null; then
        sed -i '' "s|^${key}=.*|${key}=${value}|" "$file"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Check dependencies
# ─────────────────────────────────────────────────────────────────────────────
echo "Checking dependencies..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: docker not found${NC}"
    echo "Install Docker from https://www.docker.com"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}ERROR: docker compose not found${NC}"
    echo "Make sure you have Docker Compose v2"
    exit 1
fi

echo -e "${GREEN}✓ docker and docker compose found${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 2. Configurar .env principal
# ─────────────────────────────────────────────────────────────────────────────
echo "Configuring .env..."

if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠ .env created from .env.example${NC}"
fi

# Generar DB_PASSWORD solo si falta Y el volumen de postgres no existe aún
# (si el volumen existe, la BD ya fue inicializada con la contraseña anterior)
DB_VOL_EXISTS=$(docker volume ls -q --filter name=fortunia_postgres_data 2>/dev/null | wc -l | tr -d ' ')
if env_empty .env DB_PASSWORD; then
    if [ "$DB_VOL_EXISTS" -gt "0" ]; then
        echo -e "${RED}ERROR: DB_PASSWORD está vacío pero el volumen de Postgres ya existe.${NC}"
        echo "       Recupera la contraseña original o elimina el volumen con:"
        echo "       docker compose down -v   (⚠ borra todos los datos)"
        exit 1
    fi
    DB_PASSWORD=$(openssl rand -hex 24)
    env_set .env DB_PASSWORD "$DB_PASSWORD"
    echo -e "${CYAN}  Generated DB_PASSWORD${NC}"
fi

# Generar INTERNAL_API_KEY si falta
if env_empty .env INTERNAL_API_KEY; then
    INTERNAL_API_KEY=$(openssl rand -hex 32)
    env_set .env INTERNAL_API_KEY "$INTERNAL_API_KEY"
    echo -e "${CYAN}  Generated INTERNAL_API_KEY${NC}"
fi

# Sincronizar FORTUNA_API_KEY con INTERNAL_API_KEY siempre que esté vacía
if env_empty .env FORTUNA_API_KEY; then
    INTERNAL_API_KEY=$(env_value .env INTERNAL_API_KEY)
    env_set .env FORTUNA_API_KEY "$INTERNAL_API_KEY"
    echo -e "${CYAN}  Synced FORTUNA_API_KEY = INTERNAL_API_KEY${NC}"
fi

echo -e "${GREEN}✓ .env ready${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 3. Configurar dashboard/.env (proxy server-side key)
# ─────────────────────────────────────────────────────────────────────────────
echo "Configuring dashboard/.env..."

if [ ! -f dashboard/.env ]; then
    cp dashboard/.env.example dashboard/.env
    echo -e "${YELLOW}⚠ dashboard/.env created${NC}"
fi

# Inyectar FORTUNIA_API_KEY en el dashboard
INTERNAL_API_KEY=$(env_value .env INTERNAL_API_KEY)
env_set dashboard/.env FORTUNIA_API_KEY "$INTERNAL_API_KEY"
env_set dashboard/.env FORTUNIA_API_URL "http://fortunia-api:8000"
echo -e "${GREEN}✓ dashboard/.env ready${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 4. Crear directorios de datos
# ─────────────────────────────────────────────────────────────────────────────
echo "Creating data directories..."
mkdir -p data/{postgres,uploads,backups}
chmod 755 data/{postgres,uploads,backups}
echo -e "${GREEN}✓ data directories ready${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 5. Validar docker-compose.yml
# ─────────────────────────────────────────────────────────────────────────────
echo "Validating docker-compose.yml..."
docker compose config > /dev/null && echo -e "${GREEN}✓ docker-compose.yml is valid${NC}" || {
    echo -e "${RED}ERROR: docker-compose.yml validation failed${NC}"
    exit 1
}
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 6. Build de imágenes locales
# ─────────────────────────────────────────────────────────────────────────────
echo "Pulling external images and building local images..."
docker compose pull --ignore-buildable || true
docker compose build fortunia-api ocr-service dashboard
echo -e "${GREEN}✓ Images ready${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 7. Levantar servicios
# ─────────────────────────────────────────────────────────────────────────────
echo "Starting services..."
docker compose up -d db
echo "Waiting for database to be ready..."
sleep 8

docker compose up -d fortunia-api ocr-service whisper-service dashboard backup-service
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 8. Health checks
# ─────────────────────────────────────────────────────────────────────────────
echo "Verifying service health..."
RETRIES=30
DELAY=2

# PostgreSQL
for i in $(seq 1 $RETRIES); do
    if docker compose exec -T db pg_isready -U fortunia -d fortunia &> /dev/null; then
        echo -e "${GREEN}✓ PostgreSQL healthy${NC}"
        break
    fi
    [ "$i" -eq "$RETRIES" ] && echo -e "${YELLOW}⚠ PostgreSQL did not respond in time${NC}"
    echo "  Waiting for PostgreSQL... ($i/$RETRIES)"
    sleep $DELAY
done

# Fortunia API
for i in $(seq 1 $RETRIES); do
    if curl -sf http://localhost:8000/health &> /dev/null; then
        echo -e "${GREEN}✓ API healthy${NC}"
        break
    fi
    [ "$i" -eq "$RETRIES" ] && echo -e "${YELLOW}⚠ API did not respond in time — check: docker logs fortunia-api${NC}"
    echo "  Waiting for API... ($i/$RETRIES)"
    sleep $DELAY
done

# OCR service
for i in $(seq 1 $RETRIES); do
    if curl -sf http://localhost:8001/health &> /dev/null; then
        echo -e "${GREEN}✓ OCR service healthy${NC}"
        break
    fi
    [ "$i" -eq "$RETRIES" ] && echo -e "${YELLOW}⚠ OCR service did not respond — check: docker logs ocr-service${NC}"
    echo "  Waiting for OCR service... ($i/$RETRIES)"
    sleep $DELAY
done

# ─────────────────────────────────────────────────────────────────────────────
# 9. Resumen final
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Installation Complete ==="
echo ""
echo "Services running:"
docker compose ps
echo ""
echo -e "${CYAN}Credentials (keep these safe):${NC}"
echo "  INTERNAL_API_KEY = $(env_value .env INTERNAL_API_KEY)"
echo ""
echo "Next steps:"
echo "  1. Test API:      curl http://localhost:8000/health"
echo "  2. Swagger docs:  http://localhost:8000/docs"
echo "  3. Dashboard:     http://localhost:3000"
echo "  4. Integrar con Kraken: ver kraken-integration/README.md"
echo ""
echo "To stop:  docker compose down"
echo "To logs:  docker compose logs -f"
