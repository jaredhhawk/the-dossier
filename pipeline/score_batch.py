#!/usr/bin/env python3
"""One-time scoring helper for calibration batch of 50 listings."""
import csv
import json
import sys
from pathlib import Path

CSV_PATH = Path("pipeline/data/listings/2026-04-22-deduped.csv")
OUT_PATH = Path("pipeline/data/scored/2026-04-22.json")

# Scoring data for first 50 listings (0-indexed row from CSV)
# Format: (role_match, skills_alignment, interview_likelihood, seniority_fit,
#           compensation, domain_resonance, timeline_urgency, geographic_fit,
#           company_stage, growth_trajectory, negative_adj, archetype, rationale, red_flags)
SCORES = {
    0:  (3,2,2, 4,2,1,4, 4,3,2, 0, "operations", "ERP manufacturing PM. Domain mismatch with software/AI background.", []),
    1:  (4,4,3, 4,4,3,4, 4,4,3, 0, "product_management", "AI/analytics PM in Boeing defense group. Good data+AI alignment.", []),
    2:  (3,2,2, 3,3,1,4, 4,4,2, 0, "operations", "Finance consulting PM at Deloitte. Domain mismatch.", []),
    3:  (4,3,3, 4,5,3,4, 4,5,4, 0, "product_management", "Principal PM Tech for DynamoDB. Strong platform PM role, database specialty is a stretch.", []),
    4:  (3,2,3, 4,4,2,4, 5,5,3, 0, "product_management", "Sr PM Tech for Ring/smart home. Hardware/IoT focus doesn't align.", []),
    5:  (4,3,3, 4,5,3,4, 5,5,4, 0, "operations", "Principal PM for Amazon Now ultra-fast delivery. Operations-heavy, good cross-functional scope.", []),
    6:  (3,3,2, 3,5,3,4, 5,5,4, -0.3, "product_management", "Director PM for Spanner databases at Google. Seniority stretch + database specialty.", ["Director level stretch"]),
    7:  (4,4,3, 4,5,4,4, 4,4,3, 0, "ai_technical", "AI Native PM at Accenture. Strong AI/data alignment, consulting context.", []),
    8:  (3,3,2, 3,2,3,3, 4,5,3, 0, "product_management", "Generic Meta PM posting. No specifics, low listed salary, likely stale.", ["Possibly stale posting"]),
    9:  (4,3,4, 3,2,2,4, 5,2,2, 0, "product_management", "PM at small Seattle bank. API/cloud-core focus is interesting but low comp and limited scale.", []),
    10: (4,3,3, 3,4,2,4, 5,3,2, 0, "government", "PM for ORCA transit fare system. Multi-agency stakeholder management, government-adjacent.", []),
    11: (3,2,3, 3,1,1,4, 5,3,2, 0, "product_management", "PM at Filson retail. Low salary range crosses below $100K floor. Domain mismatch.", ["Salary may be below $100K"]),
    12: (4,4,4, 3,3,4,3, 5,3,4, 0, "product_management", "PM at Orkes (Conductor OSS). Developer tools + orchestration engine directly maps to technical PM background.", []),
    13: (4,4,4, 3,3,3,4, 5,3,4, 0, "ai_technical", "PM at Avante, AI-native benefits intelligence platform. Startup, AI product, B2B SaaS.", []),
    14: (4,3,3, 3,3,3,4, 5,4,3, 0, "product_management", "PM at DAT, B2B SaaS logistics marketplace. Established company, decent Seattle PM role.", []),
    15: (4,4,4, 3,4,3,4, 5,3,4, 0, "product_management", "PM at NexHealth, healthcare infra layer. API/platform focus aligns well with API architecture experience.", []),
    16: (3,2,2, 3,2,1,4, 5,3,3, 0, "ai_technical", "PM at Carbon Robotics. Computer vision/agtech. Domain mismatch, low comp.", []),
    17: (4,3,3, 4,5,2,4, 5,5,4, 0, "operations", "Sr PM for Amazon Global Logistics exports. Operations-heavy, supply chain focus.", []),
    18: (5,4,3, 4,5,5,4, 4,5,4, 0, "product_management", "Principal PM Tech for Prime Video. Direct alignment with MediaPlatform video/streaming experience.", []),
    19: (4,4,2, 4,4,4,4, 5,5,4, -0.3, "ai_technical", "Sr PM for AI Infra GPU at Google. Strong AI fit but GPU hardware specialty may be a stretch.", ["GPU hardware specialty"]),
    20: (3,3,2, 3,3,2,4, 4,4,2, 0, "product_management", "PM Product Engineering at Deloitte consulting. Generic consulting PM.", []),
    21: (5,5,4, 4,2,5,4, 5,3,5, 0, "ai_technical", "First PM hire at AI startup. AI customer analytics, B2B SaaS. High autonomy, strong narrative fit.", []),
    22: (4,4,3, 4,3,3,4, 5,3,4, 0, "ai_technical", "Sr PM at Curative AI. Healthcare AI startup, break-even in year one. AI SaaS fit.", []),
    23: (4,4,3, 5,4,3,4, 5,3,4, 0, "ai_technical", "Principal PM at Curative AI. Same company, higher seniority. AI healthcare SaaS.", []),
    24: (3,3,3, 3,3,2,4, 5,2,2, -0.5, "product_management", "PM III via TekWissen staffing agency. Contract/staffing role, limited growth.", ["Staffing agency contract"]),
    25: (2,1,1, 3,1,1,4, 5,2,2, 0, "operations", "Hardware PM. Requires biomedical/mechanical engineering background. Complete mismatch.", []),
    26: (4,3,2, 3,3,3,3, 5,5,4, -0.3, "product_management", "Director PM at Meta. Seniority stretch for Director level at FAANG.", ["Director level stretch"]),
    27: (4,3,2, 3,3,2,4, 3,4,3, -0.3, "product_management", "Director PM at Cengage EdTech. Seniority stretch, lower comp for Director.", ["Director level stretch"]),
    28: (4,3,2, 4,2,3,3, 5,5,4, 0, "product_management", "PM Leadership role at Meta. Listed comp seems low, likely base only.", []),
    29: (5,4,4, 4,4,4,4, 5,3,4, 0, "ai_technical", "AI PM at CPRS, enterprise AI roadmap owner. Strong AI+enterprise PM fit.", []),
    30: (4,3,3, 4,3,2,3, 5,4,3, 0, "product_management", "Sr PM at F5 Networks cybersecurity. Tech company but networking/security domain.", []),
    31: (4,3,3, 5,4,2,4, 5,4,3, 0, "product_management", "Principal PM at F5. Higher seniority, better comp than Sr PM posting.", []),
    32: (3,2,2, 3,2,1,3, 4,5,3, 0, "product_management", "PM Retail focus at Meta. Retail domain mismatch, low listed comp.", []),
    33: (4,4,3, 4,3,5,3, 5,5,3, 0, "product_management", "Sr PM at Disney streaming. Video/media domain directly maps to MediaPlatform experience.", []),
    34: (4,3,3, 5,2,2,4, 3,4,3, 0, "product_management", "Principal PM at Cengage EdTech. Right seniority but low comp and EdTech domain.", []),
    35: (4,4,4, 4,5,4,4, 5,4,4, 0, "product_management", "Sr PM at DigitalOcean. Cloud platform, developer tools, strong tech PM fit.", []),
    36: (3,2,3, 3,3,1,4, 5,3,2, 0, "product_management", "Digital PM at PEMCO insurance. Domain mismatch, local Seattle company.", []),
    37: (3,3,2, 4,3,2,4, 3,4,3, 0, "product_management", "AVP PM at Synchrony financial services. Payments/merchant focus, geographic unclear.", []),
    38: (4,3,3, 4,4,2,4, 5,5,3, 0, "product_management", "Sr PM at T-Mobile Bellevue. Large tech company, telecom domain.", []),
    39: (3,2,2, 3,3,2,4, 1,3,2, 0, "operations", "PM at SEKO Logistics in Chicago. Geographic miss, logistics domain.", []),
    40: (3,2,2, 3,2,1,4, 1,4,2, 0, "product_management", "Advisor PM at Cargill agriculture in Minneapolis. Geographic + domain miss.", []),
    41: (4,3,3, 3,4,2,4, 1,5,3, 0, "product_management", "Manager PM at Capital One in Richmond VA. Geographic miss.", []),
    42: (4,3,2, 3,4,2,4, 1,5,4, -0.3, "product_management", "Director PM at Capital One in Richmond VA. Geographic miss + seniority stretch.", ["Director level stretch"]),
    43: (3,2,2, 3,3,1,4, 1,4,2, 0, "product_management", "PM at Kroger pricing strategy in Cincinnati. Geographic + domain miss.", []),
    44: (4,3,3, 3,3,3,4, 3,3,3, 0, "product_management", "PM at Cleo B2B integration platform. Remote-friendly, decent SaaS fit.", []),
    45: (3,3,2, 3,3,2,4, 1,4,3, 0, "product_management", "PM at Fiserv fintech in Atlanta. Geographic miss.", []),
    46: (4,4,3, 3,5,5,3, 1,5,3, 0, "product_management", "PM at NBC Universal media/entertainment. Strong domain fit (video/media) but LA location.", []),
    47: (2,1,1, 3,2,1,4, 1,4,2, 0, "operations", "PM for light tower hardware at Generac in Nebraska. Complete mismatch.", []),
    48: (2,1,1, 3,3,1,4, 1,4,2, 0, "operations", "PM for water/industrial products at Xylem in NY. Complete mismatch.", []),
    49: (4,4,3, 4,4,3,4, 5,5,3, 0, "product_management", "Sr PM at Expedia Seattle. Travel marketplace, strong platform/data alignment.", []),
}

