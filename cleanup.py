from __future__ import annotations
from app.database import SessionLocal
from app.models.link import Link
from app.models.activity import Activity
from app.models.screenshot import Screenshot
from app.models.report_month import ReportMonth
from sqlalchemy import select
import os

db = SessionLocal()

try:
    # 1. Delete duplicates
    links = db.execute(select(Link).order_by(Link.created_on)).scalars().all()
    act = db.execute(select(Activity).order_by(Activity.activity_type)).scalars().all()

    if len(links) > 3:
        for l in links[3:]:
            db.delete(l)

    if len(act) > 3:
        for a in act[3:]:
            db.delete(a)

    # 2. Fix next_month_plan
    report = db.execute(select(ReportMonth)).scalars().first()
    if report and report.next_month_plan:
        # Use real newlines
        text = report.next_month_plan.get('text', '').replace('\\n', '\n')
        report.next_month_plan = {'text': text}

    # 3. Create a real visible mock image (a blue square)
    screenshots_dir = os.path.join(os.getcwd(), 'app', 'static', 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    screenshot = db.execute(select(Screenshot)).scalars().first()
    if screenshot:
        filename = screenshot.file_url.split('/')[-1]
        filepath = os.path.join(screenshots_dir, filename)
        # 10x10 blue square in PNG format
        blue_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x02\x00\x00\x00\x02PX\xea\x00\x00\x00\x01sRGB\x00\xae\xce\x1c\xe9\x00\x00\x00\x16IDAT\x18Wc\xfc\xcf\x80\x1f\x00\x06\x04\x02\x01\x81T\xc3V\x00\x00\x00\x00IEND\xaeB`\x82'
        with open(filepath, 'wb') as f:
            f.write(blue_png)

    db.commit()
    print('Cleanup and fix complete.')
except Exception as e:
    db.rollback()
    print('Error:', e)
finally:
    db.close()
