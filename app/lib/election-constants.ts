import type { Alliance } from '../types/election';

export const ALLIANCES: Alliance[] = ['ldf', 'udf', 'nda'];

export const ALLIANCE_COLORS: Record<Alliance, string> = {
  ldf: '#cc0000',
  udf: '#1e40af',
  nda: '#ea580c',
  ind: '#4b5563',
  other: '#4b5563',
};

export const ALLIANCE_BG: Record<Alliance, string> = {
  ldf: '#fef2f2',
  udf: '#eff6ff',
  nda: '#fff7ed',
  ind: '#f3f4f6',
  other: '#f3f4f6',
};

export const ALLIANCE_LABELS: Record<Alliance, string> = {
  ldf: 'LDF',
  udf: 'UDF',
  nda: 'BJP',
  ind: 'IND',
  other: 'IND',
};
