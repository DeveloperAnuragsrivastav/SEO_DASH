from __future__ import annotations
from app.database import SessionLocal
from app.models.link import Link
from app.models.activity import Activity
from app.models.screenshot import Screenshot
from sqlalchemy import select
import os

db = SessionLocal()

try:
    # 1. Clean up links duplicates
    links = db.execute(select(Link)).scalars().all()
    seen_links = set()
    for l in links:
        key = (l.domain, l.url, l.activity_type)
        if key in seen_links:
            db.delete(l)
        else:
            seen_links.add(key)

    # 2. Clean up activities duplicates
    activities = db.execute(select(Activity)).scalars().all()
    seen_activities = set()
    for a in activities:
        key = (a.activity_type, a.count, a.notes)
        if key in seen_activities:
            db.delete(a)
        else:
            seen_activities.add(key)
    
    # 3. Add back the missing Technical SEO activity if it's completely gone
    technical_exists = False
    for a in activities:
        if a.activity_type == "Technical SEO":
            technical_exists = True
            break
            
    if not technical_exists:
        client_id = activities[0].client_id if activities else None
        target_month = activities[0].month if activities else None
        if client_id and target_month:
            db.add(Activity(client_id=client_id, month=target_month, activity_type="Technical SEO", count=1, notes="Fixed canonical tags issue"))

    # 4. Fix the screenshot mock
    screenshots_dir = os.path.join(os.getcwd(), 'app', 'static', 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    screenshot = db.execute(select(Screenshot)).scalars().first()
    if screenshot:
        filename = screenshot.file_url.split('/')[-1]
        filepath = os.path.join(screenshots_dir, filename)
        
        # 10x10 blue square in PNG format properly defined
        # Need to use built-in bytes.fromhex or proper byte string
        hex_str = "89504E470D0A1A0A0000000D494844520000000A0000000A0802000000025058EA000000017352474200AECE1CE90000001649444154185763FCCF801F00060402018154C3560000000049454E44AE426082"
        with open(filepath, 'wb') as f:
            f.write(bytes.fromhex(hex_str))

    db.commit()
    print('Cleanup and fix complete.')
except Exception as e:
    db.rollback()
    print('Error:', e)
finally:
    db.close()
