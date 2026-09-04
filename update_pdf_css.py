with open("app/templates/report_pdf.html", "r") as f:
    content = f.read()

import re

# Add @page rule to styles
if "@page" not in content:
    content = content.replace("        html {", "        @page {\n            size: A4;\n            margin: 0;\n        }\n\n        html {")

# Modify .report-page
old_report_page = """        .report-page {
            width: 794px;
            min-height: 1123px;
            margin: 24px auto;
            position: relative;
            overflow: hidden;
            background: var(--paper);
            box-shadow: 0 12px 42px rgba(0, 0, 0, .14);
            page-break-after: always;
        }"""
new_report_page = """        .report-page {
            position: relative;
            background: var(--paper);
            page-break-after: always;
            break-after: page;
        }"""
content = content.replace(old_report_page, new_report_page)

# Update page inner padding to be the page margins
old_page_inner = """        .page-inner {
            padding: 55px 54px 48px;
        }"""
new_page_inner = """        .page-inner {
            padding: 40px 48px;
        }"""
content = content.replace(old_page_inner, new_page_inner)

# Apply break-inside: avoid to various components
components = [".card", ".metric-grid", ".chart-shelf", ".signal-bars", ".rate-bars", ".links-layout", ".ai-grid", ".delivery-layout"]
for comp in components:
    old_comp_start = f"        {comp} {{"
    if old_comp_start in content:
        # Avoid double adding
        if "page-break-inside: avoid;" not in content.split(old_comp_start)[1].split("}")[0]:
            content = content.replace(old_comp_start, f"        {comp} {{\n            page-break-inside: avoid;\n            break-inside: avoid;")
            
# Make metric-grid dynamic
old_metric_grid = """        .metric-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-top: 24px;
        }"""
new_metric_grid = """        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px;
            margin-top: 24px;
            page-break-inside: avoid;
            break-inside: avoid;
        }"""
content = content.replace(old_metric_grid, new_metric_grid)

old_perf_grid = """        .performance-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }"""
new_perf_grid = """        .performance-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px;
            page-break-inside: avoid;
            break-inside: avoid;
        }"""
content = content.replace(old_perf_grid, new_perf_grid)

# Also avoid breaks in sections
old_section = """        .section-heading {"""
new_section = """        .section-heading {
            page-break-after: avoid;
            break-after: avoid;"""
content = content.replace(old_section, new_section)

old_table = """        table {"""
new_table = """        table {
            page-break-inside: auto;
        }
        tr {
            page-break-inside: avoid;
            page-break-after: auto;"""
content = content.replace(old_table, new_table)

# Screenshots: the user wants max 2 images per page.
# Previously I had them in individual `<section class="report-page">`.
# I should put them in a layout that fits exactly 2 per page, or use CSS to force a page break every 2 items.
screenshots_old = """    <!-- Screenshot Pages -->
    {% if screenshots and screenshots | length > 0 %}
    {% for img in screenshots %}
    <section class="report-page" style="display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px; text-align: center;">
        <h3 style="align-self: flex-start; margin-bottom: 24px; font-size: 18px;">Evidence: {{ img.caption or 'Screenshot' }}</h3>
        {% if img.base64_data %}
            <img src="{{ img.base64_data }}" alt="Proof" style="max-width: 100%; max-height: 850px; object-fit: contain; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-radius: 4px;" />
        {% else %}
            <img src="{% if img.file_url.startswith('/') %}{{ base_url }}{{ img.file_url }}{% else %}{{ img.file_url }}{% endif %}" alt="Proof" style="max-width: 100%; max-height: 850px; object-fit: contain; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-radius: 4px;" />
        {% endif %}
    </section>
    {% endfor %}
    {% endif %}"""

screenshots_new = """    <!-- Screenshot Pages -->
    {% if screenshots and screenshots | length > 0 %}
    <section class="report-page">
        <div class="page-inner">
            <h2 class="section-heading" style="margin-bottom: 20px;">Screenshots & Evidence</h2>
            <div style="display: grid; grid-template-columns: 1fr; gap: 40px;">
                {% for img in screenshots %}
                <div style="page-break-inside: avoid; break-inside: avoid; display: flex; flex-direction: column; align-items: center; {% if loop.index0 > 0 and loop.index0 % 2 == 0 %}page-break-before: always; break-before: always; padding-top: 40px;{% endif %}">
                    {% if img.base64_data %}
                        <img src="{{ img.base64_data }}" alt="Proof" style="max-width: 100%; max-height: 400px; object-fit: contain; box-shadow: 0 4px 12px rgba(0,0,0,0.15); border-radius: 8px;" />
                    {% else %}
                        <img src="{% if img.file_url.startswith('/') %}{{ base_url }}{{ img.file_url }}{% else %}{{ img.file_url }}{% endif %}" alt="Proof" style="max-width: 100%; max-height: 400px; object-fit: contain; box-shadow: 0 4px 12px rgba(0,0,0,0.15); border-radius: 8px;" />
                    {% endif %}
                    <small style="margin-top: 12px; font-size: 13px; color: var(--muted); font-weight: 500;">{{ img.caption or 'Evidence' }}</small>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>
    {% endif %}"""

if "<!-- Screenshot Pages -->" in content:
    content = content.replace(screenshots_old, screenshots_new)
else:
    print("Could not find screenshots block")

with open("app/templates/report_pdf.html", "w") as f:
    f.write(content)
