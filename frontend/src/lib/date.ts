/**
 * Safely parse a date string from backend (which might or might not have 'Z' UTC suffix)
 */
export const parseUTCDate = (dateStr?: string | null): Date | null => {
  if (!dateStr) return null;
  // If backend returned ISO string without timezone ('2026-07-15T15:00:00'), append 'Z' so browser treats it as UTC
  const safeStr = dateStr.endsWith('Z') || dateStr.includes('+') ? dateStr : `${dateStr}Z`;
  const d = new Date(safeStr);
  return isNaN(d.getTime()) ? null : d;
};

/**
 * Format a backend UTC date string into a localized readable string (e.g., Jul 15, 2026, 8:30 PM)
 */
export const formatScheduledDate = (dateStr?: string | null): string => {
  const d = parseUTCDate(dateStr);
  if (!d) return 'Pending';
  return d.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * Format a Date or backend date string into 'YYYY-MM-DDTHH:mm' for <input type="datetime-local" />
 * Uses LOCAL timezone of the user's browser so what they pick/see matches their local clock exactly.
 */
export const toLocalDatetimeInput = (dateStr?: string | null): string => {
  const d = parseUTCDate(dateStr);
  if (!d) return '';
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
