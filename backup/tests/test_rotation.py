import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rotation import parse_ts, select_keep, plan_prune, tier_for  # noqa: E402


def test_parse_ts_ok():
    assert parse_ts("db-20260701-030000.dump") == datetime(2026, 7, 1, 3, 0, 0)


def test_parse_ts_bad_returns_none():
    assert parse_ts("images") is None
    assert parse_ts("db-nope.dump") is None


def test_keeps_last_n_daily():
    # 10 días consecutivos, 1 dump/día; con keep_daily=7 y 0 semanales/mensuales
    ts = [datetime(2026, 6, d, 3, 0, 0) for d in range(1, 11)]
    kept = select_keep(ts, keep_daily=7, keep_weekly=0, keep_monthly=0)
    assert kept == set(ts[-7:])          # los 7 más recientes


def test_multiple_per_day_keeps_latest_of_day():
    ts = [datetime(2026, 6, 1, 3, 0, 0), datetime(2026, 6, 1, 21, 0, 0)]
    kept = select_keep(ts, keep_daily=1, keep_weekly=0, keep_monthly=0)
    assert kept == {datetime(2026, 6, 1, 21, 0, 0)}   # el más tardío del día


def test_weekly_and_monthly_extend_retention():
    # un dump por día durante ~100 días -> con 7d/4w/12m se conservan más que 7
    base = datetime(2026, 1, 1, 3, 0, 0)
    ts = [base.replace() for _ in range(0)]
    from datetime import timedelta
    ts = [base + timedelta(days=i) for i in range(100)]
    kept = select_keep(ts, keep_daily=7, keep_weekly=4, keep_monthly=12)
    # 7 diarios + hasta 4 semanales + hasta 3-4 mensuales (100 días ~ 3 meses)
    assert len(kept) >= 7 + 3          # estrictamente más que solo diarios
    assert set(ts[-7:]).issubset(kept) # los 7 últimos siempre están


def test_plan_prune_returns_names_to_delete():
    names = [f"db-202606{d:02d}-030000.dump" for d in range(1, 11)]
    names.append("images")             # no es dump -> se ignora, nunca se borra
    to_delete = plan_prune(names, keep_daily=7, keep_weekly=0, keep_monthly=0)
    assert "images" not in to_delete
    assert set(to_delete) == {f"db-202606{d:02d}-030000.dump" for d in range(1, 4)}


def test_tier_for_labels():
    now = datetime(2026, 7, 1, 3, 0, 0)
    from datetime import timedelta
    assert tier_for(now - timedelta(days=2), now) == "diario"
    assert tier_for(now - timedelta(days=20), now) == "semanal"
    assert tier_for(now - timedelta(days=200), now) == "mensual"
