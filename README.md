# Fortunia — Sub-agente financiero personal

Personal expense tracking sub-agent for OpenClaw.

Integrates with **Kraken** (main personal agent) to process expenses from text, images (receipts), and audio — all locally, deterministically, minimal LLM use.

## Quick Start

```bash
cp .env.example .env
# Edit .env, generate secrets
./install.sh
```

## Documentation

- Full setup: see IMPLEMENTATION_PLAN.md (stages 1-8)
- Architecture: docs/ARCHITECTURE.md (after stage 8)
- Kraken integration: kraken-integration/README.md (stage 7)

## Stack

- FastAPI + PostgreSQL + Next.js 14
- Docker Compose (self-hosted, M1 Mac)
- OCR (Tesseract) + STT (Whisper) local
- Deterministic parsers, <10% LLM use

---

**TODO**: Full docs, screenshots, troubleshooting in stage 8.
