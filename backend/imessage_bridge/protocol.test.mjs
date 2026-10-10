import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeInbound, sendAction } from './protocol.mjs';

const message = { id: 'u1', space: { id: 'chat' }, sender: { id: '+123' }, timestamp: '2026-10-10T00:00:00Z', content: { type: 'text', text: 'hello' } };
test('SDK reply wrapper preserves target and only extracts new text', () => {
  const result = normalizeInbound({ ...message, content: { type: 'reply', target: { id: 'a1', content: { type: 'text', text: 'old' } }, content: { type: 'text', text: 'new' } } });
  assert.equal(result.text, 'new'); assert.equal(result.reply_to, 'a1'); assert.equal(result.quote_text, 'old');
  assert.equal(result.sent_at, message.timestamp);
});
test('reaction is its own event, never text', () => {
  const result = normalizeInbound({ ...message, content: { type: 'reaction', emoji: '❤️', target: message } });
  assert.equal(result.kind, 'reaction'); assert.equal(result.target_id, 'u1'); assert.equal(result.text, undefined);
});
test('outbound, read, and unsupported events are ignored', () => {
  assert.equal(normalizeInbound({ ...message, direction: 'outbound' }), null);
  assert.equal(normalizeInbound({ ...message, content: { type: 'read', target: message } }), null);
  assert.equal(normalizeInbound({ ...message, content: { type: 'voice' } }), null);
});
test('reply and reaction resolve exact target after a process restart', async () => {
  const target = { ...message, id: 'u1' };
  const sent = [];
  const space = { id: 'chat', getMessage: async id => id === 'u1' ? target : null, send: async content => { sent.push(content); return { id: 'new-id' }; } };
  const builders = { text: text => ({ text }), reply: (content, target) => ({ content, target, type: 'reply' }), reaction: (emoji, target) => ({ emoji, target, type: 'reaction' }) };
  assert.equal((await sendAction(space, { kind: 'reply', chat_guid: 'chat', ref_id: 'u1', body: 'answer' }, builders)).id, 'new-id');
  await sendAction(space, { kind: 'reaction', chat_guid: 'chat', ref_id: 'u1', body: '❤️' }, builders);
  assert.equal(sent[0].target.id, 'u1'); assert.equal(sent[1].type, 'reaction');
  await assert.rejects(sendAction(space, { kind: 'reply', chat_guid: 'other', ref_id: 'u1' }, builders));
  await assert.rejects(sendAction(space, { kind: 'reply', chat_guid: 'chat', ref_id: 'missing' }, builders));
  assert.equal(sent.length, 2);
});
