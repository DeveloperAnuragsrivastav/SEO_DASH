"""Configured reporting dates survive final-report composition and HTML rendering."""
from copy import deepcopy
from datetime import date
import uuid

import pytest

from app.models.client import Client
from app.models.report_snapshot import ReportSnapshot
from app.routes.reports import _build_comparative_report
from app.services.pdf_service import render_report_html
from app.services.report_period import period_name, short_range, span_name, span_compare_label


@pytest.mark.parametrize('start,end,prev_start,prev_end', [
    (date(2026, 9, 8), date(2026, 10, 7), date(2026, 8, 8), date(2026, 9, 7)),
    (date(2026, 9, 1), date(2026, 9, 30), date(2026, 8, 1), date(2026, 8, 31)),
    (date(2025, 12, 8), date(2026, 1, 7), date(2025, 11, 8), date(2025, 12, 7)),
])
def test_final_report_preserves_current_and_comparison_dates(db_session, test_users, start, end, prev_start, prev_end):
    current, previous = period_name(start, end), period_name(prev_start, prev_end)
    client = Client(account_id=test_users['admin'].account_id, name='Period test', domain='example.com',
                    business_type='saas', locale='en-US', package_keywords=10, status='active', onboarded_at=start)
    db_session.add(client)
    db_session.flush()
    snapshot = {
        'period': {'start': start.isoformat(), 'end': end.isoformat(), 'months': 1,
                   'labels': [current], 'label': current, 'range': short_range(start, end),
                   'compare': {'start': prev_start.isoformat(), 'end': prev_end.isoformat(),
                               'range': short_range(prev_start, prev_end), 'hasData': True}},
        'periods': [{'start': start.isoformat(), 'end': end.isoformat(), 'label': current}],
        'rankings': {'keywords': [{'keyword_id': str(uuid.uuid4()), 'term': 'example keyword',
                                  'position': 5, 'previous_position': 8, 'change': 3,
                                  'positions': {current: 5}}]},
        'ga4': {'sessions': 100, 'channels': [{'channel': 'Organic Search', 'sessions': 100}],
                'channels_previous': [{'channel': 'Organic Search', 'sessions': 80}],
                'countries': [{'country': 'India', 'users': 50, 'sessions': 100}],
                'countries_previous': [{'country': 'India', 'users': 40, 'sessions': 80}]},
    }
    original = deepcopy(snapshot)
    report = ReportSnapshot(client_id=client.id, start_date=start, end_date=end, status='draft', snapshot=snapshot)
    db_session.add(report)
    db_session.flush()
    result = _build_comparative_report([report])
    assert result['period']['label'] == current
    assert result['period']['compare']['range'] == short_range(prev_start, prev_end)
    assert result['rank_months'] == [previous, current]
    assert result['rankings']['keywords'][0]['positions'] == {previous: 8, current: 5}
    assert report.snapshot == original
    html = render_report_html(result, {'name': client.name, 'domain': client.domain}, 'http://localhost:8000')
    assert f'{current} (Latest)' in html
    assert previous in html
    assert 'Traffic acquisition by channel' in html
    assert short_range(prev_start, prev_end) in html
    if start.day != 1:
        assert 'September 2026 (Latest)' not in html
        assert 'vs August 2026' not in html


def test_combined_custom_period_preserves_each_cycle(db_session, test_users):
    cycles = [(date(2026, 8, 8), date(2026, 9, 7)), (date(2026, 9, 8), date(2026, 10, 7))]
    labels = [period_name(s, e) for s, e in cycles]
    client = Client(account_id=test_users['admin'].account_id, name='Combined', domain='example.com',
                    business_type='saas', locale='en-US', package_keywords=10, status='active', onboarded_at=cycles[0][0])
    db_session.add(client)
    db_session.flush()
    snapshot = {
        'period': {'start': cycles[0][0].isoformat(), 'end': cycles[-1][1].isoformat(), 'months': 2,
                   'label': span_name(cycles, labels), 'labels': labels,
                   'compare': {'range': span_compare_label(cycles, labels), 'hasData': True}},
        'periods': [{'start': s.isoformat(), 'end': e.isoformat(), 'label': label} for (s, e), label in zip(cycles, labels)],
        'rankings': {'keywords': [{'keyword_id': str(uuid.uuid4()), 'term': 'example', 'position': 5,
                                  'positions': dict(zip(labels, [8, 5]))}]},
    }
    report = ReportSnapshot(client_id=client.id, start_date=cycles[0][0], end_date=cycles[-1][1], status='draft', snapshot=snapshot)
    db_session.add(report)
    db_session.flush()
    result = _build_comparative_report([report])
    assert result['months'] == labels
    assert [p['label'] for p in result['periods']] == labels
    assert result['period']['compare']['range'] == span_compare_label(cycles, labels)
    assert result['rankings']['keywords'][0]['positions'] == dict(zip(labels, [8, 5]))
