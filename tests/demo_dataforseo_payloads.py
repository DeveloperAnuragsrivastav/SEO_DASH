import json
from datetime import date

# ==========================================
# 1. NIGHTLY RANKINGS (SERP task_post)
# ==========================================

print("--- 1. NIGHTLY RANKINGS PULL (task_post) ---")
print("We use this to track where a keyword ranks and if an AI Overview is present.\n")

# HOW WE ARE SENDING (The Payload)
payload_rankings = [
    {
        "keyword": "seo agency",
        "location_code": 2840,           # 2840 = United States
        "language_code": "en",           # English
        "load_async_ai_overview": True,  # Critical: tells DataForSEO to scrape the AI box
        "tag": "client_uuid:keyword_uuid:2026-08-20", # Custom tracking tag
        "postback_url": "https://ezrankings.com/api/webhooks/dataforseo/serp"
    }
]

print("PAYLOAD WE SEND:")
print(json.dumps(payload_rankings, indent=2))

# HOW IT COMES (The Expected Response)
# Note: Because this is an ASYNC post, it just returns a Task ID. 
# The actual SERP data comes back to the postback_url later.
response_rankings = {
    "version": "0.1.20230215",
    "status_code": 20000,
    "status_message": "Ok.",
    "cost": 0.002,
    "tasks": [
        {
            "id": "10242023-1538-0066-0000-000000000000",
            "status_code": 20100,
            "status_message": "Task Created.",
            "data": {
                "keyword": "seo agency",
                "tag": "client_uuid:keyword_uuid:2026-08-20"
            }
        }
    ]
}

print("\nRAW OUTPUT IT RETURNS IMMEDIATELY:")
print(json.dumps(response_rankings, indent=2))
print("\n" + "="*50 + "\n")


# ==========================================
# 2. KEYWORD RESEARCH (Search Volume live)
# ==========================================

print("--- 2. KEYWORD RESEARCH (live) ---")
print("We use this when an admin types a new keyword to fetch its search volume instantly.\n")

# HOW WE ARE SENDING (The Payload)
payload_research = [
    {
        "keywords": ["seo agency"],
        "location_name": "United States",
        "language_name": "English"
    }
]

print("PAYLOAD WE SEND:")
print(json.dumps(payload_research, indent=2))

# HOW IT COMES (The Expected Response)
# Note: This is a synchronous (LIVE) call, so it returns all the volume data instantly.
response_research = {
    "version": "0.1.20230215",
    "status_code": 20000,
    "status_message": "Ok.",
    "cost": 0.005,
    "tasks": [
        {
            "id": "10242023-1538-0066-0000-000000000001",
            "status_code": 20000,
            "status_message": "Ok.",
            "result": [
                {
                    "keyword_info": {
                        "search_volume": 12100,
                        "cpc": 15.50,
                        "competition": 0.85,
                        "competition_level": "HIGH"
                    }
                }
            ]
        }
    ]
}

print("\nRAW OUTPUT IT RETURNS:")
print(json.dumps(response_research, indent=2))
