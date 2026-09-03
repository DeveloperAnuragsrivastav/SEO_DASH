import re

with open("app/templates/report_pdf.html", "r") as f:
    content = f.read()

# Replace GA4 Traffic Sources
ts_pattern = r"""(<th style="padding:8px 0;">Source / Medium</th>.*?<tbody>).*?({%\s*if ga4_traffic_sources\s*%}.*?{%\s*for s in ga4_traffic_sources\s*%}\s*<tr[^>]*>).*?(<td[^>]*>{{ s.source }}</td>\s*<td[^>]*>{{ s.sessions \| fmt }}</td>\s*<td[^>]*>{{ s.users \| fmt }}</td>\s*<td[^>]*>{{ s.conversions \| fmt }}</td>\s*</tr>\s*{%\s*endfor\s*%})\s*{%\s*else\s*%}\s*<tr><td[^>]*>No traffic sources available</td></tr>\s*{%\s*endif\s*%}"""
content = re.sub(
    r'<th style="padding:8px 0;">Source / Medium</th>\s*<th style="text-align:right;padding:8px 6px;">Sessions</th>\s*<th style="text-align:right;padding:8px 6px;">Users</th>\s*<th style="text-align:right;padding:8px 0;">Conversions</th>\s*</tr>\s*</thead>\s*<tbody>\s*{% if ga4_traffic_sources %}\s*{% for s in ga4_traffic_sources %}\s*<tr[^>]*>\s*<td[^>]*>{{ s.source }}</td>\s*<td[^>]*>{{ s.sessions \| fmt }}</td>\s*<td[^>]*>{{ s.users \| fmt }}</td>\s*<td[^>]*>{{ s.conversions \| fmt }}</td>\s*</tr>\s*{% endfor %}\s*{% else %}\s*<tr><td colspan="4"[^>]*>No traffic sources available</td></tr>\s*{% endif %}',
    r'''<th style="padding:8px 0;width:90px;">Month</th>
                            <th style="padding:8px 0;">Source / Medium</th>
                            <th style="text-align:right;padding:8px 6px;">Sessions</th>
                            <th style="text-align:right;padding:8px 6px;">Users</th>
                            <th style="text-align:right;padding:8px 0;">Conversions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% set ts_dict = ga4.get("traffic_sources", {}) %}
                        {% set ns = namespace(found=false) %}
                        {% for month in months|reverse %}
                            {% for s in ts_dict.get(month, []) %}
                            {% set ns.found = true %}
                            <tr style="border-bottom:1px solid var(--line-2, #eee);">
                                <td style="padding:6px 0;color:var(--muted);font-size:10px;">{{ month }}</td>
                                <td style="padding:6px 0;font-weight:600;">{{ s.source }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);font-weight:600;">{{ s.sessions | fmt }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);">{{ s.users | fmt }}</td>
                                <td style="text-align:right;padding:6px 0;font-family:var(--mono);">{{ s.conversions | fmt }}</td>
                            </tr>
                            {% endfor %}
                        {% endfor %}
                        {% if not ns.found %}
                            <tr><td colspan="5" style="text-align:center;padding:24px 0;color:var(--muted);">No traffic sources available</td></tr>
                        {% endif %}''', content
)

