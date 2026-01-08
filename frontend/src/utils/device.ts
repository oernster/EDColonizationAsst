export const isMobileOrTablet = (): boolean => {
  if (typeof navigator === 'undefined') return false;

  const ua = navigator.userAgent ?? '';
  // Basic UA heuristics are still the most practical for this use-case.
  // We treat Android as mobile/tablet; iPad/iPhone as mobile/tablet.
  // Windows/Mac/Linux desktop browsers should return false.
  if (/Android/i.test(ua)) return true;
  if (/iPad|iPhone|iPod/i.test(ua)) return true;

  // iPadOS 13+ may report as Mac; detect via touch points.
  if (/Macintosh/i.test(ua) && (navigator.maxTouchPoints ?? 0) > 1) return true;

  return false;
};

