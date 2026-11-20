import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCookiePairs, selectCheckinButton, hasRecordToday } from './ui-policy.js';
test('cookie values containing = are preserved without logging', () => {
  assert.deepEqual(parseCookiePairs('gld:sess=abc==; gld:sess.sig=xyz'), [{name:'gld:sess',value:'abc=='},{name:'gld:sess.sig',value:'xyz'}]);
});
test('malformed credentials stop before browser submission', () => {
  assert.throws(() => parseCookiePairs('invalid'));
});
test('only an unambiguous check-in control can be used', () => {
  const choice={text:'Check in now'};
  assert.equal(selectCheckinButton([{text:'Buy now'},choice]),choice);
  assert.equal(selectCheckinButton([{text:'Purchase'}, {text:'Verify you are human'}]),null);
  assert.throws(() => selectCheckinButton([{text:'签到'},{text:'Check in'}]));
});

test('today means the Beijing natural day, and unknown history stays unknown', () => {
  const now=Date.parse('2026-11-20T16:30:00Z');
  assert.equal(hasRecordToday([{time:'2026-11-20T17:00:00Z'}],now),true);
  assert.equal(hasRecordToday([{time:'2026-11-20T15:00:00Z'}],now),false);
  assert.equal(hasRecordToday([{unexpected:1}],now),null);
});
