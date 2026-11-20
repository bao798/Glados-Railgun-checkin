export function parseCookiePairs(raw) {
  return String(raw || '').split(';').map(s => s.trim()).filter(Boolean).map(s => {
    const i = s.indexOf('=');
    if (i <= 0) throw new Error('Invalid cookie field.');
    return { name: s.slice(0, i).trim(), value: s.slice(i + 1) };
  });
}
export function selectCheckinButton(candidates) {
  const allowed = /^(?:check[ -]?in(?: now)?|daily check[ -]?in|punch(?: in)?|(?:立即|每日|点击)?签到)$/i;
  const matches = candidates.filter(c => allowed.test(c.text));
  if (matches.length > 1) throw new Error('Multiple check-in buttons; stop instead of guessing.');
  return matches[0] || null;
}

export function hasRecordToday(list, now = Date.now()) {
  if (!Array.isArray(list) || !list.length) return null;
  const day = t => {
    if (t == null) return null;
    const ms = typeof t === 'number' ? (t < 1e12 ? t * 1000 : t) : new Date(t).getTime();
    return Number.isFinite(ms) ? new Date(ms + 8 * 3600000).toISOString().slice(0, 10) : null;
  };
  const dates = list.slice(0,8).map(it => day(it?.time ?? it?.createdAt ?? it?.created_at ?? it?.date)).filter(Boolean);
  return dates.length ? dates.includes(day(now)) : null;
}
