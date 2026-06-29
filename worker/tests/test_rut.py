"""RUT mod-11 validation (the one deterministic bit live in Phase 0)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from normalize import rut_check_digit, validate_rut  # noqa: E402


def test_check_digit():
    assert rut_check_digit("11111111") == "1"
    assert rut_check_digit("12345678") == "5"


def test_validate_rut():
    assert validate_rut("11.111.111-1")
    assert validate_rut("12.345.678-5")
    assert not validate_rut("12.345.678-9")  # wrong DV
    assert not validate_rut("abc")
