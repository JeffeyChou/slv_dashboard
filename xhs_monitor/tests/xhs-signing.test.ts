import test from 'node:test';
import assert from 'node:assert/strict';

import { parseCookieValue, SpiderXhsScriptSigner } from '../src/core/xhs/xhs-signing.js';

test('parseCookieValue extracts cookie values with embedded equals signs', () => {
  assert.equal(parseCookieValue('web_session=session; a1=abc=def; other=value', 'a1'), 'abc=def');
  assert.equal(parseCookieValue('web_session=session', 'a1'), undefined);
});

test('SpiderXhsScriptSigner requires a1 cookie before loading external script', async () => {
  const signer = new SpiderXhsScriptSigner('/tmp/does-not-need-to-exist.js');

  await assert.rejects(
    () =>
      signer.sign({
        apiPath: '/api/sns/web/v1/user_posted?num=1',
        method: 'GET',
        cookie: 'web_session=session'
      }),
    /missing required a1/
  );
});
