# Fortunia Backup & Restore Guide

## Backup Strategy

### Automated Backups

Fortunia includes `backup-service` that runs scheduled backups:

**Schedule**: Daily at 2 AM (America/Santiago)
**Retention**: 7 backups (rolling window)
**Location**: `./backups/` directory (mounted volume)

```bash
# View automated backups
ls -lh backups/

# Example output:
# fortunia_db_backup_2026-04-26_020000.sql.gz  (500MB)
# fortunia_db_backup_2026-04-25_020000.sql.gz  (502MB)
```

### Manual Backups

#### Option 1: Using Docker (Recommended)

```bash
# Create backup
docker-compose exec db pg_dump -U postgres fortunia > backups/manual_backup_$(date +%Y%m%d_%H%M%S).sql

# Create compressed backup
docker-compose exec db pg_dump -U postgres fortunia | gzip > backups/manual_backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Verify backup size
ls -lh backups/manual_backup_*.sql.gz
```

#### Option 2: Direct PostgreSQL Connection

```bash
# If PostgreSQL is installed locally
pg_dump -h localhost -U postgres -d fortunia -Fc > backups/fortunia_$(date +%Y%m%d_%H%M%S).dump

# Custom format (smaller, supports parallel restore)
pg_dump -h localhost -U postgres -d fortunia -Fc -f backups/fortunia.dump
```

#### Option 3: Full Volume Backup

```bash
# Backup entire database volume (includes all data, indexes, WAL)
docker run --rm \
  -v fortunia_db_data:/db_volume \
  -v $(pwd)/backups:/backup_dest \
  busybox \
  tar czf /backup_dest/fortunia_volume_$(date +%Y%m%d_%H%M%S).tar.gz -C /db_volume .
```

## Restore Procedures

### Scenario 1: Restore from SQL Backup

**Use when**: Recent backup, specific data recovery needed

```bash
# 1. Stop API (prevents writes during restore)
docker-compose stop api

# 2. Drop current database
docker-compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS fortunia;"

# 3. Create fresh database
docker-compose exec db psql -U postgres -c "CREATE DATABASE fortunia;"

# 4. Restore from backup
# Uncompressed:
docker-compose exec -T db psql -U postgres fortunia < backups/manual_backup_YYYYMMDD_HHMMSS.sql

# Compressed (requires gzip inside container):
docker-compose exec -T db bash -c "gunzip -c /dev/stdin | psql -U postgres fortunia" < backups/manual_backup_YYYYMMDD_HHMMSS.sql.gz

# 5. Verify restore
docker-compose exec db psql -U postgres -d fortunia -c "SELECT COUNT(*) FROM expenses;"

# 6. Restart API
docker-compose up api -d
```

### Scenario 2: Restore from Custom Format Dump

**Use when**: Custom format (more efficient, supports parallel restore)

```bash
# 1. Stop API
docker-compose stop api

# 2. Drop current database
docker-compose exec db dropdb -U postgres fortunia

# 3. Create fresh database
docker-compose exec db createdb -U postgres fortunia

# 4. Restore with parallel jobs (faster)
docker-compose exec -T db pg_restore -U postgres -d fortunia -j 4 --verbose /dev/stdin < backups/fortunia.dump

# 5. Verify
docker-compose exec db psql -U postgres -d fortunia -c "SELECT COUNT(*) AS expense_count FROM expenses;"

# 6. Restart
docker-compose up api -d
```

### Scenario 3: Point-in-Time Recovery

**Use when**: Need to recover to specific timestamp (corrupted data at time T)

```bash
# PostgreSQL must have WAL archiving enabled
# (Requires docker-compose.yml configuration with WAL archive)

# 1. List available backups with timestamps
ls -l backups/ | grep "\.sql" | tail -20

# 2. Find backup BEFORE corruption time
# Example: Corruption discovered at 2026-04-26 15:30:00
# Use backup from 2026-04-26 02:00:00

# 3. Restore to point-in-time
docker-compose exec db psql -U postgres -d fortunia << EOF
SELECT pg_stop_backup();
-- Recovery to 2026-04-26 15:00:00
-- (requires WAL files and pg_basebackup setup)
EOF
```

### Scenario 4: Restore to New Server

**Use when**: Migrating to new host, disaster recovery

```bash
# 1. Copy backup file to new server
scp user@old-server:/path/to/backups/fortunia.sql.gz ./backups/

# 2. Start Fortunia services (fresh install)
docker-compose up db -d
sleep 10  # Wait for DB to initialize

# 3. Restore backup
zcat backups/fortunia.sql.gz | docker-compose exec -T db psql -U postgres fortunia

# 4. Verify data
docker-compose exec db psql -U postgres -d fortunia << EOF
SELECT 
  (SELECT COUNT(*) FROM expenses) AS total_expenses,
  (SELECT COUNT(*) FROM users) AS total_users,
  (SELECT MAX(spent_at) FROM expenses) AS latest_expense;
EOF

# 5. Start remaining services
docker-compose up -d
```

## Backup Verification

### Automated Verification (Recommended)

```bash
# Test restore from most recent backup (without modifying data)
./scripts/verify_backup.sh

# Example script contents:
#!/bin/bash
backup_file=$(ls -t backups/*.sql.gz | head -1)
echo "Testing restore from: $backup_file"

# Create temporary database
docker-compose exec db createdb -U postgres fortunia_test

# Restore to temp database
zcat "$backup_file" | docker-compose exec -T db psql -U postgres fortunia_test

# Verify data exists
count=$(docker-compose exec db psql -U postgres -d fortunia_test -tc "SELECT COUNT(*) FROM expenses;")
echo "Restored expenses: $count"

# Clean up
docker-compose exec db dropdb -U postgres fortunia_test
echo "✓ Backup verified"
```

