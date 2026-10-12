import { test } from 'node:test';
import assert from 'node:assert/strict';
import { resolveChatImage } from '../src/utils/chatImageInput.js';
const id = '12345678-1234-1234-1234-123456789abc';
test('fresh image bytes stay unchanged', async () => {
  assert.equal(await resolveChatImage('data:image/png;base64,aGVsbG8=', '/api', () => assert.fail()), 'data:image/png;base64,aGVsbG8=');
});
test('history photo/sticker is fetched with authenticated API and encoded', async () => {
  globalThis.FileReader = class {
    async readAsDataURL(blob) { this.result = `data:${blob.type};base64,${Buffer.from(await blob.arrayBuffer()).toString('base64')}`; this.onload(); }
  };
  const result = await resolveChatImage(`/api/chat/image/${id}`, '/api', async path => {
    assert.equal(path, `/chat/image/${id}`);
    return {ok:true, blob:async()=>new Blob(['original'],{type:'image/gif'})};
  });
  assert.equal(result, 'data:image/gif;base64,b3JpZ2luYWw=');
});
test('missing original and arbitrary URLs are rejected without sending', async () => {
  await assert.rejects(resolveChatImage(`/api/chat/image/${id}`, '/api', async()=>({ok:false})), /原图读取失败/);
  await assert.rejects(resolveChatImage('https://example.com/image', '/api', ()=>assert.fail()), /重新选择/);
});
