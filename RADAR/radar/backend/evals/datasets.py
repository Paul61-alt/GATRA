"""Eval datasets for each pipeline phase."""

# Mix easy (well-known) / medium (known but niche) / hard (small/recent).
PROBE_DOMAINS = [
    "linear.app",       # easy — well-documented, lots of press
    "pennylane.com",    # medium — French B2B SaaS, less English coverage
    "mistral.ai",       # medium — recent, AI space
    "cal.com",          # hard — small open-source startup, thin press coverage
]


# Well-known startups — easy to sanity-check outputs manually.
# No expected outputs: we use LLM-as-judge scoring.
UNDERSTAND_DOMAINS = [
    "linear.app",
    "notion.so",
    "mistral.ai",
    "figma.com",
    "vercel.com",
    "runway.ml",
    "alan.com",
    "pennylane.com",
]

DISCOVER_DOMAINS = [
    "linear.app",
    "notion.so",
    "mistral.ai",
    "figma.com",
]

# Hardcoded competitor stubs for ENRICH evals.
# Avoids running phases 1+2 just to test phase 3.
ENRICH_COMPETITORS = [
    {
        "name": "Asana",
        "website": "https://asana.com",
        "hq_city": "San Francisco",
        "hq_country": "United States",
        "founded_year": 2008,
        "funding_stage": "Public",
        "employee_count": "3000+",
        "one_liner": "Work management platform for teams.",
        "differentiator": "Broader workflow automation vs Linear.",
    },
    {
        "name": "ClickUp",
        "website": "https://clickup.com",
        "hq_city": "San Diego",
        "hq_country": "United States",
        "founded_year": 2017,
        "funding_stage": "Series C",
        "employee_count": "1000+",
        "one_liner": "All-in-one productivity platform.",
        "differentiator": "More features at lower price point.",
    },
    {
        "name": "Height",
        "website": "https://height.app",
        "hq_city": "San Francisco",
        "hq_country": "United States",
        "founded_year": 2019,
        "funding_stage": "Series A",
        "employee_count": "50-100",
        "one_liner": "Autonomous project management with AI.",
        "differentiator": "AI-native task management.",
    },
]