### Manual Verification

```bash
# List all tables in backup (without restoring)
zcat backups/fortunia.sql.gz | grep "^CREATE TABLE" | wc -l
# Should show: 6 tables (categories, merchants, expenses, raw_messages, attachments, intent_feedback)

# Check backup file integrity
gunzip -t backups/fortunia.sql.gz && echo "✓ Backup is valid"

# Estimate restore time
gunzip -c backups/fortunia.sql.gz | wc -l  # Number of SQL statements

# Check backup size over time (verify compression working)
ls -lh backups/ | tail -10 | awk '{print $9, $5}'
```

## Backup Monitoring

### Check Backup Health

```bash
# View backup logs (if using backup-service)
docker logs fortunia_backup_service

# Monitor backup frequency
find backups -name "*.sql.gz" -mtime -1 -type f  # Backups from last 24h

# Alert on missing backups (cron job)
#!/bin/bash
latest=$(find backups -name "fortunia_db_backup*.sql.gz" -mtime -2 | wc -l)
if [ $latest -eq 0 ]; then
  echo "⚠️  No backup in last 2 days" | mail -s "Backup Alert" admin@example.com
fi
```

### Backup Metrics

```bash
# Backup size trend
find backups -name "*.sql.gz" -exec ls -lh {} \; | awk '{print $6, $9}'

# Database growth rate
# If backups growing >10% weekly, consider:
# 1. Data retention policy (delete old expenses)
# 2. Compression optimization
# 3. Archive older data to cold storage

# Backup age monitoring
find backups -name "*.sql.gz" -type f -printf '%T+ %p\n' | sort -r | head -5
```

## Data Retention & Cleanup

### Automated Data Cleanup

```sql
-- Delete expenses older than 2 years (optional)
DELETE FROM expenses 
WHERE spent_at < NOW() - INTERVAL '2 years'
  AND category = 'other';  -- Only clean up uncertain expenses

-- Archive old raw_messages (keep audit trail but compress)
DELETE FROM raw_messages 
WHERE created_at < NOW() - INTERVAL '1 year';

-- Run VACUUM to reclaim space
VACUUM ANALYZE;
```

### Backup Rotation

```bash
# Keep only last N backups (automatic cleanup)
#!/bin/bash
max_backups=7
backup_dir="backups"

count=$(find "$backup_dir" -name "fortunia_db_backup*.sql.gz" | wc -l)
if [ $count -gt $max_backups ]; then
  excess=$((count - max_backups))
  find "$backup_dir" -name "fortunia_db_backup*.sql.gz" -type f -printf '%T+ %p\n' \
    | sort | head -n $excess | cut -d' ' -f2- | xargs rm
  echo "Cleaned up $excess old backups"
fi
```

## Disaster Recovery Plan

### RTO/RPO Targets

**Recovery Time Objective (RTO)**: 15 minutes
**Recovery Point Objective (RPO)**: 6 hours (acceptable data loss)

### Recovery Steps

```bash
# If database is corrupted:
1. Stop API immediately
2. Restore from most recent backup (5 min)
3. Verify data integrity (5 min)
4. Restart all services (2 min)
5. Monitor for issues (3 min)

# If entire server is lost:
1. Provision new server
2. Install Docker/Docker Compose
3. Copy backup files
4. Restore database (10 min)
5. Update DNS/load balancer
6. Verify functionality
```

### Testing Recovery Regularly

```bash
# Schedule monthly recovery drill
# 1. Pick random backup from 30 days ago
# 2. Restore to staging environment
# 3. Verify all data and APIs functional
# 4. Document any issues
# 5. Update recovery procedures

# Monthly test script
#!/bin/bash
date=$(date -d "30 days ago" +%Y%m%d)
backup="backups/fortunia_db_backup_${date}*.sql.gz"
if [ -f "$backup" ]; then
  echo "Testing recovery of backup from $date"
  # Perform restore to staging
else
  echo "⚠️  No backup found for 30 days ago"
fi
```

## Off-Site Backup Strategy

### Cloud Backup (AWS S3, GCP Cloud Storage, etc.)

```bash
# Upload backups to S3 daily
#!/bin/bash
aws s3 sync backups/ s3://fortunia-backups/ \
  --exclude "*" \
  --include "fortunia_db_backup_*.sql.gz" \
  --storage-class GLACIER  # Long-term archival

# Restore from S3
aws s3 cp s3://fortunia-backups/fortunia_db_backup_YYYYMMDD.sql.gz ./backups/
zcat backups/fortunia_db_backup_YYYYMMDD.sql.gz | docker-compose exec -T db psql -U postgres fortunia
```

### Backup Encryption

```bash
# Encrypt backup before uploading
gpg --symmetric backups/fortunia.sql.gz  # Creates fortunia.sql.gz.gpg

# Restore encrypted backup
gpg --decrypt backups/fortunia.sql.gz.gpg | zcat | docker-compose exec -T db psql -U postgres fortunia
```

## Emergency Contacts & Documentation

- **Backup Location**: `./backups/` on docker host
- **Database Credentials**: `.env` file
- **Backup Schedule**: Daily 2 AM (America/Santiago TZ)
- **Contact for Restore**: DevOps team / Database admin
- **Last Tested**: [Date of last recovery drill]
