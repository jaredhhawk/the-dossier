#!/usr/bin/env python3
"""
V2 Pivot-Optimized Scorer
Scores listings using heuristics for the v2 scoring system.

Dimensions (1-5 each):
  3x: transferable_skills, hiring_accessibility, interview_likelihood
  2x: compensation, geographic_fit, timeline_urgency
  1x: role_match, seniority_fit, company_quality, growth_potential

Formula: (3*(ts+ha+il) + 2*(comp+geo+time) + 1*(rm+sf+cq+gp)) / 19 + neg_adj
Grades: A>=4.0, B>=3.5, C>=2.5, D>=1.5, F<1.5
"""
import csv
import json
import re
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

CSV_PATH = Path("pipeline/data/listings/2026-04-22-deduped.csv")
OUT_PATH = Path("pipeline/data/scored/2026-04-22.json")
BLACKLIST = {"amazon"}

# --- Transferable skills keywords (things Jared can do regardless of title) ---
TRANSFERABLE_KEYWORDS = {
    "high": [  # 2 points each
        "stakeholder management", "cross-functional", "cross functional",
        "data-driven", "data driven", "process design", "process improvement",
        "systems thinking", "roadmap", "go-to-market", "gtm",
        "product strategy", "okr", "kpi", "agile", "scrum",
        "api", "data pipeline", "analytics", "ai ", "machine learning",
        "llm", "automation", "platform", "infrastructure",
    ],
    "medium": [  # 1 point each
        "project management", "budget", "vendor", "stakeholder",
        "coordination", "planning", "reporting", "metrics",
        "customer", "requirements", "strategy", "leadership",
        "team management", "delivery", "execution", "operations",
        "process", "workflow", "optimization", "integration",
        "communication", "presentation", "negotiation",
    ],
}

# --- Hiring accessibility patterns ---
FAANG_LIKE = {
    "amazon", "google", "meta", "apple", "microsoft", "netflix",
    "alphabet", "facebook", "tiktok", "bytedance", "uber", "lyft",
    "airbnb", "stripe", "snowflake", "databricks", "salesforce",
    "oracle", "adobe", "intuit", "palantir", "coinbase",
}
CONSULTING_FIRMS = {
    "deloitte", "mckinsey", "bain", "bcg", "accenture", "pwc",
    "ernst & young", "ey", "kpmg", "booz allen",
}
STAFFING_AGENCIES = {
    "tekwissen", "robert half", "randstad", "adecco", "manpower",
    "hays", "kelly services", "insight global", "apex systems",
    "tata consultancy", "infosys", "wipro", "cognizant",
}

# --- Lane B title patterns (skills-transfer roles) ---
LANE_B_TITLES = [
    "facilities manager", "facilities director",
    "construction manager", "construction project",
    "procurement manager", "procurement director", "procurement lead",
    "property manager", "property director",
    "project manager",  # generic (not "product")
    "implementation manager", "implementation director",
    "logistics manager", "logistics director", "supply chain",
    "business operations", "operations manager", "operations director",
    "training manager", "training director", "learning and development",
    "change management",
    "process improvement",
    "vendor manager", "vendor management",
    "real estate",
]

# --- Lane C title patterns (discovery roles) ---
LANE_C_TITLES = [
    "solutions engineer", "solutions architect",
    "business development", "partnerships",
    "strategic planning", "strategy manager",
    "chief of staff",
    "revenue operations", "revops",
    "customer success",
    "technical account manager", "tam ",
    "account manager",
]

# --- Seniority patterns ---
SENIOR_TITLES = ["principal", "staff", "senior", "sr.", "sr ", "lead"]
DIRECTOR_TITLES = ["director", "vp ", "vice president", "head of", "avp"]
ENTRY_MID_TITLES = ["coordinator", "associate", "junior", "jr.", "intern", "entry"]

# --- PM title patterns (Lane A core) ---
PM_TITLES = [
    "product manager", "product owner", "product lead",
    "product director", "head of product", "vp product",
    "product operations", "product ops",
]

def parse_salary(salary_str):
    """Extract numeric salary values, return (low, high) or (None, None)."""
    if not salary_str or salary_str.strip() == "":
        return None, None
    nums = re.findall(r'[\$]?([\d,]+)', salary_str)
    if not nums:
        return None, None
    values = [int(n.replace(",", "")) for n in nums]
    # Filter out obviously wrong values (hourly rates, etc.)
    values = [v for v in values if v > 20000]
    if not values:
        return None, None
    return min(values), max(values)


