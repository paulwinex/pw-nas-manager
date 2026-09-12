import { date } from 'quasar';

const TZ_SUFFIX = /(?:Z|[+-]\d{2}:\d{2})$/;

export function isTzAware(value: string) {
  return TZ_SUFFIX.test(value);
}

export function formatDateTime(value: string) {
  const iso = isTzAware(value) ? value : `${value}Z`;
  return date.formatDate(iso, 'YYYY-MM-DD HH:mm');
}
