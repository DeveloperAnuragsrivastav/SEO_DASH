import re

with open("app/routes/reports.py", "r") as f:
    content = f.read()

# Add Request to FastAPI imports if not there
if "from fastapi import " in content and "Request" not in content:
    content = content.replace("from fastapi import APIRouter", "from fastapi import APIRouter, Request")

# Update /multi/pdf
multi_pdf_old = """@router.get("/multi/pdf")
async def download_report_pdf(client_id: uuid.UUID, count: int = 1, snapshot_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):"""
multi_pdf_new = """@router.get("/multi/pdf")
async def download_report_pdf(request: Request, client_id: uuid.UUID, count: int = 1, snapshot_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):"""
content = content.replace(multi_pdf_old, multi_pdf_new)

# Update /multi/pdf base_url
base_url_old = """    from app.config import settings
    base_url = settings.webhook_base_url"""
base_url_new = """    base_url = str(request.base_url).rstrip("/")
    
    # Inject base64 screenshots directly to avoid Playwright network issues
    import base64
    for img in comparative_data.get("screenshots", []):
        file_url = img.get("file_url")
        if file_url:
            parts = file_url.split("/")
            if len(parts) >= 5 and parts[-1] == "image":
                sid = parts[-2]
                s_obj = db.execute(select(Screenshot).where(Screenshot.id == sid)).scalar_one_or_none()
                if s_obj and s_obj.file_data:
                    b64 = base64.b64encode(s_obj.file_data).decode("utf-8")
                    img["base64_data"] = f"data:{s_obj.mime_type or 'image/png'};base64,{b64}"
"""
# Replace ONLY the first occurrence (for /multi/pdf)
content = content.replace(base_url_old, base_url_new, 1)


# Update /{snapshot_id}/pdf
single_pdf_old = """@router.get("/{snapshot_id}/pdf")
async def download_single_report_pdf(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):"""
single_pdf_new = """@router.get("/{snapshot_id}/pdf")
async def download_single_report_pdf(request: Request, client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):"""
content = content.replace(single_pdf_old, single_pdf_new)

content = content.replace(base_url_old, base_url_new, 1)

with open("app/routes/reports.py", "w") as f:
    f.write(content)
