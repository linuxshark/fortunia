#!/usr/bin/env python3
"""CLI: extract a single boleta and store it. The "read + extract" script.

  python scan.py /path/boleta.jpg          # extract + insert into DB
  python scan.py /path/boleta.pdf          # PDF -> render page 1 -> extract
  python scan.py /path/boleta.jpg --dry    # extract + print, do NOT touch DB

Runs on the host (needs tesseract + the worker deps) or inside the container:
  docker compose exec worker python scan.py data/images/<sha>.bin
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from extractor import extract_from_bytes


def load_bytes(path: Path) -> bytes:
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(path))
        bitmap = pdf[0].render(scale=200 / 72)   # ~200 DPI
        img = bitmap.to_pil()
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    return path.read_bytes()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if not args:
        print("usage: python scan.py <image|pdf> [--dry]", file=sys.stderr)
        return 2

    path = Path(args[0]).expanduser().resolve()
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 2

    raw = load_bytes(path)
    result = extract_from_bytes(raw, source_image_path=str(path))

    summary = {k: v for k, v in result.items() if k != "ocr_raw_text"}
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))

    if dry:
        print("\n[--dry] not written to DB", file=sys.stderr)
        return 0

    import db
    receipt_id, created = db.persist(result)
    if created:
        print(f"\nstored receipt_id={receipt_id} "
              f"({len(result['line_items'])} items, status={result['validation_status']})",
              file=sys.stderr)
    else:
        print("\nduplicate — already in DB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
