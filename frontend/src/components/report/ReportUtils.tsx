

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

/** A count as a reader expects it: whole, with thousand separators.
 *
 *  Everything this formats is a count — clicks, sessions, calls, links.
 *  Summing or averaging daily rows leaves decimals that mean nothing to
 *  anyone: nobody made 721.82 calls. Figures that genuinely carry decimals
 *  (average position, CTR) are formatted explicitly where they are used. */
export function fmt(n: number | undefined) {
  return Math.round(n ?? 0).toLocaleString();
}

/** For the few figures where the decimal is the point, such as a rate. */
export function fmtPrecise(n: number | undefined, places = 1) {
  return (n ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
  });
}

export function rankClass(pos: number | undefined) {
  if (!pos) return 'rank out';
  if (pos <= 10) return 'rank p1';
  if (pos <= 20) return 'rank p2';
  return 'rank out';
}
