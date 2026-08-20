from __future__ import annotations
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from app.services.groq_service import generate_report_narrative

def test_groq():
    data = {
        "gsc": {"clicks": 100},
        "ga4": {"sessions": 200},
        "gbp": {"views": 50},
        "rankings": {"top3": 5}
    }
    prev_data = {
        "gsc": {"clicks": 80},
        "ga4": {"sessions": 150},
        "gbp": {"views": 40},
        "rankings": {"top3": 4}
    }
    
    print("Testing Groq Service narrative generation...")
    try:
        narrative = generate_report_narrative(
            client_name="Test Agency",
            month="August",
            snapshot_data=data
        )
        print(f"\nResult:\n{narrative}")
    except Exception as e:
        print(f"\nError: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response text: {e.response.text}")

if __name__ == "__main__":
    test_groq()
