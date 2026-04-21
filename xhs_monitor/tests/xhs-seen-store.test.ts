import { writeFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';

import { JsonXhsSeenStore } from '../src/core/xhs/seen-store.js';
import type { XhsNoteSummary } from '../src/core/xhs/types.js';

function note(id: string): XhsNoteSummary {
  return {
    id,
    userId: 'user-a',
    title: `Note ${id}`,
    url: `https://www.xiaohongshu.com/explore/${id}`
  };
}

test('JsonXhsSeenStore persists baseline and seen notes', async () => {
  const path = `/tmp/xhs-seen-store-${Date.now()}-${Math.random()}.json`;
  const firstStore = new JsonXhsSeenStore(path);
  await firstStore.markBaseline('user-a', ['old-1'], '2026-04-18T00:00:00.000Z');
  await firstStore.markSeen('user-a', 'new-1', '2026-04-18T01:00:00.000Z');

  const secondStore = new JsonXhsSeenStore(path);
  const unseen = await secondStore.filterUnseen('user-a', [note('old-1'), note('new-1'), note('new-2')]);

  assert.equal(await secondStore.hasBaseline('user-a'), true);
  assert.deepEqual(unseen.map((entry) => entry.id), ['new-2']);
});

test('JsonXhsSeenStore reports corrupt state instead of resetting it silently', async () => {
  const path = `/tmp/xhs-seen-store-corrupt-${Date.now()}-${Math.random()}.json`;
  await writeFile(path, '{bad json', 'utf8');
  const store = new JsonXhsSeenStore(path);

  await assert.rejects(() => store.hasBaseline('user-a'), /Invalid XHS seen-state JSON/);
});
