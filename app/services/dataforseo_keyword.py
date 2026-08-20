from __future__ import annotations
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def fetch_keyword_metrics_with_retry(login: str, password: str, term: str, location_name: str = "United States", language_name: str = "English") -> dict:
    url = "https://api.dataforseo.com/v3/keywords_data/google/search_volume/live"
    payload = [
        {
            "keywords": [term],
            "location_name": location_name,
            "language_name": language_name
        }
    ]
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, auth=(login, password), json=payload)
        response.raise_for_status()
        
        data = response.json()
        if data.get("status_code") == 20000:
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                results = tasks[0]["result"]
                if results and results[0].get("keyword_info"):
                    info = results[0]["keyword_info"]
                    return {
                        "search_volume": info.get("search_volume"),
                        "cpc": info.get("cpc"),
                        "competition": info.get("competition"),
                        "cost": data.get("cost", 0.0)
                    }
        
        raise Exception(f"DataForSEO error: {data.get('status_message', 'Unknown error')}")
