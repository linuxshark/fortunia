 META: Levantar y verificar el worker de OCR de boletas con docker compose, de forma autónoma, hasta que extraiga el detalle real de una foto de boleta. Trabaja en bucle hasta cumplir el criterio DONE.
  No me preguntes nada; decide y avanza.

  CONTEXTO:
  - Repo: este proyecto (fortunia). docker-compose.yml ya define el servicio `worker` (FastAPI + Tesseract), `postgres`, `pgadmin`, `db-backup`.
  - El README dice que el worker NO está containerizado (Apple Vision); eso está OBSOLETO. La verdad es docker-compose.yml + worker/Dockerfile + worker/app.py: worker containerizado con Tesseract. Confía
  en el compose.
  - Endpoint: POST /ocr (multipart, campo `image`) -> guarda imagen -> extract_from_bytes -> persiste en Postgres -> devuelve JSON con merchant, rut_emisor, folio, issued_date, total, items,
  validation_status.
  - Foto de prueba en la raíz: "WhatsApp Image 2026-06-28 at 9.34.22 PM.jpeg".

  ALCANCE:
  - Levanta SOLO `worker` y `postgres` (worker depende de postgres healthy). No levantes pgadmin ni db-backup.

  SETUP:
  - Si no existe .env, créalo copiando .env.example tal cual (passwords de ejemplo está bien, es local).

  AUTONOMÍA:
  - Auto-fix total. Si falla el build, el arranque, la conexión a DB, o la extracción, debuggea y edita lo que haga falta (Dockerfile, compose, requirements, código del worker, config) hasta que funcione.
  No hagas commit salvo que yo lo pida.

  DONE (criterio de éxito, todos):
  1. `docker compose up -d --build worker postgres` arranca sin error y ambos containers quedan healthy/running.
  2. GET http://localhost:8000/health devuelve {"ok": true, "db": true}.
  3. POST de la foto de prueba a http://localhost:8000/ocr devuelve HTTP 200 con status "stored", y el JSON trae AL MENOS uno de {merchant, total, items>0} con valor real (no null/0/vacío).
  4. La fila quedó persistida en Postgres (verifícalo con un SELECT vía docker compose exec).

  GUARDAS ANTI-LOOP-INFINITO:
  - Máx 8 iteraciones de fix. Tras cada fix, re-corre la verificación completa.
  - Si tras 8 iteraciones la extracción sigue vacía pero el endpoint responde 200 y guarda la imagen, marca PARCIAL, reporta exactamente qué campos faltan, qué intentaste, y los logs relevantes. No sigas
  iterando.

  REPORTE FINAL:
  - Estado: DONE / PARCIAL / BLOQUEADO.
  - Comandos para reproducir, JSON de respuesta del /ocr, fila de Postgres, y lista de archivos que modificaste.