def classify_lane(title_lower, desc_lower):
    """Classify listing into Lane A, B, or C."""
    # Check Lane B first (skills-transfer)
    for pattern in LANE_B_TITLES:
        if pattern in title_lower:
            # But "product manager" in title overrides to Lane A
            if any(pm in title_lower for pm in PM_TITLES):
                return "A"
            return "B"

    # Check Lane C (discovery)
    for pattern in LANE_C_TITLES:
        if pattern in title_lower:
            return "C"

    # Default: Lane A (PM-adjacent tech)
    return "A"


def classify_archetype(title_lower, desc_lower):
    """Match to archetype based on config keywords."""
    if any(k in title_lower for k in ["ai ", "ai-", "machine learning", "ml "]):
        return "ai_technical"
    if any(k in title_lower for k in PM_TITLES):
        return "product_management"
    if any(k in title_lower for k in ["customer success", "account manager", "tam ", "technical account", "solutions", "client"]):
        return "customer_success"
    if any(k in title_lower for k in ["city manager", "county", "municipal", "public sector", "government", "federal"]):
        return "government"
    return "operations"


def score_transferable_skills(title_lower, desc_lower):
    """Score 1-5 based on how many transferable skill keywords appear in description."""
    points = 0
    for kw in TRANSFERABLE_KEYWORDS["high"]:
        if kw in desc_lower:
            points += 2
    for kw in TRANSFERABLE_KEYWORDS["medium"]:
        if kw in desc_lower:
            points += 1
    # Normalize: 0-5pts=1, 6-10=2, 11-15=3, 16-22=4, 23+=5
    if points >= 23: return 5
    if points >= 16: return 4
    if points >= 11: return 3
    if points >= 6: return 2
    return 1


def score_hiring_accessibility(title_lower, company_lower, lane):
    """Score 1-5 based on talent pool saturation and company type."""
    score = 3  # default

    # FAANG/big tech PM = oversaturated
    is_faang = any(f in company_lower for f in FAANG_LIKE)
    is_consulting = any(c in company_lower for c in CONSULTING_FIRMS)
    is_staffing = any(s in company_lower for s in STAFFING_AGENCIES)
    is_pm = any(pm in title_lower for pm in PM_TITLES)

    if is_faang and is_pm:
        score = 1  # worst: FAANG PM pool
    elif is_faang:
        score = 2  # FAANG non-PM still competitive
    elif is_consulting:
        score = 2  # rigid hiring pipeline
    elif is_staffing:
        score = 2  # intermediary, limited growth
    elif is_pm and lane == "A":
        score = 3  # PM at non-FAANG, moderately competitive
    elif lane == "B":
        score = 4  # skills-transfer: differentiated talent pool
    elif lane == "C":
        score = 4  # discovery: different talent pool
    else:
        score = 3

    # Startup boost: if company name is short/unknown and not in big lists, likely smaller
    if not is_faang and not is_consulting and not is_staffing:
        if lane == "A" and is_pm:
            # Small/startup PM roles get a boost
            score = min(score + 1, 5)

    return score


def score_interview_likelihood(title_lower, company_lower, lane, seniority_fit):
    """Score 1-5 based on realistic shot at a screen."""
    score = 3

    is_faang = any(f in company_lower for f in FAANG_LIKE)
    is_pm = any(pm in title_lower for pm in PM_TITLES)
    is_director = any(d in title_lower for d in DIRECTOR_TITLES)

    if is_faang:
        score -= 1  # FAANG bar reduces likelihood
    if is_director:
        score -= 1  # Director level harder to land
    if is_pm and is_faang:
        score -= 1  # Double penalty: PM at FAANG

    # Lane B/C boost: less competition in these pools
    if lane in ("B", "C"):
        score += 1

    # Overqualification concern at entry/mid level
    if any(e in title_lower for e in ENTRY_MID_TITLES):
        score -= 1  # HM may not want someone too senior

    # Seniority mismatch penalty
    if seniority_fit <= 2:
        score -= 1

    return max(1, min(5, score))


def score_compensation(salary_low, salary_high):
    """Score 1-5 based on salary."""
    if salary_low is None:
        return 3  # unknown, assume average
    mid = (salary_low + salary_high) / 2 if salary_high else salary_low
    if mid >= 200000: return 5
    if mid >= 150000: return 4
    if mid >= 100000: return 3
    if mid >= 80000: return 2
    return 1


