with open("app/templates/report_pdf.html", "r") as f:
    content = f.read()

# Fix agency logo
agency_logo_old = '<div class="ez-logo"><img src="{{ base_url }}/static/agency_logo.png" alt="Agency Logo" /></div>'
agency_logo_new = '''<div class="ez-logo">
                    {% if agency_logo_b64 %}
                    <img src="{{ agency_logo_b64 }}" alt="Agency Logo" />
                    {% else %}
                    <img src="{{ base_url }}/static/agency_logo.png" alt="Agency Logo" />
                    {% endif %}
                </div>'''
content = content.replace(agency_logo_old, agency_logo_new)

# Fix client logo
client_logo_old = '<img src="{{ client_logo_url }}" class="client-logo" alt="Client Logo" />'
client_logo_new = '<img src="{% if client_logo_url.startswith(\'/\') %}{{ base_url }}{{ client_logo_url }}{% else %}{{ client_logo_url }}{% endif %}" class="client-logo" alt="Client Logo" />'
content = content.replace(client_logo_old, client_logo_new)

# Fix screenshots (one per page)
screenshots_old = '''                {% if screenshots and screenshots | length > 0 %}
                <div>
                    <h3 style="margin-bottom: 16px; font-size: 16px;">Screenshots & Evidence</h3>
                    <div class="evidence-grid">
                        {% for img in screenshots %}
                        <div class="evidence">
                            {% if img.base64_data %}
                                <img class="evidence-image" src="{{ img.base64_data }}" alt="Proof" />
                            {% else %}
                                <img class="evidence-image" src="{{ base_url }}{{ img.file_url }}" alt="Proof" />
                            {% endif %}
                            <small>{{ img.caption }}</small>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}'''

# Remove screenshots block from page-five
content = content.replace(screenshots_old, "")

# Append screenshots as new full pages
screenshots_new = '''
    <!-- Screenshot Pages -->
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
    {% endif %}
</body>
'''
content = content.replace("</body>", screenshots_new)

with open("app/templates/report_pdf.html", "w") as f:
    f.write(content)
