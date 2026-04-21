import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildXhsDiscordWebhookPayload,
  buildXhsDiscordWebhookUrl,
  redactWebhookSecret,
  XhsDiscordWebhookPublisher
} from '../src/core/xhs/webhook-publisher.js';
import type { XhsNoteSummary } from '../src/core/xhs/types.js';

const NOTE: XhsNoteSummary = {
  id: 'note-1',
  userId: 'user-1',
  authorName: 'Author',
  title: 'A new post',
  url: 'https://www.xiaohongshu.com/explore/note-1',
  excerpt: 'Post body',
  publishedAt: '2026-04-18T00:00:00.000Z',
  imageUrls: ['https://cdn.example.test/image.jpg']
};

test('buildXhsDiscordWebhookPayload renders note embeds and suppresses mentions', () => {
  const payload = buildXhsDiscordWebhookPayload(NOTE);

  assert.match(payload.content, /A new post/);
  assert.deepEqual(payload.allowed_mentions, { parse: [] });
  assert.equal(payload.embeds.length, 1);
  assert.deepEqual(payload.embeds[0]?.thumbnail, { url: 'https://cdn.example.test/image.jpg' });
});

test('buildXhsDiscordWebhookUrl derives Discord webhook url from id and token', () => {
  assert.equal(buildXhsDiscordWebhookUrl('123', 'token'), 'https://discord.com/api/v10/webhooks/123/token');
});

test('XhsDiscordWebhookPublisher posts payloads and redacts failed webhook token', async () => {
  const requests: Array<{ url: string; body: Record<string, unknown> }> = [];
  const fetchImpl = (async (url: string | URL | Request, init?: RequestInit) => {
    requests.push({
      url: String(url),
      body: JSON.parse(String(init?.body)) as Record<string, unknown>
    });
    return {
      ok: true,
      status: 204,
      async text() {
        return '';
      }
    } as Response;
  }) as typeof fetch;
  const publisher = new XhsDiscordWebhookPublisher('https://discord.com/api/v10/webhooks/123/token-secret', fetchImpl);

  await publisher.publish(NOTE);

  assert.equal(requests.length, 1);
  assert.equal(requests[0]?.url, 'https://discord.com/api/v10/webhooks/123/token-secret');
  assert.deepEqual(requests[0]?.body.allowed_mentions, { parse: [] });
});

test('redactWebhookSecret removes raw token and full url', () => {
  const url = 'https://discord.com/api/v10/webhooks/123/token-secret';
  const redacted = redactWebhookSecret(`failed ${url} token-secret`, url);

  assert.equal(redacted.includes('token-secret'), false);
  assert.equal(redacted.includes(url), false);
});
