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

import { normalizeInboundWithImages } from './protocol.mjs';
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII=', 'base64');
const picture = (overrides = {}) => ({ type: 'attachment', mimeType: 'image/png', size: png.length,
  stream: async () => new ReadableStream({ start(controller) { controller.enqueue(png); controller.close(); } }), ...overrides });
test('photo-only and mixed SDK groups preserve pictures and captions', async () => {
  const result = await normalizeInboundWithImages({ ...message, content: { type: 'group', items: [{ content: picture() }, { content: { type: 'text', text: 'look' } }, { content: picture() }] } }, 'chat', '+123');
  assert.equal(result.text, 'look'); assert.equal(result.images.length, 2);
  assert.equal(result.images[0], `data:image/png;base64,${png.toString('base64')}`);
  assert.equal((await normalizeInboundWithImages({ ...message, content: picture() }, 'chat', '+123')).images.length, 1);
});
test('unknown senders never download images; unsupported formats return explicit status', async () => {
  let called = false;
  const content = picture({ stream: async () => { called = true; throw new Error('private'); } });
  assert.equal(await normalizeInboundWithImages({ ...message, content }, 'chat', '+456'), null);
  assert.equal(called, false);
  const failed = await normalizeInboundWithImages({ ...message, content: picture({ mimeType: 'image/heic' }) }, 'chat', '+123');
  assert.deepEqual(failed.images, []); assert.match(failed.text, /未提供给模型/);
});
test('stream size is enforced even when declared size lies', async () => {
  const result = await normalizeInboundWithImages({ ...message, content: picture({ size: 1, stream: async () => new ReadableStream({ start(c) { c.enqueue(Buffer.alloc(8 * 1024 * 1024 + 1)); c.close(); } }) }) }, 'chat', '+123');
  assert.deepEqual(result.images, []); assert.match(result.text, /8MB/);
});

test('outbound image sends native attachment bytes without resolving a text target', async () => {
  const sent = [];
  const space = { id: 'chat', send: async value => { sent.push(value); return { id: 'photo-guid' }; } };
  const builders = { attachment: (bytes, options) => ({ bytes, ...options }) };
  const result = await sendAction(space, { kind: 'image', chat_guid: 'chat' }, builders, { data: png, mimeType: 'image/png' });
  assert.equal(result.id, 'photo-guid'); assert.deepEqual(sent[0].bytes, png); assert.equal(sent[0].mimeType, 'image/png');
  await assert.rejects(sendAction(space, { kind: 'image', chat_guid: 'chat' }, builders));
});
