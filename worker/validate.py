"""Validation gate before insert. Arithmetic + SII checksums.

See docs/03-architecture.md Stage 6. Never trust unvalidated financial rows;
failures get validation_status='review' (still stored, surfaced to the user).
"""
from __future__ import annotations

from decimal import Decimal

TOLERANCE = Decimal("1")  # CLP rounding tolerance


def validate(header: dict, items: list[dict]) -> tuple[str, list[str]]:
    """Return (status, problems) where status in {'ok','review','failed'}.

    Chilean consumer prices are IVA-included, so line totals SUM to the grand
    total (neto/IVA are a breakdown of it, not an addend).

    Checks:
      - each line: qty * unit_price == line_total       (+/- TOLERANCE)
      - sum(line_totals) == total                       (+/- per-line tolerance)
      - net + tax == total                              (+/- TOLERANCE)
      - OCR total == TED MNT (ground-truth cross-check) when TED present
      - RUT mod-11 already validated upstream (normalize.validate_rut)
    """
    problems: list[str] = []
    total = header.get("total")
    ted_total = header.get("ted_total")
    net = header.get("net")
    tax = header.get("tax")

    if ted_total is not None and total is not None and abs(Decimal(total) - Decimal(ted_total)) > TOLERANCE:
        problems.append(f"OCR total {total} != TED MNT {ted_total}")

    if None not in (net, tax, total) and abs(Decimal(net) + Decimal(tax) - Decimal(total)) > TOLERANCE:
        problems.append(f"net+tax {Decimal(net) + Decimal(tax)} != total {total}")

    line_sum = Decimal(0)
    for it in items:
        qty, up, lt = it.get("qty"), it.get("unit_price"), it.get("line_total")
        if None not in (qty, up, lt) and abs(Decimal(qty) * Decimal(up) - Decimal(lt)) > TOLERANCE:
            problems.append(f"line {it.get('line_no')}: qty*price != line_total")
        if lt is not None:
            line_sum += Decimal(lt)

    line_tol = TOLERANCE * max(1, len(items))   # allow a few CLP rounding across lines
    if total is not None and items and abs(line_sum - Decimal(total)) > line_tol:
        problems.append(f"sum(lines) {line_sum} != total {total}")

    return ("ok", []) if not problems else ("review", problems)
