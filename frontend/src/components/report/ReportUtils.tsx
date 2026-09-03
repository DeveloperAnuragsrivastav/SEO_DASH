

export function delta(cur: number, prev: number) {
  if (!prev) return null;
  const pct = ((cur - prev) / prev) * 100;
  return pct;
}

export function deltaEl(cur: number, prev: number, suffix = '') {
  const d = delta(cur, prev);
  if (d === null) return <span className="d flat">—</span>;
  if (d > 0) return <span className="d up">▲ {Math.abs(d).toFixed(1)}%{suffix}</span>;
  if (d < 0) return <span className="d dn">▼ {Math.abs(d).toFixed(1)}%{suffix}</span>;
  return <span className="d flat">0%</span>;
}

export function fmt(n: number | undefined) { 
  return (n ?? 0).toLocaleString(); 
}

export function rankClass(pos: number | undefined) {
  if (!pos) return 'rank out';
  if (pos <= 10) return 'rank p1';
  if (pos <= 20) return 'rank p2';
  return 'rank out';
}
