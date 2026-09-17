import type { Assignment } from './types';

export function planningToday() {
  // Match the backend's fixed UTC+07 business calendar, not the browser timezone.
  return new Date(Date.now() + 7 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

export function peakAllocation(assignments: Assignment[], startDate = '', endDate = '') {
  const ordinal = (value: string) => Date.parse(`${value}T00:00:00Z`) / 86400000;
  const lower = ordinal(startDate || '0001-01-01');
  const upper = ordinal(endDate || '9999-12-31');
  const events = new Map<number, number>();
  for (const item of assignments) {
    const start = Math.max(lower, ordinal(item.start_date || '0001-01-01'));
    const end = Math.min(upper, ordinal(item.end_date || '9999-12-31'));
    if (start <= end) {
      events.set(start, (events.get(start) || 0) + item.allocation);
      events.set(end + 1, (events.get(end + 1) || 0) - item.allocation);
    }
  }
  let current = 0;
  let peak = 0;
  for (const [, delta] of [...events].sort(([a], [b]) => a - b)) {
    current += delta;
    peak = Math.max(peak, current);
  }
  return peak;
}
