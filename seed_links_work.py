from __future__ import annotations
from app.database import SessionLocal
from app.models.client import Client
from app.models.link import Link
from app.models.activity import Activity
from app.models.screenshot import Screenshot
from app.models.report_month import ReportMonth
from app.models.enums import LinkStatus, ReportStatus
from sqlalchemy import select
from datetime import date
import uuid

def seed_data():
    db = SessionLocal()
    try:
        from app.models.enums import ClientStatus
        client = db.execute(select(Client).where(Client.status == ClientStatus.active)).scalars().first()
        if not client:
            print("No active client found. Cannot seed.")
            return

        target_month = date(2026, 8, 1)

        # Links
        links = [
            Link(client_id=client.id, created_on=date(2026, 8, 5), activity_type="Guest Post", domain="techblog.com", url="https://techblog.com/seo-trends", status=LinkStatus.active, dr=65),
            Link(client_id=client.id, created_on=date(2026, 8, 12), activity_type="Niche Edit", domain="localnews.org", url="https://localnews.org/businesses", status=LinkStatus.active, dr=40),
            Link(client_id=client.id, created_on=date(2026, 8, 18), activity_type="Guest Post", domain="marketinghub.net", url="https://marketinghub.net/agency-tips", status=LinkStatus.pending, dr=55),
        ]
        db.add_all(links)

        # Activities
        activities = [
            Activity(client_id=client.id, month=target_month, activity_type="Content Optimization", count=5, notes="Updated meta descriptions for top pages"),
            Activity(client_id=client.id, month=target_month, activity_type="Technical SEO", count=1, notes="Fixed canonical tags issue"),
            Activity(client_id=client.id, month=target_month, activity_type="Keyword Research", count=2, notes="Q4 campaign planning"),
        ]
        db.add_all(activities)

        # Create a mock screenshot file
        import os
        screenshots_dir = os.path.join(os.getcwd(), "app", "static", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        mock_filename = f"mock_{uuid.uuid4().hex[:8]}.png"
        mock_filepath = os.path.join(screenshots_dir, mock_filename)
        
        # Create a simple 10x10 transparent PNG or generic text
        # Since it's a mock, we'll just write a tiny valid webp/png or even a text file.
        # Let's write a tiny transparent GIF
        with open(mock_filepath, "wb") as f:
            f.write(b"GIF89a\\x01\\x00\\x01\\x00\\x80\\x00\\x00\\xff\\xff\\xff\\x00\\x00\\x00\\x21\\xf9\\x04\\x01\\x00\\x00\\x00\\x00\\x2c\\x00\\x00\\x00\\x00\\x01\\x00\\x01\\x00\\x00\\x02\\x02\\x44\\x01\\x00\\x3b")
        
        # Screenshots
        screenshots = [
            Screenshot(client_id=client.id, month=target_month, file_url=f"/static/screenshots/{mock_filename}", caption="GSC Performance Spikes", keyword_id=None),
        ]
        db.add_all(screenshots)

        # Next Month Plan (in ReportMonth)
        report = db.execute(select(ReportMonth).where(ReportMonth.client_id == client.id, ReportMonth.month == target_month)).scalar_one_or_none()
        if not report:
            report = ReportMonth(
                client_id=client.id,
                month=target_month,
                status=ReportStatus.draft,
                snapshot={"seeded": True},
                next_month_plan={"text": "1. Launch new blog campaign\n2. Build 5 high-DR backlinks\n3. Technical audit for mobile"}
            )
            db.add(report)
        else:
            report.next_month_plan = {"text": "1. Launch new blog campaign\n2. Build 5 high-DR backlinks\n3. Technical audit for mobile"}

        db.commit()
        print(f"Successfully seeded Links and Work Done for client {client.name} (ID: {client.id})")
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
