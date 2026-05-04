#!/usr/bin/env python3
"""Apply manual review corrections to scored JSON."""
import json
from pathlib import Path

OUT_PATH = Path("pipeline/data/scored/2026-04-22.json")

with open(OUT_PATH) as f:
    data = json.load(f)

def find(company_substr, title_substr):
    """Find listings matching company and title substrings."""
    matches = []
    for i, r in enumerate(data):
        if company_substr.lower() in r["company"].lower() and title_substr.lower() in r["title"].lower():
            matches.append(i)
    return matches

def recompute(r):
    """Recompute weighted score from dimensions."""
    s = r["scores"]
    raw = (3*(s["transferable_skills"] + s["hiring_accessibility"] + s["interview_likelihood"])
           + 2*(s["compensation"] + s["geographic_fit"] + s["timeline_urgency"])
           + 1*(s["role_match"] + s["seniority_fit"] + s["company_quality"] + s["growth_potential"])) / 19
    ws = round(raw + r["negative_adjustment"], 2)
    r["weighted_score"] = ws
    if ws >= 4.0: r["grade"] = "A"
    elif ws >= 3.5: r["grade"] = "B"
    elif ws >= 2.5: r["grade"] = "C"
    elif ws >= 1.5: r["grade"] = "D"
    else: r["grade"] = "F"

corrections = 0

# --- UPGRADES ---

# Brex Marketing Ops (x2): ts 2->3
for idx in find("brex", "marketing operations"):
    data[idx]["scores"]["transferable_skills"] = 3
    data[idx]["rationale"] = "Skills-transfer role. Marketing ops at B2B fintech requires cross-functional coordination, data/analytics, process design. Thinner talent pool for PM-background pivot."
    recompute(data[idx])
    corrections += 1
    print(f"  Upgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# Qualtrics Product Ops Lead: ts 1->4
for idx in find("qualtrics", "product operations"):
    data[idx]["scores"]["transferable_skills"] = 4
    data[idx]["rationale"] = "Product operations is extremely PM-adjacent. Process design, delivery cadence, tooling, cross-functional coordination. Strong fit."
    recompute(data[idx])
    corrections += 1
    print(f"  Upgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# CBRE Sr Property Manager: ts 1->4, rm 2->4
for idx in find("cbre", "property manager"):
    data[idx]["scores"]["transferable_skills"] = 4
    data[idx]["scores"]["role_match"] = 4
    data[idx]["rationale"] = "Sr Property Manager at CBRE. Jared co-founded a property management business (HPM). Direct experience match, not a stretch. Thin talent pool for PM-background candidates with actual property mgmt experience."
    recompute(data[idx])
    corrections += 1
    print(f"  Upgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# Dura Digital Sr Project Manager: ts 2->4
for idx in find("dura digital", "project manager"):
    data[idx]["scores"]["transferable_skills"] = 4
    data[idx]["rationale"] = "Technical PM with AI implementations and Agile. Maps directly to PM + AI agent building experience. Small firm, accessible hiring."
    recompute(data[idx])
    corrections += 1
    print(f"  Upgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# LVT Principal PM: ts 1->3
for idx in find("lvt", "product manager"):
    data[idx]["scores"]["transferable_skills"] = 3
    data[idx]["rationale"] = "AI-driven site intelligence platform. IoT + AI product. Platform PM role at growth startup."
    recompute(data[idx])
    corrections += 1
    print(f"  Upgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# --- DOWNGRADES ---

# Nscale People Ops Manager: il 4->2, rm 3->1
for idx in find("nscale", "people operations"):
    data[idx]["scores"]["interview_likelihood"] = 2
    data[idx]["scores"]["role_match"] = 1
    data[idx]["rationale"] = "People Operations = HR (hiring, onboarding, employee experience). Not a skills transfer from PM background."
    recompute(data[idx])
    corrections += 1
    print(f"  Downgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# DigitalOcean Solutions Architect AI/ML: il 4->1, ha 4->2
for idx in find("digitalocean", "solutions architect"):
    data[idx]["scores"]["interview_likelihood"] = 1
    data[idx]["scores"]["hiring_accessibility"] = 2
    data[idx]["rationale"] = "Deeply technical hands-on engineering role. Requires building ML pipelines or managing K8s clusters. Not a PM pivot."
    data[idx]["red_flags"] = ["Requires hands-on engineering"]
    recompute(data[idx])
    corrections += 1
    print(f"  Downgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# APN Consulting Technical PM: add staffing penalty
for idx in find("apn consulting", "project manager"):
    data[idx]["scores"]["hiring_accessibility"] = 2
    data[idx]["negative_adjustment"] = -0.3
    data[idx]["rationale"] = "IT staffing firm contract role. Intermediary, limited growth."
    data[idx]["red_flags"] = ["Staffing agency contract"]
    recompute(data[idx])
    corrections += 1
    print(f"  Downgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")
# Also check if company name is "Bellevue, WA" (the weird one)
for idx in find("bellevue", "technical project manager"):
    if data[idx]["company"].strip() == "Bellevue, WA":
        data[idx]["scores"]["hiring_accessibility"] = 2
        data[idx]["negative_adjustment"] = -0.3
        data[idx]["rationale"] = "APN Consulting staffing firm. IT contract role. Intermediary."
        data[idx]["red_flags"] = ["Staffing agency contract"]
        recompute(data[idx])
        corrections += 1
        print(f"  Downgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# HVAC Controls PM: il 4->1
for idx in find("trane", "hvac"):
    data[idx]["scores"]["interview_likelihood"] = 1
    data[idx]["rationale"] = "HVAC Controls PM. Very specialized domain requiring HVAC technical experience. HM wants domain expertise."
    data[idx]["red_flags"] = ["Specialized HVAC domain"]
    recompute(data[idx])
    corrections += 1
    print(f"  Downgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

# US Tech Solutions Workplace PM: staffing penalty
for idx in find("us tech solutions", "workplace"):
    data[idx]["scores"]["hiring_accessibility"] = 2
    data[idx]["negative_adjustment"] = -0.3
    data[idx]["rationale"] = "Staffing firm, 7-month contract. Corporate real estate program management. Contract limits growth."
    data[idx]["red_flags"] = ["Staffing agency", "7-month contract"]
    recompute(data[idx])
    corrections += 1
    print(f"  Downgraded: {data[idx]['title']} -- {data[idx]['company']} -> {data[idx]['grade']} ({data[idx]['weighted_score']})")

print(f"\nApplied {corrections} corrections.")

with open(OUT_PATH, "w") as f:
    json.dump(data, f, indent=2)

# Final grade distribution
from collections import Counter
active = [r for r in data if r["grade"] != "F"]
grades = Counter(r["grade"] for r in active)
print("\nUpdated grade distribution:")
for g in ["A", "B", "C", "D"]:
    print(f"  {g}: {grades.get(g, 0)}")

# Show updated A+B
print("\n--- Updated A + B grades ---")
top = sorted([r for r in active if r["grade"] in ("A","B")], key=lambda x: -x["weighted_score"])
for r in top:
    print(f"{r['grade']} ({r['weighted_score']}) [{r['lane']}] | {r['title']} -- {r['company']} | {r['salary']}")
    print(f"  {r['rationale']}")
    print()
