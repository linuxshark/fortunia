# Integración Fortunia con Kraken (OpenClaw)

Guía paso a paso para integrar Fortunia como sub-agente delegado desde Kraken.

## Flujo de delegación

```
Usuario (Telegram)
    ↓
Kraken (agente principal)
    ↓ finance_detector.py (regex, zero tokens)
    ↓ Decidir: ¿es gasto?
    ↓ Si SÍ → /ingest/check (HTTP)
    ↓
Fortunia (sub-agente)
    ↓ parse_expense_text()
    ↓ Crear Expense en DB
    ↓ Devolver user_message
    ↓
Kraken
    ↓ Reenviar user_message a Telegram
```

## Requisitos previos

- Fortunia API corriendo en `http://localhost:8000` (desde `docker compose up -d`)
- OpenClaw instalado y configurado
- Kraken agente principal ya funcional
- `~/.openclaw/` directorio accesible

## Instalación paso a paso

### 1. Copiar archivos de integración

```bash
# Estos archivos ya están en kraken-integration/
cp kraken-integration/intent/finance_detector.py ~/projects/fortunia/
cp kraken-integration/delegators/fortunia_client.py ~/projects/fortunia/
```

### 2. Crear workspace de Fortunia

```bash
mkdir -p ~/.openclaw/workspace-fortunia

cat > ~/.openclaw/workspace-fortunia/AGENTS.md <<'EOF'
# Fortunia — Sub-agente financiero

Eres Fortunia, especialista en finanzas personales del usuario.

## Tu rol

Procesas gastos (texto, imagen, audio) sin conversación:

1. **Texto**: Llama a `fortunia_ingest_text` con el texto del usuario
2. **Imagen**: Llama a `fortunia_ingest_image` con ruta de boleta
3. **Audio**: Llama a `fortunia_ingest_audio` con ruta de audio

## Respuesta

La herramienta devuelve un campo `user_message` listo para Telegram.
Devuélvelo **TAL CUAL** al usuario (no re-escribas, no expliques, no reformules).

Si `needs_confirmation=true`, el mensaje ya incluye la pregunta.
Kraken se encarga de mostrar botones.

## Regla de oro

**Procesa y responde. No conversas.**
EOF
```

### 3. Actualizar configuración de OpenClaw

Abre `~/.openclaw/openclaw.json` y:

a. Agrega Fortunia a la lista de agentes:

```json5
{
  "agents": [
    {
      "id": "kraken",
      "name": "Kraken",
      // ... config existente de Kraken
    },
    {
      // Copia el contenido de openclaw-config-snippet.json5 aquí
      "id": "fortunia",
      "name": "Fortunia",
      // ...
    }
  ],
  // ...
}
```

b. Asegúrate que `agentToAgent` está habilitado:

```json5
{
  "agentToAgent": {
    "enabled": true,
    "allowList": ["kraken", "fortunia"]  // o "*" para todos
  },
  "subagents": {
    "allowAgents": ["fortunia"]  // Kraken puede invocar Fortunia
  }
}
```

### 4. Actualizar AGENTS.md de Kraken

En `~/.openclaw/workspace/AGENTS.md` (o donde viva Kraken), agrega:

```markdown
## Delegación a Fortunia (finanzas)

Antes de responder un mensaje, verifica si es financiero:

```bash
python3 /ruta/a/finance_detector.py "$usuario_mensaje"
```

Si output contiene `IS_FINANCE=true` con confidence ≥ 0.75:
- NO respondas tú
- Delega a Fortunia: `agent_send(agentId="fortunia", message="$usuario_mensaje")`
- Reenvía su respuesta textualmente al usuario

Si confidence < 0.75 o ambiguo, responde normalmente.

### Ejemplos:

**SÍ delegar:**
- "gasté 15 lucas en ropa" → IS_FINANCE=true (0.95)
- "pagué uber 6500" → IS_FINANCE=true (0.95)

**NO delegar:**
- "vi una película que costó 20 millones" → IS_FINANCE=false
- "leí que iPhone cuesta 1.5 millones" → IS_FINANCE=false
```

### 5. Reiniciar OpenClaw

```bash
openclaw gateway restart

# Verificar que Fortunia está registrada
openclaw agent list
```

## Verificación

### Test 1: Intent check

```bash
python3 kraken-integration/intent/finance_detector.py "gasté 15 lucas en ropa"
# Esperado: IS_FINANCE=true, CONFIDENCE=0.95
```

### Test 2: Ingest via Kraken

En Telegram a Kraken:
```
gasté 15 lucas en ropa
```

Esperado: Kraken delega a Fortunia y responde:
```
✅ Registrado: Ropa — CLP 15.000
```

### Test 3: Image/audio (si está todo levantado)

En Telegram a Kraken:
1. Envía foto de boleta del Jumbo
   - Esperado: OCR + parse → "✅ Boleta registrada: Alimentación — CLP X"

2. Envía audio diciendo "gasté 5 lucas en café"
   - Esperado: Whisper + parse → "✅ Audio registrado: Alimentación — CLP 5.000"

## Troubleshooting

### "agent_send not working"

- Verifica `agentToAgent.enabled = true` en openclaw.json
- Verifica `subagents.allowAgents` incluye "fortunia"
- Reinicia: `openclaw gateway restart`

### "Fortunia API not responding"

```bash
# Verifica que Fortunia está running
docker compose ps

# Verifica connectivity
curl http://localhost:8000/health
# Esperado: {"status":"ok"}
```

### "finance_detector.py error"

```bash
# Verifica que el archivo es ejecutable
chmod +x kraken-integration/intent/finance_detector.py

# Test directo
python3 kraken-integration/intent/finance_detector.py "test"
```

### "High LLM usage"

Si ves que `/intent/check` llama a LLM más de lo esperado:
- Revisar que `is_finance_intent()` está usando solo reglas (sin LLM)
- Aumentar negative context patterns en `finance_detector.py`
- Revisar dataset de tests

## Monitoring

En Fortunia API:
- `raw_messages.used_llm` = count de mensajes que usaron LLM
- Meta: < 10%

Dashboard: `/reports/today`, `/reports/month` (accesible desde LAN)

## Désactivar temporalmente

Si necesitas pausar la delegación:

En AGENTS.md de Kraken, comenta la sección de delegación.
Reinicia Kraken.

Fortunia sigue corriendo, pero Kraken no delega.

## v2 Features (futuro)

- [ ] Multi-language support
- [ ] User preferences (default category, currency)
- [ ] Feedback loop para mejorar intent_detector
- [ ] Export (CSV, XLSX)
- [ ] Recurring expenses
- [ ] Budget alerts
