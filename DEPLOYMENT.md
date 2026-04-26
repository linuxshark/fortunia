# Fortunia Deployment Guide

## Overview

Fortunia can be deployed to:
1. **Docker Compose** (development/small scale)
2. **Kubernetes** (production/high scale)
3. **Cloud Providers** (AWS ECS, GCP Cloud Run, Azure Container Instances)

## Local Development Deployment

### Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd fortunia
cp .env.example .env
# Edit .env with your values

# 2. Start services
docker-compose up -d

# 3. Verify
curl http://localhost:8000/health
curl http://localhost:3000
```

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/fortunia

# API Security
INTERNAL_API_KEY=<generate: openssl rand -hex 32>

# External Services
OCR_SERVICE_URL=http://ocr-service:8001
WHISPER_SERVICE_URL=http://whisper-service:8002

# Dashboard
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional
DEFAULT_CURRENCY=CLP
DEFAULT_TIMEZONE=America/Santiago
LOG_LEVEL=INFO
```

## Production Deployment

### Pre-Deployment Checklist

- [ ] Database backup strategy configured (see BACKUP_RESTORE.md)
- [ ] API key rotated (not default)
- [ ] HTTPS/TLS certificates obtained
- [ ] Monitoring/alerting configured
- [ ] Load testing completed (target: 100 req/s)
- [ ] Security audit completed
- [ ] Disaster recovery plan tested

### Kubernetes Deployment

#### 1. Build Docker Images

```bash
# Build and tag for registry
docker build -t your-registry/fortunia-api:latest ./api
docker build -t your-registry/fortunia-dashboard:latest ./dashboard
docker build -t your-registry/fortunia-ocr:latest ./ocr-service

# Push to registry
docker push your-registry/fortunia-api:latest
docker push your-registry/fortunia-dashboard:latest
docker push your-registry/fortunia-ocr:latest
```

#### 2. Create Kubernetes Manifests

**api-deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fortunia-api
  namespace: fortunia
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fortunia-api
  template:
    metadata:
      labels:
        app: fortunia-api
    spec:
      containers:
      - name: api
        image: your-registry/fortunia-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: fortunia-secrets
              key: database-url
        - name: INTERNAL_API_KEY
          valueFrom:
            secretKeyRef:
              name: fortunia-secrets
              key: api-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**postgres-statefulset.yaml**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: fortunia-db
  namespace: fortunia
spec:
  serviceName: fortunia-db
  replicas: 1
  selector:
    matchLabels:
      app: fortunia-db
  template:
    metadata:
      labels:
        app: fortunia-db
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: fortunia-secrets
              key: postgres-password
        - name: POSTGRES_DB
          value: "fortunia"
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 50Gi
```

**service.yaml**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: fortunia-api
  namespace: fortunia
spec:
  type: LoadBalancer
  selector:
    app: fortunia-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
```

#### 3. Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace fortunia

# Create secrets
kubectl create secret generic fortunia-secrets \
  --from-literal=database-url="postgresql://postgres:password@fortunia-db:5432/fortunia" \
  --from-literal=api-key="$(openssl rand -hex 32)" \
  --from-literal=postgres-password="$(openssl rand -hex 16)" \
  -n fortunia

# Apply manifests
kubectl apply -f api-deployment.yaml
kubectl apply -f postgres-statefulset.yaml
kubectl apply -f service.yaml

# Verify deployment
kubectl get pods -n fortunia
kubectl logs -f deployment/fortunia-api -n fortunia
```

### AWS ECS Deployment

```bash
# 1. Create ECR repositories
aws ecr create-repository --repository-name fortunia-api
aws ecr create-repository --repository-name fortunia-dashboard

# 2. Push images
$(aws ecr get-login --no-include-email --region us-east-1)
docker tag fortunia-api:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/fortunia-api:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/fortunia-api:latest

# 3. Create RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier fortunia-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --master-username postgres \
  --master-user-password <password> \
  --allocated-storage 100

# 4. Create ECS task definition (task-definition.json):
{
  "family": "fortunia",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "fortunia-api",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/fortunia-api:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://postgres:<password>@<rds-endpoint>:5432/fortunia"
        },
        {
          "name": "INTERNAL_API_KEY",
          "value": "<generated-key>"
        }
      ]
    }
  ]
}

# 5. Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 6. Create ECS service
aws ecs create-service \
  --cluster fortunia \
  --service-name fortunia-api \
  --task-definition fortunia \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

## Performance Tuning

### Database Optimization

