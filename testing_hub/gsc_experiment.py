import os
import json
import datetime
import sys
from dateutil.relativedelta import relativedelta
# Ensure the parent directory is in sys.path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Do not use load_dotenv('.env') because it contains an invalid placeholder DATABASE_URL.
import os
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@postgres:5432/ez_rankings"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(__file__), '..', 'google_credentials.json')


from app.database import SessionLocal
from app.models.connection import Connection
from app.services.gsc_service import pull_gsc_data

def run_experiment():
    db = SessionLocal()
    # Find any active GSC connection
    conn = db.query(Connection).filter(Connection.provider == 'gsc', Connection.status == 'connected').first()
    
    if not conn:
        print("No connected GSC client found.")
        return

    m1_start = datetime.date(2026, 7, 25)
    m1_end = datetime.date(2026, 8, 25)
    print(f"Pulling GSC data: {m1_start} to {m1_end}")
    
    try:
        data = pull_gsc_data(db, conn.id, m1_start, m1_end)
        
        output = {
            "property": conn.property_id,
            "period": f"{m1_start} to {m1_end}",
            "totals": data["totals"],
            "top_pages": data.get("top_pages", [])[:5],
            "top_queries": data.get("top_queries", [])[:5]
        }
        
        output_path = os.path.join(os.path.dirname(__file__), 'gsc_experiment_results.json')
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=4)
            
        print(f"Experiment finished! Results written to {output_path}")
        print(json.dumps(output, indent=4))
    except Exception as e:
        print(f"Error pulling data: {e}")
        
    print(f"Experiment finished! Results written to {output_path}")

if __name__ == '__main__':
    run_experiment()
