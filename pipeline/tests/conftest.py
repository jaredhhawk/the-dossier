"""Shared test fixtures for pipeline unit tests."""
import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def scored_sample():
    """4-card synthetic scored JSON covering filter cases."""
    with open(FIXTURES_DIR / "scored_sample.json") as f:
        return json.load(f)


@pytest.fixture
def source_minimal():
    """Minimal source.json subset for tests that don't need full bio."""
    return {
        "meta": {
            "name": "Jared Hawkins",
            "location": "Seattle, WA",
            "email": "hawkins.jared@gmail.com",
            "phone": "555-1212",
            "linkedin": "https://www.linkedin.com/in/jaredhawkins/",
        },
        "summary_variants": {
            "product_management": "Senior PM with 10 years building...",
        },
    }
