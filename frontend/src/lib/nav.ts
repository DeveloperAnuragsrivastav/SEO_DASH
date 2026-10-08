/** Every screen's identity, in one place.
 *
 * A screen's name is written here once and read by the sidebar, the
 * breadcrumb trail and the page's own heading — so the three can never
 * disagree about what a screen is called, which is exactly how the same
 * page ended up as "Backlinks", "Performed Backlinks Activities" and
 * "Links built for this client" at the same time.
 *
 * `name` is the canonical short label: nav item, breadcrumb, and <h1>.
 * `lede` is the one sentence the page may show under its heading. It says
 * what the screen is *for*, never what it is called again.
 */

export type Role = 'super_admin' | 'manager' | 'user';

/** Sidebar groups, in the order they are shown. */
export const GROUPS = ['report', 'performance', 'delivery', 'setup'] as const;
export type Group = (typeof GROUPS)[number];

export const GROUP_LABEL: Record<Group, string> = {
  report: 'Report',
  performance: 'Performance',
  delivery: 'Work delivered',
  setup: 'Setup',
};

export interface Screen {
  key: string;
  name: string;
  lede?: string;
  /** Path builder. Client screens take the client id. */
  path: (clientId?: string) => string;
  /** Sidebar group. Omitted screens are reachable but not listed. */
  group?: Group;
  /** Roles that may see the nav entry. Omitted means everyone. */
  roles?: Role[];
  /** Screens that sit under another in the trail. */
  parent?: string;
}

/** Agency-level screens — shown above the client context. */
export const AGENCY: Screen[] = [
  {
    key: 'team-assignments',
    name: 'Assign Projects',
    lede: 'Assign your manager’s projects to yourself or another member of your team.',
    path: () => '/admin/team-assignments',
    roles: ['user'],
  },
  {
    key: 'clients',
    name: 'Clients',
    lede: 'Every project this agency is responsible for.',
    path: () => '/admin/clients',
  },
  {
    key: 'managers',
    name: 'Managers',
    lede: 'Manager accounts, the people they oversee and the projects they own.',
    path: () => '/admin/users',
    roles: ['super_admin'],
  },
  {
    key: 'team',
    name: 'Team',
    lede: 'Your team and who works on what.',
    path: () => '/admin/manager-tools',
    roles: ['manager'],
  },
];

/** Client-level screens — shown once a client is open. */
export const CLIENT: Screen[] = [
  {
    key: 'overview',
    name: 'Overview',
    lede: 'Where this client’s reporting stands, and what it is built from.',
    path: id => `/admin/clients/${id}`,
    group: 'report',
  },

  {
    key: 'reports',
    name: 'Reports',
    lede: 'Every month’s report — open, download, or reopen one to change it.',
    path: id => `/clients/${id}/reports`,
    group: 'report',
  },

  {
    key: 'search-console',
    name: 'Search Console',
    lede: 'Clicks, impressions, CTR and position — one column per published month.',
    path: id => `/clients/${id}/search-console`,
    group: 'performance',
  },
  {
    key: 'google-analytics',
    name: 'Google Analytics',
    lede: 'Sessions, leads, channels and countries — one column per published month.',
    path: id => `/clients/${id}/google-analytics`,
    group: 'performance',
  },
  {
    key: 'business-profile',
    name: 'Business Profile',
    lede: 'Calls, directions, website clicks and impressions — one column per published month.',
    path: id => `/clients/${id}/gbp`,
    group: 'performance',
  },
  {
    key: 'keywords',
    name: 'Keywords',
    lede: 'Every tracked keyword’s position, month by month as published.',
    path: id => `/clients/${id}/keywords`,
    group: 'performance',
  },
  {
    key: 'ai-visibility',
    name: 'AI Visibility',
    lede: 'Visibility score, mentions and each prompt’s answers — month by month as published.',
    path: id => `/clients/${id}/ai-mentions-data`,
    group: 'performance',
  },
  {
    key: 'ai-prompts',
    name: 'Prompts',
    lede: 'The prompts checked against each AI assistant.',
    path: id => `/clients/${id}/ai-prompts`,
    parent: 'ai-visibility',
  },

  {
    key: 'backlinks',
    name: 'Backlinks',
    lede: 'Links built each month, by kind. Click a month for the full list.',
    path: id => `/clients/${id}/links`,
    group: 'delivery',
  },
  {
    key: 'on-site',
    name: 'On-Site SEO',
    lede: 'On-site work delivered each month. Click a month for the task list.',
    path: id => `/clients/${id}/work`,
    group: 'delivery',
  },
  {
    key: 'screenshots',
    name: 'Screenshots',
    lede: 'Screenshots from each published report, by month.',
    path: id => `/clients/${id}/screenshots`,
    group: 'delivery',
  },

  {
    key: 'connections',
    name: 'Connections',
    lede: 'Google properties this client’s data is pulled from.',
    path: id => `/admin/clients/${id}/connections`,
    group: 'setup',
    roles: ['super_admin', 'manager'],
  },
];

/** Screens outside the nav that still need a name in the trail. */
export const OTHER: Screen[] = [
  { key: 'report', name: 'Report', path: () => '', parent: 'reports' },
  { key: 'report-builder', name: 'Report builder', path: () => '', parent: 'overview' },
];

const ALL = [...AGENCY, ...CLIENT, ...OTHER];

export function screen(key: string): Screen | undefined {
  return ALL.find(s => s.key === key);
}

export function canSee(s: Screen, role?: string): boolean {
  return !s.roles || s.roles.includes(role as Role);
}

/** The client screens of one group that this role may see. */
export function groupScreens(group: Group, role?: string): Screen[] {
  return CLIENT.filter(s => s.group === group && canSee(s, role));
}

/** Which screen a pathname is, by longest matching path. */
export function screenForPath(pathname: string, clientId?: string): Screen | undefined {
  if (/\/reports\/[^/]+\/build$/.test(pathname)) return screen('report-builder');
  if (/\/reports\//.test(pathname)) return screen('report');

  const candidates = ALL
    .map(s => ({ s, p: s.path(clientId) }))
    .filter(({ p }) => p && (pathname === p || pathname.startsWith(p + '/')))
    .sort((a, b) => b.p.length - a.p.length);

  return candidates[0]?.s;
}
