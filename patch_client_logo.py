import re

with open("app/routes/reports.py", "r") as f:
    content = f.read()

# For /multi/pdf
multi_old = """    client_data = {
        "name": client.name,
        "domain": client.domain,
        "logo_url": client.logo_url,
        "theme_color": client.theme_color,
    }"""
    
multi_new = """    client_logo_url = client.logo_url
    client_logo_b64 = ""
    if client_logo_url and client_logo_url.strip():
        import httpx
        import base64
        fetch_url = base_url + client_logo_url if client_logo_url.startswith("/") else client_logo_url
        try:
            with httpx.Client(timeout=5.0) as c:
                resp = c.get(fetch_url)
                if resp.status_code == 200:
                    b64 = base64.b64encode(resp.content).decode("utf-8")
                    ctype = resp.headers.get("content-type", "image/png")
                    client_logo_b64 = f"data:{ctype};base64,{b64}"
        except Exception:
            pass

    client_data = {
        "name": client.name,
        "domain": client.domain,
        "logo_url": client.logo_url,
        "logo_b64": client_logo_b64,
        "theme_color": client.theme_color,
    }"""
content = content.replace(multi_old, multi_new)

with open("app/routes/reports.py", "w") as f:
    f.write(content)

with open("app/services/pdf_service.py", "r") as f:
    content = f.read()

logo_path_old = """        logo_path = os.path.join(os.getcwd(), "app", "static", "agency_logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:"""
logo_path_new = """        from pathlib import Path
        logo_path = Path(__file__).resolve().parent.parent / "static" / "agency_logo.png"
        if logo_path.exists():
            with open(logo_path, "rb") as image_file:"""
content = content.replace(logo_path_old, logo_path_new)

client_logo_old = 'client_logo_url=client.get("logo_url", ""),'
client_logo_new = 'client_logo_url=client.get("logo_url", ""),\n        client_logo_b64=client.get("logo_b64", ""), '
content = content.replace(client_logo_old, client_logo_new)

with open("app/services/pdf_service.py", "w") as f:
    f.write(content)

with open("app/templates/report_pdf.html", "r") as f:
    content = f.read()
    
brandline_old = """                {% if client_logo_url %}
                <img src="{% if client_logo_url.startswith('/') %}{{ base_url }}{{ client_logo_url }}{% else %}{{ client_logo_url }}{% endif %}" class="client-logo" alt="Client Logo" />
                {% else %}
                <div class="brand-mark">{{ client_name[:1] | upper }}</div>
                {% endif %}"""
brandline_new = """                {% if client_logo_b64 %}
                <img src="{{ client_logo_b64 }}" class="client-logo" alt="Client Logo" />
                {% else %}
                <div class="brand-mark">{{ client_name[:1] | upper }}</div>
                {% endif %}"""
content = content.replace(brandline_old, brandline_new)

with open("app/templates/report_pdf.html", "w") as f:
    f.write(content)

