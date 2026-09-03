import re

with open("frontend/src/components/report/TrafficSection.tsx", "r") as f:
    content = f.read()

# Add months to props
content = content.replace("deltas: any;\n}", "deltas: any;\n  months: string[];\n}")
content = content.replace("({ gsc, ga4, gbp, deltas }) =>", "({ gsc, ga4, gbp, deltas, months }) =>")

# GSC Top Pages table
content = re.sub(
    r'<th style={{ textAlign: \'left\' }}>Page URL</th>\s*<th style={{ textAlign: \'right\' }}>Clicks</th>\s*<th style={{ textAlign: \'right\' }}>Impressions</th>\s*<th style={{ textAlign: \'right\' }}>CTR</th>\s*<th style={{ textAlign: \'right\' }}>Position</th>\s*</tr>\s*</thead>\s*<tbody>\s*\{topPages.length > 0 \? topPages\.map\(\(p: any, i: number\) => \(\s*<tr key=\{i\}>\s*<td style={{ maxWidth: \'320px\', overflow: \'hidden\', textOverflow: \'ellipsis\', whiteSpace: \'nowrap\' }}>\s*<a href=\{p\.page\} target="_blank" rel="noreferrer" style={{ color: \'var\(--brand, #2563eb\)\', textDecoration: \'none\' }}>\s*\{\(p\.page \|\| \'\'\)\.replace\(\/\^https\?:\\\\\/\\\\/\/, \'\'\)\.replace\(\/\\\\/\$\/, \'\'\)\}\s*</a>\s*</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\', fontWeight: 500 }}>\{fmt\(p\.clicks\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{fmt\(p\.impressions\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{p\.ctr\}%</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{p\.position\}</td>\s*</tr>\s*\)\) : \(',
    r'''<th style={{ textAlign: 'left', width: '80px' }}>Month</th>
                  <th style={{ textAlign: 'left' }}>Page URL</th>
                  <th style={{ textAlign: 'right' }}>Clicks</th>
                  <th style={{ textAlign: 'right' }}>Impressions</th>
                  <th style={{ textAlign: 'right' }}>CTR</th>
                  <th style={{ textAlign: 'right' }}>Position</th>
                </tr>
              </thead>
              <tbody>
                {months.length > 0 && months.some(m => gsc.top_pages?.[m]?.length > 0) ? (
                  [...months].reverse().map(month => (
                    (gsc.top_pages?.[month] || []).map((p: any, i: number) => (
                      <tr key={`${month}-${i}`}>
                        <td style={{ color: 'var(--text-subtle)', fontSize: '11px' }}>{month}</td>
                        <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <a href={p.page} target="_blank" rel="noreferrer" style={{ color: 'var(--brand, #2563eb)', textDecoration: 'none' }}>
                            {(p.page || '').replace(/^https?:\/\//, '').replace(/\/$/, '')}
                          </a>
                        </td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(p.clicks)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.impressions)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{p.ctr}%</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{p.position}</td>
                      </tr>
                    ))
                  ))
                ) : (''', content
)

# Replace Top Queries (GSC)
content = re.sub(
    r'<th style={{ textAlign: \'left\' }}>Search Query</th>\s*<th style={{ textAlign: \'right\' }}>Clicks</th>\s*<th style={{ textAlign: \'right\' }}>Impressions</th>\s*<th style={{ textAlign: \'right\' }}>CTR</th>\s*<th style={{ textAlign: \'right\' }}>Position</th>\s*</tr>\s*</thead>\s*<tbody>\s*\{\(gsc\.top_queries \|\| \[\]\)\.length > 0 \? \(gsc\.top_queries \|\| \[\]\)\.map\(\(q: any, i: number\) => \(\s*<tr key=\{i\}>\s*<td style={{ fontWeight: 500 }}>\{q\.query\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\', fontWeight: 500 }}>\{fmt\(q\.clicks\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{fmt\(q\.impressions\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{q\.ctr\}%</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{q\.position\}</td>\s*</tr>\s*\)\) : \(',
    r'''<th style={{ textAlign: 'left', width: '80px' }}>Month</th>
                  <th style={{ textAlign: 'left' }}>Search Query</th>
                  <th style={{ textAlign: 'right' }}>Clicks</th>
                  <th style={{ textAlign: 'right' }}>Impressions</th>
                  <th style={{ textAlign: 'right' }}>CTR</th>
                  <th style={{ textAlign: 'right' }}>Position</th>
                </tr>
              </thead>
              <tbody>
                {months.length > 0 && months.some(m => gsc.top_queries?.[m]?.length > 0) ? (
                  [...months].reverse().map(month => (
                    (gsc.top_queries?.[month] || []).map((q: any, i: number) => (
                      <tr key={`${month}-${i}`}>
                        <td style={{ color: 'var(--text-subtle)', fontSize: '11px' }}>{month}</td>
                        <td style={{ fontWeight: 500 }}>{q.query}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(q.clicks)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(q.impressions)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{q.ctr}%</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{q.position}</td>
                      </tr>
                    ))
                  ))
                ) : (''', content
)

