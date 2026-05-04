#!/usr/bin/env python3
"""Rescore calibration batch with pivot-optimized scoring system."""
import csv
import json
from pathlib import Path
from collections import Counter

CSV_PATH = Path("pipeline/data/listings/2026-04-22-deduped.csv")
OUT_PATH = Path("pipeline/data/scored/2026-04-22.json")

# New scoring dimensions (v2 - pivot-optimized):
# (transferable_skills, hiring_accessibility, interview_likelihood,
#  compensation, geographic_fit, timeline_urgency,
#  role_match, seniority_fit, company_quality, growth_potential,
#  negative_adj, archetype, lane, rationale, red_flags)
#
# Weights: 3x(ts,ha,il) + 2x(comp,geo,time) + 1x(rm,sf,cq,gp) / 19
#
# Lane: A = PM-adjacent tech, B = skills-transfer, C = discovery

SCORES = {
    # 0: Robert Half - Sr PM - ERP manufacturing - King County ~$126K
    # Transferable: process design, cross-functional, stakeholder mgmt used in ERP transformation
    # Hiring access: staffing firm posting, less competitive than direct big-co PM
    # Interview: ERP/manufacturing specialty limits fit, but staffing firms are less picky
    0:  (3,3,3, 2,4,4, 3,3,3,2, 0, "operations", "A", "ERP manufacturing PM via Robert Half. Transferable ops skills but specialized domain.", []),

    # 1: Boeing - Sr PM Specialist - AI/analytics - Seattle ~$194K
    # Transferable: data/analytics, cross-functional, product strategy all apply
    # Hiring access: defense/aerospace PM hiring is less saturated than consumer tech PM
    # Interview: Boeing hires methodically, AI group may value hands-on AI experience
    1:  (4,3,3, 4,4,4, 4,3,4,3, 0, "ai_technical", "A", "AI/analytics PM in Boeing defense group. AI experience differentiates. Defense hiring is slower but less saturated.", []),

    # 2: Deloitte - PM Accelsior Suite - Finance ~$159K
    # Transferable: stakeholder mgmt, process design, cross-functional
    # Hiring access: consulting firms have rigid hiring pipelines, hard to break in laterally
    # Interview: finance transformation specialty, consulting background expected
    2:  (3,2,2, 3,4,4, 3,3,4,2, 0, "operations", "A", "Finance consulting PM at Deloitte. Rigid consulting hiring pipeline, finance domain mismatch.", []),

    # 3: Amazon - Principal PM Tech DynamoDB - BLACKLISTED
    3:  (0,0,0, 0,0,0, 0,0,0,0, 0, "product_management", "A", "BLACKLISTED: Amazon", []),

    # 4: Amazon - Sr PM Tech Ring - BLACKLISTED
    4:  (0,0,0, 0,0,0, 0,0,0,0, 0, "product_management", "A", "BLACKLISTED: Amazon", []),

    # 5: Amazon - Principal PM Amazon Now - BLACKLISTED
    5:  (0,0,0, 0,0,0, 0,0,0,0, 0, "operations", "A", "BLACKLISTED: Amazon", []),

    # 6: Google - Director PM Databases Spanner - Kirkland ~$339K
    # Hiring access: Director at Google = extremely competitive, ageism risk at FAANG
    # Seniority: Director is a stretch AND overqualification paradox (too senior for some, not Google-senior enough)
    6:  (3,1,1, 5,5,4, 3,2,5,4, -0.5, "product_management", "A", "Director PM at Google. FAANG Director bar extremely high, oversaturated talent pool.", ["FAANG hiring bar", "Director level stretch"]),

    # 7: Accenture - AI Native FDE PM ~$257K
    # Transferable: AI, data, cross-functional leadership
    # Hiring access: consulting firm but AI-native role is newer category, less rigid
    # Interview: AI experience is a genuine differentiator here
    7:  (4,3,4, 5,4,4, 4,4,4,3, 0, "ai_technical", "A", "AI Native PM at Accenture. AI hands-on experience is a real differentiator for this role.", []),

    # 8: Meta - PM generic ~$113K
    # Hiring access: FAANG PM = most oversaturated talent pool on earth
    8:  (3,1,1, 2,4,3, 3,3,5,3, -0.5, "product_management", "A", "Generic Meta PM. FAANG PM pool is oversaturated, low listed comp, likely stale.", ["FAANG oversaturation", "Possibly stale"]),

    # 9: Seattle Bank - PM - $105-130K
    # Hiring access: small local bank, far less competitive, may value breadth
    # Interview: smaller company, less structured process, more likely to talk to you
    9:  (3,4,4, 2,5,4, 4,3,2,2, 0, "product_management", "A", "PM at small Seattle bank. API/cloud core. Less competitive, bank may value PM breadth. Low comp.", []),

    # 10: Triplenet/ORCA - PM - $201K
    # Transferable: multi-stakeholder, process, cross-functional across 7 agencies
    # Hiring access: government/transit PM is a very thin talent pool
    # Lane: could be A or B (government adjacent)
    10: (4,4,3, 4,5,4, 4,3,3,2, 0, "government", "B", "PM for ORCA transit fare system. Government-adjacent, thin talent pool. Multi-agency stakeholder management.", []),

    # 11: Filson - PM - $90-120K
    # Hiring access: retail brand, PM talent pool is smaller here
    # Comp: may cross below $100K floor
    11: (2,3,3, 1,5,4, 3,3,3,2, 0, "product_management", "A", "PM at Filson retail. Salary may be below $100K floor. Retail domain.", ["Salary may be below $100K"]),

    # 12: Orkes - PM - $150-180K
    # Transferable: orchestration, developer tools, API — very close to his actual building experience
    # Hiring access: startup, developer tools niche, less saturated
    # Interview: startup PM hire, values breadth and hands-on technical ability
    12: (4,4,4, 3,5,3, 4,3,3,4, 0, "product_management", "A", "PM at Orkes (Conductor OSS). Startup, developer tools. His hands-on orchestration/AI agent work is directly relevant.", []),

    # 13: Avante - PM - $155K
    # Transferable: AI product, analytics, B2B SaaS
    # Hiring access: early startup, AI-native, values builders over polished PM resumes
    # Interview: startup likely cares more about ability than pedigree
    13: (4,4,4, 3,5,4, 4,3,3,4, 0, "ai_technical", "A", "AI-native benefits intelligence startup. Early stage, values builders. AI product experience maps directly.", []),

    # 14: DAT - PM - $135-188K
    # Transferable: B2B SaaS, data marketplace, cross-functional
    # Hiring access: logistics SaaS is less trendy, thinner PM talent pool
    14: (3,3,3, 3,5,4, 4,3,4,3, 0, "product_management", "A", "PM at DAT, B2B SaaS logistics marketplace. Established 45yr company, less competitive PM hire.", []),

    # 15: NexHealth - PM - $200-275K
    # Transferable: API architecture, platform, integrations — strong alignment
    # Hiring access: healthcare infra startup, looking for platform PM, less saturated than generic PM
    # Interview: API/platform experience at Knock directly maps
    15: (4,4,4, 4,5,4, 4,3,3,4, 0, "product_management", "A", "Healthcare infra API platform. Knock's API ecosystem experience maps directly. Growth startup.", []),

    # 16: Carbon Robotics - PM - $125-145K
    # Transferable: cross-functional, product roadmap, but hardware/agtech specific
    # Hiring access: robotics PM is niche, less competitive
    # Interview: hardware PM specialty is a barrier
    16: (2,3,2, 2,5,4, 3,3,3,3, 0, "product_management", "A", "PM at Carbon Robotics agtech. Hardware/robotics specialty. Niche but domain mismatch.", []),

    # 17: Amazon - Sr PM Global Logistics - BLACKLISTED
    17: (0,0,0, 0,0,0, 0,0,0,0, 0, "operations", "A", "BLACKLISTED: Amazon", []),

    # 18: Amazon - Principal PM Tech Prime Video - BLACKLISTED
    18: (0,0,0, 0,0,0, 0,0,0,0, 0, "product_management", "A", "BLACKLISTED: Amazon", []),

    # 19: Google - Sr PM AI Infra GPU - Kirkland ~$214K
    # Hiring access: FAANG, but AI infra is a thinner specialty pool
    # Interview: GPU hardware specialty is a barrier, FAANG bar
    19: (3,2,2, 4,5,4, 4,3,5,4, -0.3, "ai_technical", "A", "AI Infra GPU PM at Google. FAANG bar + GPU hardware specialty. AI experience helps but not enough.", ["FAANG hiring bar", "GPU hardware specialty"]),

    # 20: Deloitte - PM Product Engineering ~$160K
    # Same consulting pipeline issues
    20: (3,2,2, 3,4,4, 3,3,4,2, 0, "product_management", "A", "Consulting PM at Deloitte. Rigid hiring pipeline, generic posting.", []),

    # 21: Success Matcher - AI PM (first PM hire) - $136K
    # Transferable: AI, customer analytics, B2B SaaS — perfect alignment
    # Hiring access: FIRST PM hire at startup. They want a builder, not a title-matcher. This is the sweet spot.
    # Interview: co-founder handoff, they want someone who can own everything. Very high likelihood.
    21: (5,5,5, 2,5,4, 5,4,3,5, 0, "ai_technical", "A", "First PM hire at AI analytics startup. Co-founder handoff. Builder mindset valued over pedigree. Best possible interview dynamics.", []),

    # 22: Curative AI - Sr PM - Bellevue ~$164K
    # Hiring access: healthcare AI startup, less competitive, values AI hands-on
    22: (4,4,3, 3,5,4, 4,4,3,4, 0, "ai_technical", "A", "Healthcare AI startup, break-even year one. AI SaaS fit, startup environment.", []),

    # 23: Curative AI - Principal PM - Bellevue ~$192K
    23: (4,4,3, 4,5,4, 4,4,3,4, 0, "ai_technical", "A", "Principal PM at same Curative AI. Higher seniority, better comp.", []),

    # 24: TekWissen - PM III - staffing agency ~$162K
    24: (3,2,3, 3,5,4, 3,3,2,2, -0.5, "product_management", "A", "Contract PM via staffing agency. Limited growth, intermediary.", ["Staffing agency contract"]),

    # 25: Hardware PM - Seattle - $80-146K
    # Complete mismatch - requires biomedical/mechanical engineering
    25: (1,2,1, 1,5,4, 2,2,2,2, 0, "operations", "C", "Hardware PM requiring biomedical/mechanical engineering. Complete skills mismatch.", []),

    # 26: Meta - Director PM - Bellevue ~$150K
    # FAANG Director = worst possible intersection of oversaturated + ageism risk + seniority stretch
    26: (3,1,1, 3,5,3, 4,2,5,4, -0.5, "product_management", "A", "Director PM at Meta. FAANG Director = oversaturated, ageism risk, seniority stretch.", ["FAANG oversaturation", "Director stretch"]),

    # 27: Cengage - Director PM ~$155K
    # EdTech, Director level, but not FAANG — less competitive
    # Hiring access: EdTech PM is less saturated than consumer tech
    27: (3,3,2, 3,3,4, 4,2,4,3, -0.3, "product_management", "A", "Director PM at Cengage EdTech. Less competitive than FAANG but Director stretch.", ["Director stretch"]),

    # 28: Meta - PM Leadership - Bellevue ~$133K
    28: (3,1,1, 2,5,3, 4,3,5,4, -0.5, "product_management", "A", "PM Leadership at Meta. FAANG PM oversaturation.", ["FAANG oversaturation"]),

    # 29: CPRS - AI PM - Bellevue $185-210K
    # Transferable: AI roadmap, enterprise stakeholder mgmt, data-driven decisions
    # Hiring access: enterprise AI PM is newer category, less saturated
    # Interview: AI hands-on experience is a genuine differentiator
    29: (5,4,4, 4,5,4, 5,4,3,4, 0, "ai_technical", "A", "Enterprise AI PM. Owns AI roadmap + value realization. AI experience is a real differentiator here.", []),

    # 30: F5 - Sr PM - Seattle $150-224K
    # Hiring access: cybersecurity PM is a niche, less saturated
    30: (3,3,3, 3,5,3, 4,4,4,3, 0, "product_management", "A", "Sr PM at F5 cybersecurity. Niche domain, less competitive PM pool.", []),

    # 31: F5 - Principal PM - Seattle $179-269K
    31: (3,3,3, 4,5,4, 4,4,4,3, 0, "product_management", "A", "Principal PM at F5. Higher seniority + comp. Cybersecurity niche.", []),

    # 32: Meta - PM Retail ~$113K
    32: (2,1,1, 2,4,3, 3,3,5,3, -0.5, "product_management", "A", "Retail PM at Meta. FAANG oversaturation + retail specialty.", ["FAANG oversaturation"]),

    # 33: Disney - Sr PM - Seattle ~$167K
    # Transferable: video/streaming/media — direct MediaPlatform alignment
    # Hiring access: entertainment PM is less saturated than general tech PM
    # Interview: video/media domain expertise is a genuine differentiator
    33: (4,3,3, 3,5,3, 4,4,5,3, 0, "product_management", "A", "Sr PM at Disney streaming. Video/media domain maps to MediaPlatform. Entertainment PM is less saturated.", []),

    # 34: Cengage - Principal PM ~$124K
    34: (3,3,3, 2,3,4, 4,4,4,3, 0, "product_management", "A", "Principal PM at Cengage EdTech. Right seniority but low comp.", []),

    # 35: DigitalOcean - Sr PM - Seattle ~$279K
    # Transferable: cloud platform, developer tools, infra
    # Hiring access: cloud PM is competitive but less than FAANG consumer
    # Interview: platform/infra experience maps well
    35: (4,3,4, 5,5,4, 4,4,4,4, 0, "product_management", "A", "Sr PM at DigitalOcean cloud platform. Developer tools focus, strong platform PM alignment.", []),

    # 36: PEMCO - Digital PM - Seattle $137-167K
    # Transferable: digital transformation, process design
    # Hiring access: insurance PM = very thin talent pool, less competitive
    # Interview: insurance company may value cross-functional PM experience
    36: (3,4,3, 3,5,4, 3,3,3,2, 0, "product_management", "A", "Digital PM at PEMCO insurance. Thin talent pool for insurance PM. Domain mismatch but accessible.", []),

    # 37: Synchrony - AVP PM ~$146K
    # Financial services, unclear geography
    37: (3,2,2, 3,3,4, 3,3,4,3, 0, "product_management", "A", "AVP PM at Synchrony financial services. Payments/merchant focus.", []),

    # 38: T-Mobile - Sr PM - Bellevue ~$176K
    # Hiring access: telecom PM is less saturated than pure tech PM
    38: (3,3,3, 4,5,4, 4,3,5,3, 0, "product_management", "A", "Sr PM at T-Mobile Bellevue. Large company, telecom domain. Less competitive than FAANG.", []),

    # 39: SEKO Logistics - PM - Chicago ~$145K
    # Geographic miss (Chicago)
    39: (3,2,2, 3,1,4, 3,3,3,2, 0, "operations", "B", "PM at SEKO Logistics in Chicago. Geographic miss.", []),

    # 40: Cargill - Advisor PM - Minneapolis ~$111K
    # Geographic miss, agriculture domain
    40: (2,2,2, 2,1,4, 3,3,4,2, 0, "product_management", "A", "Advisor PM at Cargill agriculture in Minneapolis. Geographic + domain miss.", []),

    # 41: Capital One - Manager PM - Richmond VA ~$196K
    # Geographic miss, financial services
    41: (3,2,2, 4,1,4, 4,3,5,3, 0, "product_management", "A", "Manager PM at Capital One in Richmond VA. Geographic miss.", []),

    # 42: Capital One - Director PM - Richmond VA ~$203K
    42: (3,2,1, 4,1,4, 4,2,5,4, -0.3, "product_management", "A", "Director PM at Capital One Richmond VA. Geographic miss + Director stretch.", ["Director stretch"]),

    # 43: Kroger - PM - Cincinnati ~$144K
    43: (2,2,2, 3,1,4, 3,3,4,2, 0, "product_management", "A", "PM at Kroger pricing in Cincinnati. Geographic + domain miss.", []),

    # 44: Cleo - PM - Remote? ~$170K
    # B2B integration platform, may be remote
    44: (3,3,3, 3,3,4, 4,3,3,3, 0, "product_management", "A", "PM at Cleo B2B integration. Possibly remote. Decent SaaS fit.", []),

    # 45: Fiserv - PM - Atlanta ~$142K
    45: (3,2,2, 3,1,4, 3,3,4,3, 0, "product_management", "A", "PM at Fiserv fintech in Atlanta. Geographic miss.", []),

    # 46: NBC Universal - PM - LA ~$415K
    # Strong domain fit (video/media) but LA
    # Hiring access: entertainment PM is less competitive
    46: (4,3,3, 5,1,3, 4,3,5,3, 0, "product_management", "A", "PM at NBCUniversal media/entertainment. Strong video/media domain fit but LA location.", []),

    # 47: Generac - PM - Nebraska ~$124K
    # Hardware product (light towers), complete mismatch
    47: (1,2,1, 2,1,4, 2,3,4,2, 0, "operations", "C", "PM for light tower hardware in Nebraska. Complete mismatch.", []),

    # 48: Xylem - PM - Auburn NY ~$163K
    # Water/industrial, complete mismatch
    48: (1,2,1, 3,1,4, 2,3,4,2, 0, "operations", "C", "PM for water/industrial products in NY. Complete mismatch.", []),

    # 49: Expedia - Sr PM - Seattle $173-243K
    # Transferable: platform, marketplace, data
    # Hiring access: Expedia PM is competitive but less than FAANG
    49: (4,3,3, 4,5,4, 4,4,5,3, 0, "product_management", "A", "Sr PM at Expedia Seattle. Travel marketplace, platform/data alignment. Less competitive than FAANG.", []),
}

