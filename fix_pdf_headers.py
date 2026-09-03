import re

with open("app/templates/report_pdf.html", "r") as f:
    content = f.read()

# AI Visibility
content = re.sub(
    r'<th style="padding:8px 0;">Keyword</th>\s*<th style="padding:8px 0;">Platform</th>\s*<th style="padding:8px 0;text-align:right;">Mentioned\?</th>',
    r'<th style="padding:8px 0;width:70px;">Month</th>\n                                <th style="padding:8px 0;">Keyword</th>\n                                <th style="padding:8px 0;">Platform</th>\n                                <th style="padding:8px 0;text-align:right;">Mentioned?</th>',
    content
)

# Links
content = re.sub(
    r'<th style="padding:8px 0;">Live URL</th>\s*<th style="padding:8px 0;">Target Domain</th>\s*<th style="padding:8px 0;text-align:right;">DR</th>',
    r'<th style="padding:8px 0;width:70px;">Month</th>\n                                <th style="padding:8px 0;">Live URL</th>\n                                <th style="padding:8px 0;">Target Domain</th>\n                                <th style="padding:8px 0;text-align:right;">DR</th>',
    content
)

with open("app/templates/report_pdf.html", "w") as f:
    f.write(content)
