"""Resolve a job listing to the real employer apply URL via search.

For each listing we have from the scored pipeline we know the company and role
title; that's enough to search for the actual employer posting (usually a
greenhouse/lever/ashby/workday page, or the company's own careers site).

Uses Brave Search HTML as primary (href URLs are clean, no redirect wrapper)
and DuckDuckGo HTML as secondary fallback. No API key, no OAuth, stdlib-only.
Results are ranked: ATS domains first, then company-branded careers subdomains,
then anything non-aggregator. Known aggregators (adzuna, indeed, linkedin/jobs,
glassdoor) are skipped since the whole point is to escape them.

If both search engines fail outright (network error, challenge page), fall
back to `search_fallback_url()` which builds a Google search URL the user can
open and click through.
"""
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}

# ATS / employer-native domains, ranked by preference (lower index = better)
_ATS_PRIORITY = [
    "greenhouse.io", "boards.greenhouse.io", "job-boards.greenhouse.io",
    "lever.co", "jobs.lever.co",
    "ashbyhq.com", "jobs.ashbyhq.com",
    "workday.com", "myworkdayjobs.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "icims.com",
    "taleo.net",
    "successfactors.com",
    "breezy.hr",
    "rippling.com",
    "gem.com",
    "jobvite.com",
    "workable.com",
    "teamtailor.com",
    "recruitee.com",
    "pinpointhq.com",
]

# Aggregators / indirection layers we want to escape, not land on
_AGGREGATOR_DOMAINS = (
    "adzuna.com", "indeed.com", "linkedin.com/jobs", "linkedin.com/company",
    "ziprecruiter.com", "glassdoor.com", "monster.com", "simplyhired.com",
    "jobsyn.org", "drjobpro.com", "talent.com", "jobcase.com", "neuvoo.com",
    "snagajob.com", "careerbuilder.com", "builtin.com",
    "jobs.google.com", "careers.google.com/jobs",
)

# Social, tracking, and misc non-result domains to skip
_NOISE_DOMAINS = (
    "duckduckgo.com", "google.com", "bing.com", "youtube.com", "facebook.com",
    "twitter.com", "x.com", "instagram.com", "pinterest.com", "reddit.com",
    "wikipedia.org", "wikimedia.org",
)


def _fetch(url, timeout=20, max_retries=2):
    """Fetch a URL. On 429/5xx, backs off 30-60s before retry."""
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    last_exc = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    last_exc = urllib.error.HTTPError(
                        url, resp.status, f"non-200 status {resp.status}",
                        resp.headers, None)
                    if resp.status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                        time.sleep(45.0)  # long backoff on rate-limit signals
                        continue
                    raise last_exc
                return resp.geturl(), resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(45.0)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(3.0)
                continue
            raise
    if last_exc:
        raise last_exc


_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', re.IGNORECASE)
_HREF_RE = re.compile(r'href="(https?://[^"]+)"', re.IGNORECASE)


def _brave_search(query, timeout=20):
    """Run a Brave Search HTML query. Returns a list of external result URLs."""
    url = "https://search.brave.com/search?" + urllib.parse.urlencode({"q": query})
    _, html = _fetch(url, timeout=timeout)
    results = []
    seen = set()
    for m in _HREF_RE.finditer(html):
        href = m.group(1)
        d = _domain(href)
        if "search.brave.com" in d or "brave.com" in d:
            continue
        if href in seen:
            continue
        seen.add(href)
        results.append(href)
    return results


def _ddg_search(query, timeout=20):
    """Run a DuckDuckGo HTML search. Returns a list of result URLs (decoded)."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    _, html = _fetch(url, timeout=timeout)
    results = []
    for m in _DDG_RESULT_RE.finditer(html):
        href = m.group(1)
        if href.startswith("//duckduckgo.com/l/?") or href.startswith("/l/?"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if "uddg" in qs:
                results.append(qs["uddg"][0])
        elif href.startswith("http"):
            results.append(href)
    return results


def _domain(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_aggregator(url):
    d = _domain(url)
    path = urllib.parse.urlparse(url).path.lower() if url else ""
    full = d + path
    return any(agg in full for agg in _AGGREGATOR_DOMAINS)


def _is_noise(url):
    d = _domain(url)
    return any(n in d for n in _NOISE_DOMAINS)


def _ats_rank(url):
    """Return index into _ATS_PRIORITY, or len(_ATS_PRIORITY) if not an ATS."""
    d = _domain(url)
    for i, ats in enumerate(_ATS_PRIORITY):
        if ats in d:
            return i
    return len(_ATS_PRIORITY)


def _pick_best(results, company):
    """Rank results and return the best candidate URL, or None.

    Preference order:
      1. ATS domains (greenhouse/lever/ashby/workday/etc), by ATS priority list
      2. URLs on the company's own domain (heuristic: company name in netloc)
      3. Any other non-aggregator, non-noise URL
    """
    if not results:
        return None

    company_slug = re.sub(r"[^a-z0-9]", "", (company or "").lower())

    def company_match(url):
        if not company_slug:
            return False
        d_slug = re.sub(r"[^a-z0-9]", "", _domain(url))
        return bool(company_slug) and company_slug in d_slug

    def rank(url):
        if _is_noise(url):
            return (9, 0)
        if _is_aggregator(url):
            return (8, 0)
        ats = _ats_rank(url)
        if ats < len(_ATS_PRIORITY):
            return (0, ats)
        if company_match(url):
            return (1, 0)
        return (5, 0)

    ranked = sorted(results, key=rank)
    best = ranked[0]
    if _is_aggregator(best) or _is_noise(best):
        return None
    return best


_SEARCH_ENGINES = [
    ("brave", _brave_search),
    ("ddg", _ddg_search),
]


def search_employer_url(company, title, timeout=20):
    """Search for the real employer apply URL for a company + role.

    Tries Brave Search first, then DuckDuckGo, with progressively looser
    queries on each engine. Returns on the first engine/query pair that yields
    a usable (non-aggregator, non-noise) result.

    Returns (url, status) where status is one of:
      "ok:<engine>"  -- found a usable result via <engine>
      "no_results"   -- all engines/queries returned only aggregators/noise
      "error:<type>" -- all engines failed (network, challenge page)
    """
    queries = [
        f'"{company}" "{title}" careers',
        f'"{company}" {title}',
        f'{company} {title}',
    ]
    last_error = None
    had_results = False
    for engine_name, engine_fn in _SEARCH_ENGINES:
        for q in queries:
            try:
                results = engine_fn(q, timeout=timeout)
            except (urllib.error.HTTPError, urllib.error.URLError,
                    TimeoutError, OSError) as e:
                last_error = f"error:{type(e).__name__}"
                break  # move to next engine; don't keep retrying broken engine
            if results:
                had_results = True
            best = _pick_best(results, company)
            if best:
                return best, f"ok:{engine_name}"
    if had_results:
        return None, "no_results"
    return None, last_error or "no_results"


def search_fallback_url(company, title):
    """Build a Google search URL for a company + role, suitable for opening in
    a browser when resolution fails -- the user can click the right result.
    """
    q = f'"{company}" "{title}" careers'
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(q)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: url_resolver.py <company> <title>")
        sys.exit(1)
    url, status = search_employer_url(sys.argv[1], sys.argv[2])
    print(f"status: {status}")
    print(f"url:    {url}")
