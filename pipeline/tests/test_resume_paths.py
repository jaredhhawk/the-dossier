"""Tests for resume output-path helpers."""
from datetime import date
from pipeline.resume import build_output_path


def test_build_output_path_uses_today_by_default():
    p = build_output_path("product_management", company="Acme", role="PM",
                          full_name="Jared Hawkins")
    assert date.today().isoformat() in p.name


def test_build_output_path_accepts_explicit_date():
    p = build_output_path("product_management", company="Acme", role="PM",
                          full_name="Jared Hawkins", date_str="2026-04-22")
    assert "2026-04-22" in p.name
    assert "Jared-Hawkins-Acme-PM-2026-04-22" in p.name


def test_build_output_path_explicit_date_archetype_only():
    """No company+role → archetype-based name still respects date_str."""
    p = build_output_path("operations", date_str="2026-04-22")
    assert "operations-2026-04-22" in p.name
