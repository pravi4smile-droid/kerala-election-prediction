export function fmtInt(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString();
}

export function pct(numerator: number, denominator: number, digits = 1): string {
  if (!denominator) return '-';
  return `${(numerator / denominator * 100).toFixed(digits)}%`;
}

export function cleanName(name?: string): string {
  return (name || '')
    .replace(/^(ADV\.|DR\.|ADVOCATE|SHRI|SMT\.)\s*/i, '')
    .trim();
}

export function shortName(name?: string, words = 2): string {
  const cleaned = cleanName(name);
  if (!cleaned) return '-';
  return cleaned.split(/\s+/).slice(-words).join(' ');
}

export function signed(value: number | null | undefined, suffix = ''): string {
  if (value == null || Number.isNaN(value)) return '-';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}${suffix}`;
}