def compute_weighted(s):
    rm, sa, il, sf, co, dr, tu, gf, cs, gt, neg = s[:11]
    raw = (3*(rm + sa + il) + 2*(sf + co + dr + tu) + 1*(gf + cs + gt)) / 20
    return round(raw + neg, 2)

def grade(ws):
    if ws >= 4.0: return "A"
    if ws >= 3.5: return "B"
    if ws >= 2.5: return "C"
    if ws >= 1.5: return "D"
    return "F"

def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 50:
                break
            if i not in SCORES:
                continue
            s = SCORES[i]
            ws = compute_weighted(s)
            rows.append({
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "salary": row["salary"],
                "url": row["url"],
                "source": row["source"],
                "description": row["description"],
                "scores": {
                    "role_match": s[0],
                    "skills_alignment": s[1],
                    "interview_likelihood": s[2],
                    "seniority_fit": s[3],
                    "compensation": s[4],
                    "domain_resonance": s[5],
                    "timeline_urgency": s[6],
                    "geographic_fit": s[7],
                    "company_stage": s[8],
                    "growth_trajectory": s[9],
                },
                "negative_adjustment": s[10],
                "weighted_score": ws,
                "grade": grade(ws),
                "archetype": s[11],
                "rationale": s[12],
                "red_flags": s[13],
                "status": "new",
            })

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    # Print grade distribution
    from collections import Counter
    grades = Counter(r["grade"] for r in rows)
    print(f"Scored {len(rows)} listings")
    for g in ["A", "B", "C", "D", "F"]:
        print(f"  {g}: {grades.get(g, 0)}")

if __name__ == "__main__":
    main()
