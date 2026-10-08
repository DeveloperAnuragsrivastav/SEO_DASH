"""Real-Postgres assignment tests using authenticated HTTP requests."""
from datetime import date
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.dependencies import get_current_user
from app.main import app
from app.models.client import Client
from app.models.enums import UserRole
from app.models.user import User
from app.models.user_project import UserProjectAssignment


@pytest.fixture
def team(db_session, test_users):
    account_id = test_users['admin'].account_id

    def member(name, role=UserRole.user, manager=None, active=True):
        user = User(account_id=account_id, email=f'{name}@example.com', password_hash='unused',
                    role=role, manager_id=manager.id if manager else None, is_active=active)
        db_session.add(user)
        db_session.flush()
        return user

    manager = member('manager', UserRole.manager)
    other_manager = member('other-manager', UserRole.manager)
    actor = member('actor', manager=manager)
    colleague = member('colleague', manager=manager)
    outsider = member('outsider', manager=other_manager)
    inactive = member('inactive', manager=manager, active=False)
    orphan = member('orphan')

    def project(name, owner):
        client = Client(account_id=account_id, manager_id=owner.id, name=name,
                        domain=f'{name}.example.com', business_type='saas', locale='en-US',
                        package_keywords=10, status='active', onboarded_at=date.today())
        db_session.add(client)
        db_session.flush()
        return client

    project_a = project('ours', manager)
    project_b = project('theirs', other_manager)
    db_session.commit()
    # Remove the legacy super-admin override: these tests exercise real JWT authentication.
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as http:
        yield dict(http=http, manager=manager, other_manager=other_manager, actor=actor,
                   colleague=colleague, outsider=outsider, inactive=inactive, orphan=orphan,
                   project=project_a, other_project=project_b)


def headers(user):
    return {'Authorization': f'Bearer {create_access_token({"sub": user.email})}'}


def assign(team, target, project=None, actor=None, path='/team/assignments'):
    return team['http'].post(path, headers=headers(actor or team['actor']), json={
        'user_id': str(target.id), 'client_id': str((project or team['project']).id),
    })


def test_options_only_show_own_team(team):
    response = team['http'].get('/team/assignments', headers=headers(team['actor']))
    assert response.status_code == 200
    data = response.json()
    assert {u['id'] for u in data['users']} == {str(team['actor'].id), str(team['colleague'].id)}
    assert [p['id'] for p in data['projects']] == [str(team['project'].id)]
    assert data['projects'][0]['user_id'] is None


@pytest.mark.parametrize('target', ['actor', 'colleague'])
def test_assign_to_self_or_teammate(team, db_session, target):
    assert assign(team, team[target]).status_code == 201
    mapping = db_session.scalar(select(UserProjectAssignment))
    assert mapping.user_id == team[target].id
    # The recipient gains project access; the other team member does not.
    for name in ['actor', 'colleague']:
        response = team['http'].get(f'/clients/{team["project"].id}', headers=headers(team[name]))
        assert response.status_code == (200 if name == target else 403)


def test_reassignment_requires_unassign_and_repeat_does_not_duplicate(team, db_session):
    assert assign(team, team['actor']).status_code == 201
    assert assign(team, team['colleague']).status_code == 409
    assert db_session.scalar(select(UserProjectAssignment)).user_id == team['actor'].id
    response = team['http'].delete(
        f'/team/assignments/{team["project"].id}/{team["actor"].id}', headers=headers(team['actor']))
    assert response.status_code == 200
    assert db_session.get(Client, team['project'].id) is not None
    assert db_session.scalar(select(UserProjectAssignment)) is None
    assert assign(team, team['colleague']).status_code == 201
    assert assign(team, team['colleague']).status_code == 201
    mappings = db_session.scalars(select(UserProjectAssignment)).all()
    assert len(mappings) == 1
    assert mappings[0].user_id == team['colleague'].id
    assert team['http'].get(f'/clients/{team["project"].id}', headers=headers(team['actor'])).status_code == 403
    options = team['http'].get('/team/assignments', headers=headers(team['actor'])).json()
    assert options['projects'][0]['user_id'] == str(team['colleague'].id)


