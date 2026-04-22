# Scoring Prompt Template

Reference doc for the scoring logic used by `/pipeline`. The actual scoring happens inline in the SKILL.md instructions -- this doc exists for review and tuning.

## System Context (loaded once per batch)

The candidate's structured resume from `pipeline/data/resumes/source.json`.

## Per-Listing Evaluation

Score each listing across 10 weighted dimensions (1-5 each):

| Dimension | Weight | Question |
|-----------|--------|----------|
| Role match | 3x | Title + responsibilities align with experience? |
| Skills alignment | 3x | Required skills match what they've done? |
| Interview likelihood | 3x | Realistic shot at a screen? Consider title inflation, overqualification, exact-match hiring. |
| Seniority fit | 2x | Right level (not too junior, not requiring 20+ years)? |
| Compensation | 2x | Meets $100K+ floor? Competitive for the role? |
| Domain resonance | 2x | Industry/domain connects to experience (SaaS, marketplaces, AI, property, govt)? |
| Timeline/urgency | 2x | Recent posting? Likely to still be open? |
| Geographic fit | 1x | Seattle, remote, or hybrid-compatible? |
| Company stage | 1x | Reasonable company (not pre-revenue with 3 people, not massive corp)? |
| Growth trajectory | 1x | Career advancement potential? |

## Negative Factors (deduct from aggregate)

- Known layoff signals, poor Glassdoor (<3.0), CEO churn: -0.5 to -1.0
- Backfill red flags (fired mid-project language): -0.3
- Unicorn requirements (10 conflicting skills): -0.5

## Weighted Score Formula

```
(3*(role_match + skills_alignment + interview_likelihood)
 + 2*(seniority_fit + compensation + domain_resonance + timeline_urgency)
 + 1*(geographic_fit + company_stage + growth_trajectory)) / 20
 + negative_adjustment
```

## Grading Thresholds

- A: 4.0+
- B: 3.5-3.9
- C: 2.5-3.4
- D: 1.5-2.4
- F: below 1.5

## Output Per Listing (JSON)

```json
{
  "title": "Senior Product Manager",
  "company": "Acme Corp",
  "location": "Seattle",
  "salary": "$120-140K",
  "url": "https://...",
  "source": "Adzuna",
  "description": "...",
  "scores": {
    "role_match": 4,
    "skills_alignment": 3,
    "interview_likelihood": 4,
    "seniority_fit": 4,
    "compensation": 3,
    "domain_resonance": 3,
    "timeline_urgency": 4,
    "geographic_fit": 5,
    "company_stage": 3,
    "growth_trajectory": 3
  },
  "negative_adjustment": 0,
  "weighted_score": 3.7,
  "grade": "B",
  "archetype": "product_management",
  "rationale": "Strong PM fit. Roadmap ownership + platform experience align. Salary meets floor.",
  "red_flags": [],
  "status": "new"
}
```

## Archetype Assignment

Match listing title + description against archetype keywords in config.yaml. First match wins. Default: operations.

| Archetype | Typical titles |
|-----------|---------------|
| product_management | PM, Product Owner, AI PM, TPM |
| operations | Ops Manager, Program Manager, Chief of Staff, RevOps |
| government | City Manager, county/municipal roles, public sector |
| customer_success | CS, Account Manager, TAM, Solutions |
| ai_technical | AI/ML roles, Technical Advisor, Fractional |
