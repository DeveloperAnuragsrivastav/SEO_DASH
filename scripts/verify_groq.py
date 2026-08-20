from __future__ import annotations
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.groq_service import generate_report_narrative
import json

def verify_groq():
    print("\n--- Verifying Groq Narrative Generation ---\n")
    
    # 1. Check if GROQ_API_KEY is available
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Explicit Honest Statement: No real GROQ_API_KEY is available in the environment to verify Groq narrative generation. Thus, cannot test real call.")
        return
        
    # 2. Realistic snapshot data
    snapshot_data = {
        "gsc": {
            "clicks": 4500,
            "impressions": 120000,
            "ctr": 0.0375,
            "position": 12.4
        },
        "ga4": {
            "sessions": 5200,
            "conversions": 150,
            "revenue": 3450.00
        },
        "kpi_deltas": {
            "gsc": {
                "clicks": {"delta": 500, "pct": 12.5},
                "impressions": {"delta": 10000, "pct": 9.1}
            },
            "ga4": {
                "sessions": {"delta": 400, "pct": 8.3},
                "conversions": {"delta": -10, "pct": -6.2}
            }
        },
        "rankings": {
            "top_3": 15,
            "top_10": 42
        }
    }
    
    try:
        print("Calling Groq API with realistic snapshot data...")
        narrative = generate_report_narrative("Acme Corp", "August 2026", snapshot_data)
        
        print("\n--- Generated Narrative Output ---")
        print(narrative)
        print("----------------------------------\n")
    except Exception as e:
        print(f"Failed to generate narrative: {e}")

if __name__ == "__main__":
    verify_groq()
