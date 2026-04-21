import test from 'node:test';
import assert from 'node:assert/strict';

import { XhsUserMonitor } from '../src/core/xhs/monitor.js';
import { InMemoryXhsSeenStore } from '../src/core/xhs/seen-store.js';
import type {
  XhsFeedClient,
  XhsMonitorRuntimeConfig,
  XhsNoteSummary,
  XhsWebhookPublisher
} from '../src/core/xhs/types.js';
import type { Logger } from '../src/infra/logging/logger.js';

function baseConfig(overrides: Partial<XhsMonitorRuntimeConfig> = {}): XhsMonitorRuntimeConfig {
  return {
    userIds: ['user-a'],
    cookie: 'a1=abc',
    webhook: {
      url: 'https://discord.com/api/v10/webhooks/123/token',
      redactedUrl: 'https://discord.com/api/v10/webhooks/123/[redacted-webhook-token]'
    },
    apiProfile: 'xiaohongshu',
    apiBase: 'https://edith.xiaohongshu.com',
    webBase: 'https://www.xiaohongshu.com',
    intervalMs: 30 * 60_000,
    jitterMs: 5 * 60_000,
    statePath: '.data/xhs-seen.json',
    sendBaseline: false,
    maxNotesPerScan: 10,
    requestTimeoutMs: 15_000,
    minUserGapMs: 3000,
    ...overrides
  };
}

function note(id: string, publishedAt: string): XhsNoteSummary {
  return {
    id,
    userId: 'user-a',
    title: `Note ${id}`,
    url: `https://www.xiaohongshu.com/explore/${id}`,
    publishedAt
  };
}

class FakeClient implements XhsFeedClient {
  public responses: XhsNoteSummary[][] = [];

  async listRecentPosts(): Promise<XhsNoteSummary[]> {
    return this.responses.shift() ?? [];
  }
}

class FakePublisher implements XhsWebhookPublisher {
  public published: XhsNoteSummary[] = [];
  public failNext = false;

  async publish(note: XhsNoteSummary): Promise<void> {
    if (this.failNext) {
      this.failNext = false;
      throw new Error('webhook failed');
    }
    this.published.push(note);
  }
}

function logger(): Logger {
  return {
    info() {},
    error() {}
  };
}

test('XhsUserMonitor seeds baseline on first scan without publishing by default', async () => {
  const client = new FakeClient();
  const publisher = new FakePublisher();
  const store = new InMemoryXhsSeenStore();
  client.responses = [[note('old-1', '2026-04-17T00:00:00.000Z'), note('old-2', '2026-04-17T01:00:00.000Z')]];
  const monitor = new XhsUserMonitor(baseConfig(), client, store, publisher, logger());

  const result = await monitor.scanUserOnce('user-a', '2026-04-18T00:00:00.000Z');

  assert.equal(result.baselineSeeded, true);
  assert.equal(result.published, 0);
  assert.equal(publisher.published.length, 0);
});

test('XhsUserMonitor publishes unseen notes after baseline oldest-first', async () => {
  const client = new FakeClient();
  const publisher = new FakePublisher();
  const store = new InMemoryXhsSeenStore();
  client.responses = [
    [note('old-1', '2026-04-17T00:00:00.000Z')],
    [
      note('old-1', '2026-04-17T00:00:00.000Z'),
      note('new-2', '2026-04-18T02:00:00.000Z'),
      note('new-1', '2026-04-18T01:00:00.000Z')
    ],
    [
      note('old-1', '2026-04-17T00:00:00.000Z'),
      note('new-2', '2026-04-18T02:00:00.000Z'),
      note('new-1', '2026-04-18T01:00:00.000Z')
    ]
  ];
  const monitor = new XhsUserMonitor(baseConfig(), client, store, publisher, logger());

  await monitor.scanUserOnce('user-a', '2026-04-18T00:00:00.000Z');
  const second = await monitor.scanUserOnce('user-a', '2026-04-18T03:00:00.000Z');
  const third = await monitor.scanUserOnce('user-a', '2026-04-18T04:00:00.000Z');

  assert.equal(second.published, 2);
  assert.deepEqual(publisher.published.map((published) => published.id), ['new-1', 'new-2']);
  assert.equal(third.published, 0);
});

test('XhsUserMonitor leaves failed webhook notes unseen for retry', async () => {
  const client = new FakeClient();
  const publisher = new FakePublisher();
  const store = new InMemoryXhsSeenStore();
  client.responses = [
    [],
    [note('new-1', '2026-04-18T01:00:00.000Z')],
    [note('new-1', '2026-04-18T01:00:00.000Z')]
  ];
  publisher.failNext = true;
  const monitor = new XhsUserMonitor(baseConfig(), client, store, publisher, logger());

  await monitor.scanUserOnce('user-a', '2026-04-18T00:00:00.000Z');
  const failed = await monitor.scanUserOnce('user-a', '2026-04-18T01:30:00.000Z');
  const retried = await monitor.scanUserOnce('user-a', '2026-04-18T02:00:00.000Z');

  assert.equal(failed.publishFailures, 1);
  assert.equal(retried.published, 1);
  assert.deepEqual(publisher.published.map((published) => published.id), ['new-1']);
});

test('XhsUserMonitor can publish baseline when configured', async () => {
  const client = new FakeClient();
  const publisher = new FakePublisher();
  const store = new InMemoryXhsSeenStore();
  client.responses = [[note('old-1', '2026-04-17T00:00:00.000Z')]];
  const monitor = new XhsUserMonitor(baseConfig({ sendBaseline: true }), client, store, publisher, logger());

  const result = await monitor.scanUserOnce('user-a', '2026-04-18T00:00:00.000Z');

  assert.equal(result.baselineSeeded, false);
  assert.equal(result.published, 1);
  assert.deepEqual(publisher.published.map((published) => published.id), ['old-1']);
});
