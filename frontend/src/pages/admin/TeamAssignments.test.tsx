// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TeamAssignments from './TeamAssignments';
import api from '../../api/client';
import { confirmDialog } from '../../components/ui/ConfirmDialog';

vi.mock('../../api/client', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: { id: 'me', email: 'me@example.com', role: 'user' } }) }));
vi.mock('../../components/ui/ConfirmDialog', () => ({ confirmDialog: vi.fn() }));
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }));

const options = {
  users: [{ id: 'me', email: 'me@example.com' }, { id: 'colleague', email: 'colleague@example.com' }],
  projects: [{ id: 'free', name: 'Available', domain: 'free.com', user_id: null },
    { id: 'taken', name: 'Assigned', domain: 'taken.com', user_id: 'colleague' }],
};

beforeEach(() => {
  vi.mocked(confirmDialog).mockResolvedValue(true);
  vi.mocked(api.delete).mockResolvedValue({ data: { message: 'Project unassigned successfully' } });
  vi.mocked(api.get).mockResolvedValue({ data: options });
  vi.mocked(api.post).mockResolvedValue({ data: { message: 'Project assigned successfully' } });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

async function open() {
  render(<MemoryRouter><TeamAssignments /></MemoryRouter>);
  await screen.findByLabelText('Project');
}

describe('team assignments', () => {
  it('defaults to self and submits the selected project', async () => {
    await open();
    expect((screen.getByLabelText('Assign to') as HTMLSelectElement).value).toBe('me');
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'free' } });
    fireEvent.click(screen.getByRole('button', { name: 'Assign Project' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/team/assignments', { client_id: 'free', user_id: 'me' }));
  });

  it('allows choosing another team member', async () => {
    await open();
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'free' } });
    fireEvent.change(screen.getByLabelText('Assign to'), { target: { value: 'colleague' } });
    fireEvent.click(screen.getByRole('button', { name: 'Assign Project' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/team/assignments', { client_id: 'free', user_id: 'colleague' }));
  });

  it('blocks assignment to anyone until the current user is unassigned', async () => {
    await open();
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'taken' } });
    expect(screen.getByRole('status').textContent).toContain('Unassign the current user');
    expect((screen.getByRole('button', { name: 'Assign Project' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('button', { name: 'Unassign' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Assign to'), { target: { value: 'colleague' } });
    expect((screen.getByRole('button', { name: 'Assign Project' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows a retry when the team cannot be loaded', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(new Error('offline'));
    render(<MemoryRouter><TeamAssignments /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    expect(await screen.findByLabelText('Project')).toBeTruthy();
  });

  it('retains the selection after an assignment failure', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('forbidden'));
    await open();
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'free' } });
    fireEvent.click(screen.getByRole('button', { name: 'Assign Project' }));
    await waitFor(() => expect((screen.getByRole('button', { name: 'Assign Project' }) as HTMLButtonElement).disabled).toBe(false));
    expect((screen.getByLabelText('Project') as HTMLSelectElement).value).toBe('free');
  });
});


it('unassigns explicitly before enabling assignment', async () => {
  await open();
  fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'taken' } });
  vi.mocked(api.get).mockResolvedValueOnce({ data: {
    ...options, projects: options.projects.map(p => ({ ...p, user_id: null })),
  } });
  fireEvent.click(screen.getByRole('button', { name: 'Unassign' }));
  await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/team/assignments/taken/colleague'));
  await waitFor(() => expect((screen.getByRole('button', { name: 'Assign Project' }) as HTMLButtonElement).disabled).toBe(false));
  expect(api.post).not.toHaveBeenCalled();
});

it('leaves the assignment intact when unassign is cancelled', async () => {
  vi.mocked(confirmDialog).mockResolvedValueOnce(false);
  await open();
  fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'taken' } });
  fireEvent.click(screen.getByRole('button', { name: 'Unassign' }));
  await waitFor(() => expect(confirmDialog).toHaveBeenCalled());
  expect(api.delete).not.toHaveBeenCalled();
  expect((screen.getByRole('button', { name: 'Assign Project' }) as HTMLButtonElement).disabled).toBe(true);
});

it('offers project creation even when the team has no projects', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: { users: options.users, projects: [] } });
  render(<MemoryRouter><TeamAssignments /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Create Project' }));
  expect((screen.getByLabelText('Assign to') as HTMLSelectElement).value).toBe('me');
  fireEvent.change(screen.getByLabelText('Project name'), { target: { value: 'New project' } });
  fireEvent.change(screen.getByLabelText('Domain'), { target: { value: 'new.example.com' } });
  fireEvent.change(screen.getByLabelText('Assign to'), { target: { value: 'colleague' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create & Assign' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/team/projects', {
    name: 'New project', domain: 'new.example.com', business_type: 'ecommerce', locale: 'en-GB',
    package_keywords: 10, user_id: 'colleague',
  }));
});

it('keeps creation fields available after a failed request', async () => {
  await open();
  vi.mocked(api.post).mockRejectedValueOnce(new Error('unavailable'));
  fireEvent.click(screen.getByRole('button', { name: 'Create Project' }));
  fireEvent.change(screen.getByLabelText('Project name'), { target: { value: 'Keep this' } });
  fireEvent.change(screen.getByLabelText('Domain'), { target: { value: 'keep.example.com' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create & Assign' }));
  await waitFor(() => expect((screen.getByRole('button', { name: 'Create & Assign' }) as HTMLButtonElement).disabled).toBe(false));
  expect((screen.getByLabelText('Project name') as HTMLInputElement).value).toBe('Keep this');
});
