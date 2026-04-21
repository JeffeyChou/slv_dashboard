import type { Logger } from '../../infra/logging/logger.js';
import { computeBackoffDelayMs, computeJitteredDelayMs } from './scheduler.js';
import type {
  XhsFeedClient,
  XhsMonitorRuntimeConfig,
  XhsNoteSummary,
  XhsScanResult,
  XhsSeenStore,
  XhsWebhookPublisher
} from './types.js';

type TimerHandle = ReturnType<typeof setTimeout>;

export class XhsUserMonitor {
  private readonly timers = new Map<string, TimerHandle>();
  private readonly runningUsers = new Set<string>();
  private readonly failureCounts = new Map<string, number>();

  constructor(
    private readonly config: XhsMonitorRuntimeConfig,
    private readonly client: XhsFeedClient,
    private readonly store: XhsSeenStore,
    private readonly publisher: XhsWebhookPublisher,
    private readonly logger: Logger,
    private readonly random: () => number = Math.random
  ) {}

  start(): void {
    for (const userId of this.config.userIds) {
      this.scheduleUser(userId, 0);
    }
  }

  stop(): void {
    for (const timer of this.timers.values()) {
      clearTimeout(timer);
    }
    this.timers.clear();
  }

  async scanUserOnce(userId: string, observedAt = new Date().toISOString()): Promise<XhsScanResult> {
    if (this.runningUsers.has(userId)) {
      return {
        userId,
        fetched: 0,
        baselineSeeded: false,
        published: 0,
        skippedKnown: 0,
        publishFailures: 0,
        duplicateRisk: 0
      };
    }

    this.runningUsers.add(userId);
    try {
      const notes = await this.client.listRecentPosts(userId, this.config.maxNotesPerScan);
      const limitedNotes = notes.slice(0, this.config.maxNotesPerScan);
      const hasBaseline = await this.store.hasBaseline(userId);
      if (!hasBaseline && !this.config.sendBaseline) {
        await this.store.markBaseline(
          userId,
          limitedNotes.map((note) => note.id),
          observedAt
        );
        this.logger.info('xhs.monitor.baseline_seeded', {
          userId,
          noteCount: limitedNotes.length
        });
        return {
          userId,
          fetched: limitedNotes.length,
          baselineSeeded: true,
          published: 0,
          skippedKnown: limitedNotes.length,
          publishFailures: 0,
          duplicateRisk: 0
        };
      }

      if (!hasBaseline) {
        await this.store.markBaseline(userId, [], observedAt);
      }

      const unseen = await this.store.filterUnseen(userId, limitedNotes);
      const publishable = sortOldestFirst(unseen).slice(0, this.config.maxNotesPerScan);
      let published = 0;
      let publishFailures = 0;
      let duplicateRisk = 0;

      for (const note of publishable) {
        try {
          await this.publisher.publish(note);
        } catch (error) {
          publishFailures += 1;
          this.logger.error('xhs.monitor.webhook_publish_failed', {
            userId,
            noteId: note.id,
            message: error instanceof Error ? error.message : String(error)
          });
          continue;
        }

        try {
          await this.store.markSeen(userId, note.id, observedAt);
          published += 1;
        } catch (error) {
          duplicateRisk += 1;
          this.logger.error('xhs.monitor.seen_store_write_failed_after_publish', {
            userId,
            noteId: note.id,
            duplicateRisk: true,
            message: error instanceof Error ? error.message : String(error)
          });
        }
      }

      const result = {
        userId,
        fetched: limitedNotes.length,
        baselineSeeded: false,
        published,
        skippedKnown: limitedNotes.length - unseen.length,
        publishFailures,
        duplicateRisk
      };
      this.logger.info('xhs.monitor.scan_completed', result);
      return result;
    } finally {
      this.runningUsers.delete(userId);
    }
  }

  private scheduleUser(userId: string, delayMs: number): void {
    const timer = setTimeout(() => {
      this.timers.delete(userId);
      void this.runScheduledScan(userId);
    }, delayMs);
    this.timers.set(userId, timer);
  }

  private async runScheduledScan(userId: string): Promise<void> {
    try {
      await this.scanUserOnce(userId);
      this.failureCounts.set(userId, 0);
    } catch (error) {
      const failureCount = (this.failureCounts.get(userId) ?? 0) + 1;
      this.failureCounts.set(userId, failureCount);
      this.logger.error('xhs.monitor.scan_failed', {
        userId,
        failureCount,
        message: error instanceof Error ? error.message : String(error)
      });
    } finally {
      const failureCount = this.failureCounts.get(userId) ?? 0;
      const jitteredDelay = computeJitteredDelayMs({
        intervalMs: this.config.intervalMs,
        jitterMs: this.config.jitterMs,
        random: this.random
      });
      const backoffDelay = computeBackoffDelayMs(failureCount, this.config.minUserGapMs);
      this.scheduleUser(userId, Math.max(this.config.minUserGapMs, jitteredDelay + backoffDelay));
    }
  }
}

function sortOldestFirst(notes: XhsNoteSummary[]): XhsNoteSummary[] {
  return [...notes].sort((a, b) => timestampValue(a.publishedAt) - timestampValue(b.publishedAt));
}

function timestampValue(value: string | undefined): number {
  return value ? Date.parse(value) || 0 : 0;
}