# Top Landing Pages GA4
content = re.sub(
    r'<th style="padding:8px 0;">Page Path</th>\s*<th style="text-align:right;padding:8px 6px;">Sessions</th>\s*<th style="text-align:right;padding:8px 6px;">Users</th>\s*<th style="text-align:right;padding:8px 0;">Conversions</th>\s*</tr>\s*</thead>\s*<tbody>\s*{% if ga4_top_pages %}\s*{% for p in ga4_top_pages %}\s*<tr[^>]*>\s*<td[^>]*>{{ p.page }}</td>\s*<td[^>]*>{{ p.sessions \| fmt }}</td>\s*<td[^>]*>{{ p.users \| fmt }}</td>\s*<td[^>]*>{{ p.conversions \| fmt }}</td>\s*</tr>\s*{% endfor %}\s*{% else %}\s*<tr><td colspan="4"[^>]*>No landing pages available</td></tr>\s*{% endif %}',
    r'''<th style="padding:8px 0;width:90px;">Month</th>
                            <th style="padding:8px 0;">Page Path</th>
                            <th style="text-align:right;padding:8px 6px;">Sessions</th>
                            <th style="text-align:right;padding:8px 6px;">Users</th>
                            <th style="text-align:right;padding:8px 0;">Conversions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% set ts_dict = ga4.get("top_pages", {}) %}
                        {% set ns = namespace(found=false) %}
                        {% for month in months|reverse %}
                            {% for p in ts_dict.get(month, []) %}
                            {% set ns.found = true %}
                            <tr style="border-bottom:1px solid var(--line-2, #eee);">
                                <td style="padding:6px 0;color:var(--muted);font-size:10px;">{{ month }}</td>
                                <td style="padding:6px 0;max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--brand, #2563eb);">{{ p.page }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);font-weight:600;">{{ p.sessions | fmt }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);">{{ p.users | fmt }}</td>
                                <td style="text-align:right;padding:6px 0;font-family:var(--mono);">{{ p.conversions | fmt }}</td>
                            </tr>
                            {% endfor %}
                        {% endfor %}
                        {% if not ns.found %}
                            <tr><td colspan="5" style="text-align:center;padding:24px 0;color:var(--muted);">No landing pages available</td></tr>
                        {% endif %}''', content
)

# Countries GA4
content = re.sub(
    r'<th style="padding:8px 0;">Country</th>\s*<th style="text-align:right;padding:8px 6px;">Sessions</th>\s*<th style="text-align:right;padding:8px 0;">Users</th>\s*</tr>\s*</thead>\s*<tbody>\s*{% if ga4_countries %}\s*{% for c in ga4_countries %}\s*<tr[^>]*>\s*<td[^>]*>{{ c.country }}</td>\s*<td[^>]*>{{ c.sessions \| fmt }}</td>\s*<td[^>]*>{{ c.users \| fmt }}</td>\s*</tr>\s*{% endfor %}\s*{% else %}\s*<tr><td colspan="3"[^>]*>No country data available</td></tr>\s*{% endif %}',
    r'''<th style="padding:8px 0;width:90px;">Month</th>
                            <th style="padding:8px 0;">Country</th>
                            <th style="text-align:right;padding:8px 6px;">Sessions</th>
                            <th style="text-align:right;padding:8px 0;">Users</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% set ts_dict = ga4.get("countries", {}) %}
                        {% set ns = namespace(found=false) %}
                        {% for month in months|reverse %}
                            {% for c in ts_dict.get(month, []) %}
                            {% set ns.found = true %}
                            <tr style="border-bottom:1px solid var(--line-2, #eee);">
                                <td style="padding:6px 0;color:var(--muted);font-size:10px;">{{ month }}</td>
                                <td style="padding:6px 0;font-weight:600;">{{ c.country }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);font-weight:600;">{{ c.sessions | fmt }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);">{{ c.users | fmt }}</td>
                            </tr>
                            {% endfor %}
                        {% endfor %}
                        {% if not ns.found %}
                            <tr><td colspan="4" style="text-align:center;padding:24px 0;color:var(--muted);">No country data available</td></tr>
                        {% endif %}''', content
)


