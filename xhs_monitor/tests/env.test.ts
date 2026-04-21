import test from 'node:test';
import assert from 'node:assert/strict';

import { parseCsvList, parseDiscordGuildIds, parseDotEnv, parseXhsMonitorEnvironment } from '../src/discord/env.js';

test('parseDotEnv reads key-value pairs and strips quotes', () => {
  const parsed = parseDotEnv(`DISCORD_BOT_TOKEN="abc"\nDISCORD_GUILD_ID=123\n# comment\n`);

  assert.deepEqual(parsed, {
    DISCORD_BOT_TOKEN: 'abc',
    DISCORD_GUILD_ID: '123'
  });
});

test('parseDiscordGuildIds supports comma-separated guild ids with single-id fallback', () => {
  assert.deepEqual(parseDiscordGuildIds('123, 456,123', '789'), ['123', '456', '789']);
  assert.deepEqual(parseDiscordGuildIds(undefined, '123'), ['123']);
  assert.deepEqual(parseDiscordGuildIds(undefined, undefined), []);
});

test('parseCsvList trims and deduplicates entries', () => {
  assert.deepEqual(parseCsvList(' user-a, user-b,user-a ,, '), ['user-a', 'user-b']);
});

test('parseXhsMonitorEnvironment leaves monitor disabled by default', () => {
  assert.equal(parseXhsMonitorEnvironment({}), undefined);
});

test('parseXhsMonitorEnvironment parses webhook url config', () => {
  const config = parseXhsMonitorEnvironment({
    XHS_MONITOR_USER_IDS: 'user-a,user-b',
    XHS_COOKIE: 'a1=abc; web_session=session',
    XHS_DISCORD_WEBHOOK_URL: 'https://discord.com/api/v10/webhooks/123/token-secret'
  });

  assert.deepEqual(config?.userIds, ['user-a', 'user-b']);
  assert.equal(config?.intervalMs, 30 * 60_000);
  assert.equal(config?.jitterMs, 5 * 60_000);
  assert.equal(config?.apiProfile, 'xiaohongshu');
  assert.equal(config?.apiBase, 'https://edith.xiaohongshu.com');
  assert.equal(config?.webBase, 'https://www.xiaohongshu.com');
  assert.equal(config?.statePath, '.data/xhs-seen.json');
  assert.equal(config?.sendBaseline, false);
  assert.equal(config?.maxNotesPerScan, 10);
  assert.equal(config?.requestTimeoutMs, 15_000);
  assert.equal(config?.minUserGapMs, 3000);
  assert.equal(config?.webhook.redactedUrl.includes('token-secret'), false);
});

test('parseXhsMonitorEnvironment supports rednote profile endpoints', () => {
  const config = parseXhsMonitorEnvironment({
    XHS_MONITOR_USER_IDS: 'user-a',
    XHS_COOKIE: 'a1=abc',
    XHS_DISCORD_WEBHOOK_URL: 'https://discord.com/api/v10/webhooks/123/token-secret',
    XHS_API_PROFILE: 'rednote'
  });

  assert.equal(config?.apiProfile, 'rednote');
  assert.equal(config?.apiBase, 'https://webapi.rednote.com');
  assert.equal(config?.webBase, 'https://www.rednote.com');
});

test('parseXhsMonitorEnvironment derives webhook url from id and token', () => {
  const config = parseXhsMonitorEnvironment({
    XHS_MONITOR_USER_IDS: 'user-a',
    XHS_COOKIE: 'a1=abc',
    XHS_DISCORD_WEBHOOK_ID: '123',
    XHS_DISCORD_WEBHOOK_TOKEN: 'token-secret',
    XHS_MONITOR_INTERVAL_MINUTES: '40',
    XHS_MONITOR_JITTER_MINUTES: '7',
    XHS_MONITOR_SEND_BASELINE: 'true'
  });

  assert.equal(config?.webhook.url, 'https://discord.com/api/v10/webhooks/123/token-secret');
  assert.equal(config?.intervalMs, 40 * 60_000);
  assert.equal(config?.jitterMs, 7 * 60_000);
  assert.equal(config?.sendBaseline, true);
});

test('parseXhsMonitorEnvironment rejects incomplete enabled monitor config', () => {
  assert.throws(
    () =>
      parseXhsMonitorEnvironment({
        XHS_MONITOR_USER_IDS: 'user-a',
        XHS_DISCORD_WEBHOOK_TOKEN: 'token-secret'
      }),
    /XHS_COOKIE/
  );

  assert.throws(
    () =>
      parseXhsMonitorEnvironment({
        XHS_MONITOR_USER_IDS: 'user-a',
        XHS_COOKIE: 'a1=abc',
        XHS_DISCORD_WEBHOOK_TOKEN: 'token-secret'
      }),
    /WEBHOOK_TOKEN requires/
  );
});

test('parseXhsMonitorEnvironment rejects jitter greater than interval', () => {
  assert.throws(
    () =>
      parseXhsMonitorEnvironment({
        XHS_MONITOR_USER_IDS: 'user-a',
        XHS_COOKIE: 'a1=abc',
        XHS_DISCORD_WEBHOOK_URL: 'https://discord.com/api/v10/webhooks/123/token-secret',
        XHS_MONITOR_INTERVAL_MINUTES: '5',
        XHS_MONITOR_JITTER_MINUTES: '5'
      }),
    /JITTER/
  );
});