def compute_weighted(s):
    ts, ha, il, comp, geo, time, rm, sf, cq, gp, neg = s[:11]
    if ts == 0 and ha == 0:  # blacklisted
        return 0.0
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
            g = grade(ws)

            # Blacklisted companies get grade F
            if "BLACKLISTED" in s[13]:
                g = "F"
                ws = 0.0

            rows.append({
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "salary": row["salary"],
                "url": row["url"],
                "source": row["source"],
                "description": row["description"],
                "scores": {
                    "transferable_skills": s[0],
                    "hiring_accessibility": s[1],
                    "interview_likelihood": s[2],
                    "compensation": s[3],
                    "geographic_fit": s[4],
                    "timeline_urgency": s[5],
                    "role_match": s[6],
                    "seniority_fit": s[7],
                    "company_quality": s[8],
                    "growth_potential": s[9],
                },
                "negative_adjustment": s[10],
                "weighted_score": ws,
                "grade": g,
                "archetype": s[11],
                "lane": s[12],
                "rationale": s[13],
                "red_flags": s[14],
                "status": "new",
            })

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    # Print grade distribution (excluding blacklisted)
    active = [r for r in rows if r["grade"] != "F"]
    grades = Counter(r["grade"] for r in active)
    print(f"Scored {len(active)} active listings ({len(rows) - len(active)} blacklisted)")
    for g in ["A", "B", "C", "D"]:
        print(f"  {g}: {grades.get(g, 0)}")

    # Print all A and B grades sorted by score
    print("\n--- A + B Grade Listings ---")
    top = sorted([r for r in active if r["grade"] in ("A", "B")], key=lambda x: -x["weighted_score"])
    for r in top:
        print(f"{r['grade']} ({r['weighted_score']}) [{r['lane']}] | {r['title']} -- {r['company']} | {r['location']} | {r['salary']}")
        print(f"  {r['rationale']}")
        print()

if __name__ == "__main__":
    main()