# Top Queries GSC
content = re.sub(
    r'<th style="padding:8px 0;">Search Query</th>\s*<th style="text-align:right;padding:8px 6px;">Clicks</th>\s*<th style="text-align:right;padding:8px 6px;">Impr.</th>\s*<th style="text-align:right;padding:8px 6px;">CTR</th>\s*<th style="text-align:right;padding:8px 0;">Avg. Pos</th>\s*</tr>\s*</thead>\s*<tbody>\s*{% if gsc_top_queries %}\s*{% for q in gsc_top_queries %}\s*<tr[^>]*>\s*<td[^>]*>{{ q.query }}</td>\s*<td[^>]*>{{ q.clicks \| fmt }}</td>\s*<td[^>]*>{{ q.impressions \| fmt }}</td>\s*<td[^>]*>{{ q.ctr }}%</td>\s*<td[^>]*>{{ q.position }}</td>\s*</tr>\s*{% endfor %}\s*{% else %}\s*<tr><td colspan="5"[^>]*>No search console data available</td></tr>\s*{% endif %}',
    r'''<th style="padding:8px 0;width:90px;">Month</th>
                            <th style="padding:8px 0;">Search Query</th>
                            <th style="text-align:right;padding:8px 6px;">Clicks</th>
                            <th style="text-align:right;padding:8px 6px;">Impr.</th>
                            <th style="text-align:right;padding:8px 6px;">CTR</th>
                            <th style="text-align:right;padding:8px 0;">Avg. Pos</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% set ts_dict = gsc.get("top_queries", {}) %}
                        {% set ns = namespace(found=false) %}
                        {% for month in months|reverse %}
                            {% for q in ts_dict.get(month, []) %}
                            {% set ns.found = true %}
                            <tr style="border-bottom:1px solid var(--line-2, #eee);">
                                <td style="padding:6px 0;color:var(--muted);font-size:10px;">{{ month }}</td>
                                <td style="padding:6px 0;font-weight:600;">{{ q.query }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);font-weight:600;">{{ q.clicks | fmt }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);">{{ q.impressions | fmt }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);">{{ q.ctr }}%</td>
                                <td style="text-align:right;padding:6px 0;font-family:var(--mono);">{{ q.position }}</td>
                            </tr>
                            {% endfor %}
                        {% endfor %}
                        {% if not ns.found %}
                            <tr><td colspan="6" style="text-align:center;padding:24px 0;color:var(--muted);">No search console data available</td></tr>
                        {% endif %}''', content
)

# Top Pages GSC
content = re.sub(
    r'<th style="padding:8px 0;">Page Path</th>\s*<th style="text-align:right;padding:8px 6px;">Clicks</th>\s*<th style="text-align:right;padding:8px 6px;">Impr.</th>\s*<th style="text-align:right;padding:8px 6px;">CTR</th>\s*<th style="text-align:right;padding:8px 0;">Avg. Pos</th>\s*</tr>\s*</thead>\s*<tbody>\s*{% if gsc_top_pages %}\s*{% for p in gsc_top_pages %}\s*<tr[^>]*>\s*<td[^>]*>{{ p.page }}</td>\s*<td[^>]*>{{ p.clicks \| fmt }}</td>\s*<td[^>]*>{{ p.impressions \| fmt }}</td>\s*<td[^>]*>{{ p.ctr }}%</td>\s*<td[^>]*>{{ p.position }}</td>\s*</tr>\s*{% endfor %}\s*{% else %}\s*<tr><td colspan="5"[^>]*>No search console data available</td></tr>\s*{% endif %}',
    r'''<th style="padding:8px 0;width:90px;">Month</th>
                            <th style="padding:8px 0;">Page Path</th>
                            <th style="text-align:right;padding:8px 6px;">Clicks</th>
                            <th style="text-align:right;padding:8px 6px;">Impr.</th>
                            <th style="text-align:right;padding:8px 6px;">CTR</th>
                            <th style="text-align:right;padding:8px 0;">Avg. Pos</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% set ts_dict = gsc.get("top_pages", {}) %}
                        {% set ns = namespace(found=false) %}
                        {% for month in months|reverse %}
                            {% for p in ts_dict.get(month, []) %}
                            {% set ns.found = true %}
                            <tr style="border-bottom:1px solid var(--line-2, #eee);">
                                <td style="padding:6px 0;color:var(--muted);font-size:10px;">{{ month }}</td>
                                <td style="padding:6px 0;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--brand, #2563eb);">{{ p.page }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);font-weight:600;">{{ p.clicks | fmt }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);">{{ p.impressions | fmt }}</td>
                                <td style="text-align:right;padding:6px;font-family:var(--mono);">{{ p.ctr }}%</td>
                                <td style="text-align:right;padding:6px 0;font-family:var(--mono);">{{ p.position }}</td>
                            </tr>
                            {% endfor %}
                        {% endfor %}
                        {% if not ns.found %}
                            <tr><td colspan="6" style="text-align:center;padding:24px 0;color:var(--muted);">No search console data available</td></tr>
                        {% endif %}''', content
)


with open("app/templates/report_pdf.html", "w") as f:
    f.write(content)
