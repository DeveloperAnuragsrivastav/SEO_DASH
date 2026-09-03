from __future__ import annotations
import json
from app.config import settings
import httpx

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

def extract_mention_and_citations(raw_response: str, client_domain: str, client_name: str) -> dict:
    """
    Analyzes a raw LLM response using OpenAI to determine if a client was mentioned
    and extract any cited pages.
    """
    openai_api_key = settings.OPENAI_API_KEY
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in configuration.")

    prompt_text = f"""
You are an expert SEO data analyst. Your job is to analyze an AI model's response to a search prompt and determine if a specific brand or domain was mentioned or cited.

Brand Name: {client_name}
Brand Domain: {client_domain}

Here is the raw text of the AI model's response:
---
{raw_response}
---

Task:
1. Determine if the brand name or the brand domain was mentioned anywhere in the response text. Set "mentioned" to true or false.
2. If the brand domain was mentioned in the form of specific URLs (citations or links), extract them. For each unique URL belonging to the brand domain, count how many times it appeared.
3. Output the result STRICTLY as a valid JSON object with the following schema, and NO OTHER TEXT or markdown formatting.

Schema:
{{
  "mentioned": boolean,
  "cited_pages": [
    {{"page": "url_string", "prompt_count": integer}}
  ]
}}

If there are no cited pages, "cited_pages" should be an empty list [].
"""

    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You output only valid JSON."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(OPENAI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        try:
            parsed = json.loads(content)
            return {
                "mentioned": parsed.get("mentioned", False),
                "cited_pages": parsed.get("cited_pages", [])
            }
        except json.JSONDecodeError:
            # Fallback if the LLM hallucinated non-JSON
            return {
                "mentioned": False,
                "cited_pages": []
            }


def generate_report_narrative(client_name: str, month: str, snapshot_data: dict) -> str:
    """
    Generates a draft narrative for the monthly SEO report using OpenAI.
    """
    openai_api_key = settings.OPENAI_API_KEY
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in configuration.")

    # Strip out large lists (pages, screenshots, keywords) to keep payload small
    minimal_data = {
        "gsc": {k: v for k, v in (snapshot_data.get("gsc") or {}).items() if k not in ["top_pages", "top_queries", "devices"]},
        "ga4": {k: v for k, v in (snapshot_data.get("ga4") or {}).items() if k not in ["top_pages", "traffic_sources", "devices", "countries"]},
        "gbp": snapshot_data.get("gbp", {}),
        "rankings_summary": snapshot_data.get("rankings", {}).get("summary", {}),
        "ai_visibility": {
            "total_prompts": len(snapshot_data.get("ai_visibility", [])),
            "mentioned": sum(1 for m in snapshot_data.get("ai_visibility", []) if m.get("mentioned"))
        },
        "links_built": len(snapshot_data.get("links", [])),
        "kpi_deltas": snapshot_data.get("kpi_deltas", {})
    }

    prompt_text = f"""
You are an expert SEO data analyst. Write a professional, client-facing draft executive summary (1 paragraph, max 100 words) for {client_name}'s {month} SEO performance.

Use the following snapshot data:
{json.dumps(minimal_data, indent=2, default=str)}

Guidelines:
- Highlight the most positive KPIs (e.g., increased clicks, improved rankings).
- If traffic or rankings dropped, frame it constructively (e.g., "identifying areas for growth").
- Do not invent metrics; only use the provided snapshot data.
- Tone: Professional, reassuring, and data-driven.
- Output ONLY the paragraph text. Do not include greetings, sign-offs, or Markdown formatting.
"""

    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You write concise, professional executive summaries."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.4
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(OPENAI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        return content.strip()
