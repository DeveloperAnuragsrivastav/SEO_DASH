import asyncio
from sqlalchemy.orm import Session
from app.database import engine
from app.models.report_month import ReportMonth
from app.models.client import Client
from sqlalchemy import select
from app.services.pdf_service import generate_report_pdf

async def main():
    with Session(engine) as db:
        client = db.execute(select(Client).limit(1)).scalar_one()
        report = db.execute(select(ReportMonth).where(ReportMonth.client_id == client.id).limit(1)).scalar_one()
        
        report_data = {
            "id": str(report.id),
            "client_id": str(report.client_id),
            "month": report.month,
            "status": "published",
            "snapshot": report.snapshot,
            "narrative": report.narrative,
            "generated_at": report.generated_at,
            "published_at": report.published_at,
        }
        client_data = {
            "name": client.name,
            "domain": client.domain,
            "logo_url": client.logo_url,
        }
        print("Generating PDF...")
        pdf_bytes = await generate_report_pdf(report_data, client_data, "http://localhost:8000")
        print(f"Success! PDF bytes length: {len(pdf_bytes)}")
        with open('test_report.pdf', 'wb') as f:
            f.write(pdf_bytes)

asyncio.run(main())
