#!/usr/bin/env bash
set -euo pipefail

echo "=== Fortunia Installation Script ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check dependencies
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

# Setup .env
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠ .env created. Please edit it and set DB_PASSWORD and INTERNAL_API_KEY${NC}"
    echo ""

    # Generate secrets if not already set
    if grep -q "^DB_PASSWORD=$" .env; then
        DB_PASSWORD=$(openssl rand -hex 24)
        sed -i '' "s/^DB_PASSWORD=$/DB_PASSWORD=$DB_PASSWORD/" .env
        echo "Generated DB_PASSWORD: $DB_PASSWORD"
    fi

    if grep -q "^INTERNAL_API_KEY=$" .env; then
        INTERNAL_API_KEY=$(openssl rand -hex 32)
        sed -i '' "s/^INTERNAL_API_KEY=$/INTERNAL_API_KEY=$INTERNAL_API_KEY/" .env
        echo "Generated INTERNAL_API_KEY: $INTERNAL_API_KEY"
    fi
else
    echo -e "${GREEN}✓ .env exists${NC}"
fi

# Update FORTUNA_API_KEY in .env
if grep -q "^FORTUNA_API_KEY=$" .env; then
    INTERNAL_API_KEY=$(grep "^INTERNAL_API_KEY=" .env | cut -d= -f2)
    sed -i '' "s/^FORTUNA_API_KEY=$/FORTUNA_API_KEY=$INTERNAL_API_KEY/" .env
fi

echo ""

# Create data directories
echo "Creating data directories..."
mkdir -p data/{postgres,uploads,backups}
chmod 755 data/{postgres,uploads,backups}
echo -e "${GREEN}✓ data directories ready${NC}"
echo ""

# Validate docker-compose.yml
echo "Validating docker-compose.yml..."
docker compose config > /dev/null && echo -e "${GREEN}✓ docker-compose.yml is valid${NC}" || {
    echo -e "${RED}ERROR: docker-compose.yml validation failed${NC}"
    exit 1
}
echo ""

# Pull and build images
echo "Pulling external images and building local images..."
docker compose pull || true
docker compose build --no-cache fortunia-api ocr-service dashboard
echo -e "${GREEN}✓ Images ready${NC}"
echo ""

# Start services
echo "Starting services..."
docker compose up -d db
echo "Waiting for database to be ready..."
sleep 10

docker compose up -d fortunia-api ocr-service whisper-service dashboard backup-service
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Health checks
echo "Verifying service health..."
RETRIES=30
DELAY=2

# Check DB
for i in $(seq 1 $RETRIES); do
    if docker compose exec -T db pg_isready -U fortunia -d fortunia &> /dev/null; then
        echo -e "${GREEN}✓ PostgreSQL healthy${NC}"
        break
    fi
    echo "Waiting for PostgreSQL... ($i/$RETRIES)"
    sleep $DELAY
done

# Check API
for i in $(seq 1 $RETRIES); do
    if curl -s http://localhost:8000/health &> /dev/null; then
        echo -e "${GREEN}✓ API healthy${NC}"
        break
    fi
    echo "Waiting for API... ($i/$RETRIES)"
    sleep $DELAY
done

# Check OCR
for i in $(seq 1 $RETRIES); do
    if curl -s http://localhost:8001/docs &> /dev/null; then
        echo -e "${GREEN}✓ OCR service healthy${NC}"
        break
    fi
    echo "Waiting for OCR service... ($i/$RETRIES)"
    sleep $DELAY
done

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Services running:"
docker compose ps
echo ""
echo "Next steps:"
echo "1. Verify .env is correctly configured"
echo "2. Test API: curl http://localhost:8000/health"
echo "3. View OpenAPI docs: http://localhost:8000/docs"
echo "4. Dashboard: http://localhost:3000"
echo ""
echo "To stop services: docker compose down"
echo "To view logs: docker compose logs -f"