def score_geographic_fit(location):
    """Score 1-5 based on location."""
    loc_lower = location.lower()
    if any(s in loc_lower for s in ["seattle", "king county", "bellevue", "kirkland", "redmond", "tacoma", "renton", "kent"]):
        return 5
    if "remote" in loc_lower or loc_lower.strip() == "":
        return 4
    if any(s in loc_lower for s in ["washington", "portland", "oregon"]):
        return 3
    if any(s in loc_lower for s in ["san francisco", "new york", "los angeles", "boston", "chicago", "austin", "denver"]):
        return 2
    return 1


def score_seniority_fit(title_lower):
    """Score 1-5. Jared is Principal/Staff level. Overqualification penalized."""
    is_senior = any(s in title_lower for s in SENIOR_TITLES)
    is_director = any(d in title_lower for d in DIRECTOR_TITLES)
    is_entry = any(e in title_lower for e in ENTRY_MID_TITLES)

    if "principal" in title_lower or "staff" in title_lower:
        return 5  # perfect match
    if is_senior:
        return 4  # slightly under, fine
    if is_director:
        return 3  # stretch up, HM may question
    if is_entry:
        return 2  # overqualified, HM concern
    return 3  # generic/unclear


def score_company_quality(company_lower):
    """Score 1-5."""
    is_faang = any(f in company_lower for f in FAANG_LIKE)
    is_staffing = any(s in company_lower for s in STAFFING_AGENCIES)

    if is_faang:
        return 5
    if is_staffing:
        return 2
    return 3  # default for unknown companies


def score_growth_potential(title_lower, lane):
    """Score 1-5."""
    is_director = any(d in title_lower for d in DIRECTOR_TITLES)
    is_entry = any(e in title_lower for e in ENTRY_MID_TITLES)

    if is_director:
        return 4
    if is_entry:
        return 2
    if lane == "B":
        return 3  # skills transfer roles: career change, moderate growth
    return 3


def score_role_match(title_lower, desc_lower):
    """Score 1-5. How well title/responsibilities align with resume. Kept but downweighted."""
    score = 2  # base: most roles partially match some experience

    # Direct PM title match
    if any(pm in title_lower for pm in PM_TITLES):
        score = 5
    # PM-adjacent
    elif any(k in title_lower for k in ["program manager", "chief of staff", "customer success"]):
        score = 4
    # Tech/AI roles
    elif any(k in title_lower for k in ["ai ", "machine learning", "solutions engineer"]):
        score = 4
    # Operations (transferable)
    elif any(k in title_lower for k in ["operations manager", "business operations", "project manager"]):
        score = 3
    # Lane B (less direct match)
    elif any(k in title_lower for k in ["construction", "procurement", "facilities", "property manager", "logistics"]):
        score = 2

    return score


def generate_rationale(title, company, lane, archetype, hiring_acc, interview_like, geo_fit, comp_score):
    """Generate a brief rationale string."""
    parts = []

    # Lane context
    if lane == "B":
        parts.append(f"Skills-transfer role.")
    elif lane == "C":
        parts.append(f"Discovery lane.")

    # Hiring signal
    if hiring_acc >= 4:
        parts.append("Less competitive talent pool.")
    elif hiring_acc <= 2:
        parts.append("Oversaturated/rigid hiring.")

    # Interview signal
    if interview_like >= 4:
        parts.append("Good interview likelihood.")
    elif interview_like <= 2:
        parts.append("Low interview likelihood.")

    # Geo
    if geo_fit <= 2:
        parts.append("Geographic miss.")
    elif geo_fit == 5:
        parts.append("Seattle area.")

    # Comp
    if comp_score >= 4:
        parts.append("Strong comp.")
    elif comp_score <= 2:
        parts.append("Below target comp.")

    return " ".join(parts) if parts else f"{archetype.replace('_', ' ').title()} role."


def compute_weighted(ts, ha, il, comp, geo, time, rm, sf, cq, gp, neg):
    raw = (3*(ts + ha + il) + 2*(comp + geo + time) + 1*(rm + sf + cq + gp)) / 19
    return round(raw + neg, 2)


