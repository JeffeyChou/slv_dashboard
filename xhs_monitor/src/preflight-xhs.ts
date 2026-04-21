import { readFile } from 'node:fs/promises';

import { parseDotEnv, parseXhsMonitorEnvironment } from './discord/env.js';
import { SpiderXhsScriptSigner } from './core/xhs/xhs-signing.js';
import { XhsPcFeedClient } from './core/xhs/xhs-client.js';

const fileEnv = await readDotEnv('.env');
const xhsMonitor = parseXhsMonitorEnvironment({
  ...fileEnv,
  ...process.env
});
if (!xhsMonitor) {
  throw new Error('XHS monitor is disabled. Set XHS_MONITOR_USER_IDS, XHS_COOKIE, and webhook config first.');
}

const signer = xhsMonitor.signerScriptPath ? new SpiderXhsScriptSigner(xhsMonitor.signerScriptPath) : undefined;
const client = new XhsPcFeedClient(xhsMonitor, signer ? { signer } : {});
const userId = xhsMonitor.userIds[0]!;
const notes = await client.listRecentPosts(userId, xhsMonitor.maxNotesPerScan);

console.log(
  JSON.stringify(
    {
      userId,
      noteCount: notes.length,
      apiProfile: xhsMonitor.apiProfile,
      apiBase: xhsMonitor.apiBase,
      webBase: xhsMonitor.webBase,
      notes: notes.slice(0, 3).map((note) => ({
        id: note.id,
        title: note.title,
        url: note.url,
        publishedAt: note.publishedAt
      }))
    },
    null,
    2
  )
);

async function readDotEnv(envPath: string): Promise<Record<string, string>> {
  try {
    const raw = await readFile(envPath, 'utf8');
    return parseDotEnv(raw);
  } catch {
    return {};
  }
}