```sql
-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Index analysis
ANALYZE;
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM expenses 
WHERE user_id = 'user_123' 
  AND spent_at > NOW() - INTERVAL '30 days';

-- Connection pooling (PgBouncer)
-- config: /etc/pgbouncer/pgbouncer.ini
[databases]
fortunia = host=db port=5432 user=postgres dbname=fortunia

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

### API Optimization

```python
# api/app/main.py
app = FastAPI()

# Add caching middleware
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
)

# Response compression
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Dashboard Optimization

```bash
# Build optimized bundle
cd dashboard
npm run build
# Creates .next/static/chunks optimized for production

# Enable CDN caching (next.config.js)
const nextConfig = {
  images: {
    unoptimized: true,  // Use CDN for images
  },
  compress: true,
};
```

## Monitoring & Alerts

### Prometheus Metrics

```python
# Track in API
from prometheus_client import Counter, Histogram

ingest_requests = Counter(
    'ingest_requests_total',
    'Total ingest requests',
    ['method', 'status']
)

parse_duration = Histogram(
    'parse_duration_seconds',
    'Parsing duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)
```

### Key Metrics to Monitor

| Metric | Target | Alert |
|--------|--------|-------|
| API response time (p95) | <500ms | >1000ms |
| Intent detection accuracy | >95% | <90% |
| Ingest success rate | >99% | <98% |
| Database query time (p95) | <100ms | >500ms |
| Error rate | <0.1% | >0.5% |
| OCR service availability | 99.9% | <99% |

### Health Checks

```bash
# Kubernetes livenessProbe
GET /health
Response: {"status": "ok", "timestamp": "2026-04-26T..."}

# Readiness (before accepting traffic)
GET /health/ready
Response: {
  "status": "ready",
  "database": "ok",
  "services": {"ocr": "ok", "whisper": "ok"}
}
```

## Security Best Practices

### API Security

```python
# 1. Rate limiting
app.add_middleware(
    SlowAPIMiddleware,
    limiter=limiter
)

# 2. CORS (production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.fortunia.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["X-Internal-Key"],
)

# 3. HTTPS only
# Redirect HTTP → HTTPS in load balancer

# 4. API key rotation
# Change INTERNAL_API_KEY every 90 days
```

### Database Security

```bash
# 1. Backup encryption (see BACKUP_RESTORE.md)
# 2. Database user permissions (least privilege)
psql -U postgres -c "CREATE USER app_user WITH PASSWORD 'secure_password';"
psql -U postgres -c "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;"
psql -U postgres -c "ALTER DEFAULT PRIVILEGES GRANT SELECT, INSERT, UPDATE ON TABLES TO app_user;"

# 3. Audit logging
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
CREATE POLICY expense_isolation ON expenses USING (user_id = current_user_id);

# 4. SSL connections (Kubernetes secrets)
# Store cert in: Secret/fortunia-tls
```

### Network Security

```yaml
# Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: fortunia-policy
spec:
  podSelector:
    matchLabels:
      app: fortunia-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx-ingress
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: fortunia-db
    ports:
    - protocol: TCP
      port: 5432
```

## Rollback Procedures

### Zero-Downtime Deployment

```bash
# 1. Deploy new version alongside old
kubectl set image deployment/fortunia-api \
  fortunia-api=your-registry/fortunia-api:v2.0.0 \
  --record -n fortunia

# 2. Monitor metrics (wait for new pods to be healthy)
kubectl rollout status deployment/fortunia-api -n fortunia

# 3. If issues: rollback
kubectl rollout undo deployment/fortunia-api -n fortunia

# 4. Check rollback status
kubectl rollout history deployment/fortunia-api -n fortunia
```

### Database Migration Rollback

```sql
-- Tag current schema version
INSERT INTO schema_versions VALUES ('v1.0.0', NOW());

-- Run migrations (using Alembic)
alembic upgrade head

-- If migration fails, rollback
alembic downgrade -1
```

## Cost Optimization

### Resource Sizing

| Service | vCPU | Memory | Storage |
|---------|------|--------|---------|
| API (3x) | 0.5 | 256Mi | — |
| Database | 2 | 2Gi | 50Gi |
| OCR Service | 2 | 4Gi | — |
| Dashboard | 0.25 | 256Mi | — |

### Cost Reduction

- Use spot instances for non-critical services (OCR, Dashboard)
- Archive old expenses to S3 Glacier (older than 2 years)
- Use auto-scaling (scale down during off-hours)
- Consolidate services on single node if <100k expenses/month

## Support & Runbooks

- **Runbook**: See TROUBLESHOOTING.md
- **Backup**: See BACKUP_RESTORE.md
- **Architecture**: See ARCHITECTURE.md
- **On-call**: Page DevOps for P1 incidents