# GA4 Traffic Sources
content = re.sub(
    r'<th style={{ textAlign: \'left\' }}>Source / Medium</th>\s*<th style={{ textAlign: \'right\' }}>Sessions</th>\s*<th style={{ textAlign: \'right\' }}>Users</th>\s*<th style={{ textAlign: \'right\' }}>Conversions</th>\s*</tr>\s*</thead>\s*<tbody>\s*\{ga4Sources\.length > 0 \? ga4Sources\.map\(\(s: any, i: number\) => \(\s*<tr key=\{i\}>\s*<td style={{ fontWeight: 600 }}>\{s\.source\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\', fontWeight: 500 }}>\{fmt\(s\.sessions\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{fmt\(s\.users\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{fmt\(s\.conversions\)\}</td>\s*</tr>\s*\)\) : \(',
    r'''<th style={{ textAlign: 'left', width: '80px' }}>Month</th>
                  <th style={{ textAlign: 'left' }}>Source / Medium</th>
                  <th style={{ textAlign: 'right' }}>Sessions</th>
                  <th style={{ textAlign: 'right' }}>Users</th>
                  <th style={{ textAlign: 'right' }}>Conversions</th>
                </tr>
              </thead>
              <tbody>
                {months.length > 0 && months.some(m => ga4.traffic_sources?.[m]?.length > 0) ? (
                  [...months].reverse().map(month => (
                    (ga4.traffic_sources?.[month] || []).map((s: any, i: number) => (
                      <tr key={`${month}-${i}`}>
                        <td style={{ color: 'var(--text-subtle)', fontSize: '11px' }}>{month}</td>
                        <td style={{ fontWeight: 600 }}>{s.source}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(s.sessions)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(s.users)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(s.conversions)}</td>
                      </tr>
                    ))
                  ))
                ) : (''', content
)

# GA4 Top Pages
content = re.sub(
    r'<th style={{ textAlign: \'left\' }}>Page Path</th>\s*<th style={{ textAlign: \'right\' }}>Sessions</th>\s*<th style={{ textAlign: \'right\' }}>Users</th>\s*<th style={{ textAlign: \'right\' }}>Conversions</th>\s*</tr>\s*</thead>\s*<tbody>\s*\{ga4Pages\.length > 0 \? ga4Pages\.map\(\(p: any, i: number\) => \(\s*<tr key=\{i\}>\s*<td style={{ maxWidth: \'320px\', overflow: \'hidden\', textOverflow: \'ellipsis\', whiteSpace: \'nowrap\', color: \'var\(--brand, #2563eb\)\' }}>\{p\.page\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\', fontWeight: 500 }}>\{fmt\(p\.sessions\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{fmt\(p\.users\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{fmt\(p\.conversions\)\}</td>\s*</tr>\s*\)\) : \(',
    r'''<th style={{ textAlign: 'left', width: '80px' }}>Month</th>
                  <th style={{ textAlign: 'left' }}>Page Path</th>
                  <th style={{ textAlign: 'right' }}>Sessions</th>
                  <th style={{ textAlign: 'right' }}>Users</th>
                  <th style={{ textAlign: 'right' }}>Conversions</th>
                </tr>
              </thead>
              <tbody>
                {months.length > 0 && months.some(m => ga4.top_pages?.[m]?.length > 0) ? (
                  [...months].reverse().map(month => (
                    (ga4.top_pages?.[month] || []).map((p: any, i: number) => (
                      <tr key={`${month}-${i}`}>
                        <td style={{ color: 'var(--text-subtle)', fontSize: '11px' }}>{month}</td>
                        <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--brand, #2563eb)' }}>{p.page}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(p.sessions)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.users)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.conversions)}</td>
                      </tr>
                    ))
                  ))
                ) : (''', content
)

# GA4 Countries
content = re.sub(
    r'<th style={{ textAlign: \'left\' }}>Country</th>\s*<th style={{ textAlign: \'right\' }}>Sessions</th>\s*<th style={{ textAlign: \'right\' }}>Users</th>\s*</tr>\s*</thead>\s*<tbody>\s*\{ga4Countries\.length > 0 \? ga4Countries\.map\(\(c: any, i: number\) => \(\s*<tr key=\{i\}>\s*<td style={{ fontWeight: 500 }}>\{c\.country\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\', fontWeight: 500 }}>\{fmt\(c\.sessions\)\}</td>\s*<td style={{ textAlign: \'right\', fontFamily: \'var\(--mono\)\' }}>\{fmt\(c\.users\)\}</td>\s*</tr>\s*\)\) : \(',
    r'''<th style={{ textAlign: 'left', width: '80px' }}>Month</th>
                  <th style={{ textAlign: 'left' }}>Country</th>
                  <th style={{ textAlign: 'right' }}>Sessions</th>
                  <th style={{ textAlign: 'right' }}>Users</th>
                </tr>
              </thead>
              <tbody>
                {months.length > 0 && months.some(m => ga4.countries?.[m]?.length > 0) ? (
                  [...months].reverse().map(month => (
                    (ga4.countries?.[month] || []).map((c: any, i: number) => (
                      <tr key={`${month}-${i}`}>
                        <td style={{ color: 'var(--text-subtle)', fontSize: '11px' }}>{month}</td>
                        <td style={{ fontWeight: 500 }}>{c.country}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(c.sessions)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(c.users)}</td>
                      </tr>
                    ))
                  ))
                ) : (''', content
)


with open("frontend/src/components/report/TrafficSection.tsx", "w") as f:
    f.write(content)
