"""Tests for pipeline.ats_signals — typed dispatch for post-submit confirmation."""
from unittest.mock import MagicMock

import pytest

from pipeline.ats_signals import detect_confirmation, greenhouse_confirmed


# -- greenhouse_confirmed: unit-test with mocked page --

def _make_mock_page(*, url="https://job-boards.greenhouse.io/x/jobs/1", h1_text=None, has_confirmation_attr=False):
    """Build a Playwright-page-shaped mock."""
    page = MagicMock()
    page.url = url

    h1_loc = MagicMock()
    if h1_text:
        h1_loc.is_visible.return_value = True
        h1_loc.text_content.return_value = h1_text
    else:
        h1_loc.is_visible.return_value = False
        h1_loc.text_content.return_value = ""

    confirm_loc = MagicMock()
    confirm_loc.is_visible.return_value = has_confirmation_attr

    def locator(selector):
        if "h1" in selector:
            return h1_loc
        if "data-application-confirmation" in selector:
            return confirm_loc
        return MagicMock(is_visible=MagicMock(return_value=False))
    page.locator.side_effect = locator
    return page


def test_greenhouse_confirmed_url_match_confirmation():
    page = _make_mock_page(url="https://job-boards.greenhouse.io/x/jobs/1/confirmation")
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_url_match_thanks():
    page = _make_mock_page(url="https://job-boards.greenhouse.io/x/applications/12345/thanks")
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_dom_match_thank_you():
    page = _make_mock_page(h1_text="Thank you for your application")
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_dom_match_data_attr():
    page = _make_mock_page(has_confirmation_attr=True)
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_no_signal_returns_false_after_timeout():
    page = _make_mock_page()  # No URL, no h1, no attr
    assert greenhouse_confirmed(page, timeout_seconds=1) is False


# -- detect_confirmation dispatch --

def test_detect_confirmation_dispatches_greenhouse_url():
    page = _make_mock_page(url="https://job-boards.greenhouse.io/x/jobs/1/confirmation")
    assert detect_confirmation(
        page,
        url="https://job-boards.greenhouse.io/x/jobs/1",
        timeout_seconds=1,
    ) is True


def test_detect_confirmation_unknown_ats_returns_false():
    page = _make_mock_page(url="https://workday.com/jobs/abc/done")
    assert detect_confirmation(
        page,
        url="https://workday.com/jobs/abc",
        timeout_seconds=1,
    ) is False