def grade(ws):
    if ws >= 4.0: return "A"
    if ws >= 3.5: return "B"
    if ws >= 2.5: return "C"
    if ws >= 1.5: return "D"
    return "F"


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load existing scored JSON if present (preserve manually scored entries)
    existing = []
    existing_keys = set()
    if OUT_PATH.exists():
        with open(OUT_PATH) as f:
            existing = json.load(f)
        for e in existing:
            existing_keys.add((e.get("company", ""), e.get("title", ""), e.get("url", "")))

    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            company = row["company"]
            title = row["title"]
            url = row["url"]

            # Skip if already scored
            if (company, title, url) in existing_keys:
                continue

            company_lower = company.lower().strip()
            title_lower = title.lower().strip()
            desc_lower = row.get("description", "").lower()

            # Blacklist check
            if any(b in company_lower for b in BLACKLIST):
                rows.append({
                    "title": title, "company": company,
                    "location": row["location"], "salary": row["salary"],
                    "url": url, "source": row["source"],
                    "description": row.get("description", ""),
                    "scores": {k: 0 for k in ["transferable_skills","hiring_accessibility",
                        "interview_likelihood","compensation","geographic_fit",
                        "timeline_urgency","role_match","seniority_fit",
                        "company_quality","growth_potential"]},
                    "negative_adjustment": 0, "weighted_score": 0.0,
                    "grade": "F", "archetype": "operations", "lane": "A",
                    "rationale": f"BLACKLISTED: {company}",
                    "red_flags": [], "status": "new",
                })
                continue

            # Classify
            lane = classify_lane(title_lower, desc_lower)
            archetype = classify_archetype(title_lower, desc_lower)

            # Parse salary
            sal_low, sal_high = parse_salary(row.get("salary", ""))

            # Score all dimensions
            sf = score_seniority_fit(title_lower)
            ts = score_transferable_skills(title_lower, desc_lower)
            ha = score_hiring_accessibility(title_lower, company_lower, lane)
            il = score_interview_likelihood(title_lower, company_lower, lane, sf)
            comp = score_compensation(sal_low, sal_high)
            geo = score_geographic_fit(row.get("location", ""))
            time_urg = 4  # all discovered today
            rm = score_role_match(title_lower, desc_lower)
            cq = score_company_quality(company_lower)
            gp = score_growth_potential(title_lower, lane)

            # Negative adjustments
            neg = 0.0
            red_flags = []

            is_faang = any(f in company_lower for f in FAANG_LIKE)
            is_staffing = any(s in company_lower for s in STAFFING_AGENCIES)
            is_director = any(d in title_lower for d in DIRECTOR_TITLES)
            is_pm = any(pm in title_lower for pm in PM_TITLES)

            if is_faang and is_pm:
                neg -= 0.5
                red_flags.append("FAANG PM oversaturation")
            if is_staffing:
                neg -= 0.3
                red_flags.append("Staffing agency")
            if is_director and is_faang:
                neg -= 0.3
                red_flags.append("FAANG Director stretch")

            ws = compute_weighted(ts, ha, il, comp, geo, time_urg, rm, sf, cq, gp, neg)
            g = grade(ws)
            rationale = generate_rationale(title, company, lane, archetype, ha, il, geo, comp)

            rows.append({
                "title": title, "company": company,
                "location": row["location"], "salary": row["salary"],
                "url": url, "source": row["source"],
                "description": row.get("description", ""),
                "scores": {
                    "transferable_skills": ts, "hiring_accessibility": ha,
                    "interview_likelihood": il, "compensation": comp,
                    "geographic_fit": geo, "timeline_urgency": time_urg,
                    "role_match": rm, "seniority_fit": sf,
                    "company_quality": cq, "growth_potential": gp,
                },
                "negative_adjustment": neg, "weighted_score": ws,
                "grade": g, "archetype": archetype, "lane": lane,
                "rationale": rationale, "red_flags": red_flags,
                "status": "new",
            })

    # Merge: existing (manually scored) + new (heuristic scored)
    all_scored = existing + rows

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_scored, f, indent=2)

    # Stats
    active = [r for r in all_scored if r["grade"] != "F"]
    grades = Counter(r["grade"] for r in active)
    lanes = Counter(r["lane"] for r in active)

    print(f"Total scored: {len(all_scored)} ({len(existing)} prior + {len(rows)} new)")
    print(f"Active (non-blacklisted): {len(active)}")
    print()
    print("Grade distribution:")
    for g in ["A", "B", "C", "D"]:
        print(f"  {g}: {grades.get(g, 0)}")
    print()
    print("Lane distribution:")
    for l in ["A", "B", "C"]:
        print(f"  Lane {l}: {lanes.get(l, 0)}")
    print()

    # Show top listings
    top = sorted([r for r in active if r["grade"] in ("A", "B")], key=lambda x: -x["weighted_score"])
    print(f"--- Top {min(30, len(top))} (A + B grades) ---")
    for r in top[:30]:
        print(f"{r['grade']} ({r['weighted_score']}) [{r['lane']}] | {r['title']} -- {r['company']} | {r['location']} | {r['salary']}")
        print(f"  {r['rationale']}")
        print()


if __name__ == "__main__":
    main()
