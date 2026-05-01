"""Tests for pregenerate orchestrator pure functions."""
from pathlib import Path
import json

from pipeline.pregenerate import (
    filter_cards,
    derive_date_from_scored_path,
    build_card_slug,
    build_manifest,
    update_scored_with_artifacts,
)


def test_filter_cards_keeps_grade_a_b_new_resolvable(scored_sample):
    kept = filter_cards(scored_sample, grades=("A", "B"))
    assert len(kept) == 2
    companies = {c["company"] for c in kept}
    assert companies == {"AcmeCorp", "BetaInc"}


def test_filter_cards_drops_grade_c(scored_sample):
    kept = filter_cards(scored_sample, grades=("A", "B"))
    assert all(c["grade"] in ("A", "B") for c in kept)


def test_filter_cards_drops_already_applied(scored_sample):
    kept = filter_cards(scored_sample, grades=("A", "B"))
    assert all(c["status"] == "new" for c in kept)


def test_filter_cards_grade_a_only(scored_sample):
    kept = filter_cards(scored_sample, grades=("A",))
    assert len(kept) == 1
    assert kept[0]["company"] == "AcmeCorp"


def test_derive_date_from_scored_path():
    assert derive_date_from_scored_path(Path("foo/2026-04-22.json")) == "2026-04-22"
    assert derive_date_from_scored_path(Path("/abs/path/2026-04-22.json")) == "2026-04-22"


def test_derive_date_rejects_non_date_filename():
    import pytest
    with pytest.raises(ValueError):
        derive_date_from_scored_path(Path("foo/not-a-date.json"))


def test_build_card_slug_is_deterministic():
    card = {"company": "Acme Co", "title": "Senior PM", "url": "https://x.example/1"}
    a = build_card_slug(card, date_str="2026-04-22")
    b = build_card_slug(card, date_str="2026-04-22")
    assert a == b
    assert "Acme-Co" in a
    assert "Senior-PM" in a
    assert "2026-04-22" in a


def test_build_manifest_schema(tmp_path: Path):
    generated = [{"company": "X", "role": "Y", "url": "u",
                  "resume_pdf": "/r.pdf", "cl_pdf": "/c.pdf",
                  "jd_cache": "/j.txt"}]
    cached = [{"company": "Z", "role": "W", "url": "u2",
               "resume_pdf": "/r2.pdf", "cl_pdf": "/c2.pdf",
               "jd_cache": "/j2.txt"}]
    failures = [{"company": "F", "role": "G", "url": "u3", "reason": "no resolved url"}]
    m = build_manifest(date_str="2026-04-22",
                       scored_file="/abs/2026-04-22.json",
                       generated=generated, cached=cached, failures=failures)
    assert m["date"] == "2026-04-22"
    assert m["scored_file"] == "/abs/2026-04-22.json"
    assert m["counts"] == {"generated": 1, "cached": 1, "failures": 1}
    assert m["generated"] == generated
    assert m["cached"] == cached
    assert m["failures"] == failures
    assert "generated_at" in m  # ISO timestamp


def test_update_scored_with_artifacts_adds_artifacts_field(scored_sample):
    artifacts_by_url = {
        "https://job-boards.greenhouse.io/acmecorp/jobs/12345": {
            "resume_pdf": "/r.pdf", "cl_pdf": "/c.pdf", "jd_cache": "/j.txt",
        }
    }
    updated = update_scored_with_artifacts(scored_sample, artifacts_by_url)
    by_url = {c["url"]: c for c in updated}
    acme = by_url["https://job-boards.greenhouse.io/acmecorp/jobs/12345"]
    assert "artifacts" in acme
    assert acme["artifacts"]["resume_pdf"] == "/r.pdf"
    # Other cards unchanged
    beta = by_url["https://jobs.lever.co/betainc/abc123"]
    assert "artifacts" not in beta
    # Non-artifact fields preserved
    assert acme["grade"] == "A"
    assert acme["company"] == "AcmeCorp"