@pytest.mark.parametrize('target', ['outsider', 'manager', 'inactive', 'orphan'])
def test_reject_invalid_recipient(team, db_session, target):
    assert assign(team, team[target]).status_code == 403
    assert db_session.scalar(select(UserProjectAssignment)) is None


def test_reject_foreign_project(team, db_session):
    assert assign(team, team['actor'], project=team['other_project']).status_code == 403
    assert db_session.scalar(select(UserProjectAssignment)) is None


def test_unlinked_user_cannot_list_or_assign(team):
    assert team['http'].get('/team/assignments', headers=headers(team['orphan'])).status_code == 403
    assert assign(team, team['actor'], actor=team['orphan']).status_code == 403


def test_inactive_manager_cannot_delegate(team, db_session):
    team['manager'].is_active = False
    db_session.commit()
    assert team['http'].get('/team/assignments', headers=headers(team['actor'])).status_code == 403
    assert assign(team, team['actor']).status_code == 403


def test_user_still_cannot_create_users_or_projects(team):
    assert team['http'].post('/managers/me/users', headers=headers(team['actor']), json={
        'email': 'new@example.com', 'password': 'password', 'role': 'user',
    }).status_code == 403
    assert team['http'].post('/clients', headers=headers(team['actor']), json={
        'name': 'new', 'domain': 'new.example.com', 'business_type': 'saas', 'locale': 'en-US',
        'package_keywords': 10, 'status': 'active',
    }).status_code == 403
    assert assign(team, team['actor'], path='/managers/me/assignments').status_code == 403


def test_manager_assignments_still_work(team):
    assert assign(team, team['actor'], actor=team['manager'], path='/managers/me/assignments').status_code == 201
    assert assign(team, team['outsider'], actor=team['manager'], path='/managers/me/assignments').status_code == 403


def test_requires_login_and_active_user(team, db_session):
    assert team['http'].get('/team/assignments').status_code == 401
    team['actor'].is_active = False
    db_session.commit()
    assert assign(team, team['colleague']).status_code == 401


def test_unknown_recipient_is_rejected(team):
    response = team['http'].post('/team/assignments', headers=headers(team['actor']), json={
        'user_id': str(uuid.uuid4()), 'client_id': str(team['project'].id),
    })
    assert response.status_code == 403


@pytest.mark.parametrize('actor,path', [('actor', '/team/assignments'), ('manager', '/managers/me/assignments')])
def test_unassign_permissions_and_stale_request(team, db_session, actor, path):
    assert assign(team, team['colleague']).status_code == 201
    http = team['http']
    auth = headers(team[actor])
    # A stale UI must not remove someone else's newer assignment.
    assert http.delete(f'{path}/{team["project"].id}/{team["actor"].id}', headers=auth).status_code == 409
    assert http.delete(f'{path}/{team["other_project"].id}/{team["outsider"].id}', headers=auth).status_code == 403
    assert db_session.scalar(select(UserProjectAssignment)).user_id == team['colleague'].id
    assert http.delete(f'{path}/{team["project"].id}/{team["colleague"].id}', headers=auth).status_code == 200
    assert http.get(f'/clients/{team["project"].id}', headers=headers(team['colleague'])).status_code == 403
    assert db_session.get(Client, team['project'].id) is not None


def test_manager_must_also_unassign_first(team):
    assert assign(team, team['actor']).status_code == 201
    assert assign(team, team['colleague'], actor=team['manager'], path='/managers/me/assignments').status_code == 409


def test_unassign_requires_active_team_and_login(team, db_session):
    path = f'/team/assignments/{team["project"].id}/{team["actor"].id}'
    assert team['http'].delete(path).status_code == 401
    assert team['http'].delete(path, headers=headers(team['orphan'])).status_code == 403
    team['manager'].is_active = False
    db_session.commit()
    assert team['http'].delete(path, headers=headers(team['actor'])).status_code == 403
