import os
import sys

os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@postgres:5432/ez_rankings"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models.user import User
from app.models.client import Client
from app.models.user_project import UserProjectAssignment
from app.models.report_snapshot import ReportSnapshot

def clear_reports():
    db = SessionLocal()
    user = db.query(User).filter(User.email == 'i@gmail.com').first()
    if not user:
        print("User not found.")
        return

    # Find clients this user has access to
    user_projects = db.query(UserProjectAssignment).filter(UserProjectAssignment.user_id == user.id).all()
    if not user_projects:
        print("User has no associated clients.")
        return
        
    for up in user_projects:
        client_id = up.client_id
        client = db.query(Client).filter(Client.id == client_id).first()
        if client:
            reports = db.query(ReportSnapshot).filter(ReportSnapshot.client_id == client_id).all()
            print(f"Deleting {len(reports)} reports for client {client.name} (ID: {client_id})")
            for r in reports:
                db.delete(r)
                
    db.commit()
    print("Done!")

if __name__ == '__main__':
    clear_reports()
