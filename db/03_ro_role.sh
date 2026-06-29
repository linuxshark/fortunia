#!/bin/bash
# Crea/actualiza el rol de SOLO LECTURA usado por el dashboard (:8001).
# Corre automáticamente en el primer init del cluster (docker-entrypoint-initdb.d)
# y también a mano vía `make ro-role` sobre una DB ya existente.
# Idempotente: crea el rol si falta, si existe sólo refresca la contraseña.
set -euo pipefail

: "${POSTGRES_RO_USER:=fortunia_ro}"
: "${POSTGRES_RO_PASSWORD:=change_me_ro}"
: "${POSTGRES_USER:=boleta}"
: "${POSTGRES_DB:=boletas}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	DO \$\$
	BEGIN
	  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${POSTGRES_RO_USER}') THEN
	    CREATE ROLE ${POSTGRES_RO_USER} LOGIN PASSWORD '${POSTGRES_RO_PASSWORD}';
	  ELSE
	    ALTER ROLE ${POSTGRES_RO_USER} WITH LOGIN PASSWORD '${POSTGRES_RO_PASSWORD}';
	  END IF;
	END
	\$\$;

	GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_RO_USER};
	GRANT USAGE  ON SCHEMA public          TO ${POSTGRES_RO_USER};
	GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${POSTGRES_RO_USER};
	-- tablas/vistas futuras quedan SELECT-only automáticamente
	ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ${POSTGRES_RO_USER};
EOSQL

echo "✓ Rol ${POSTGRES_RO_USER} listo (SELECT-only sobre $POSTGRES_DB)"
