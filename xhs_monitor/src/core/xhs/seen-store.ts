import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

import type { XhsNoteSummary, XhsSeenStore } from './types.js';

type SeenRecord = {
  firstSeenAt: string;
  lastSeenAt: string;
};

type SeenUserState = {
  baselineAt?: string;
  notes: Record<string, SeenRecord>;
};

type SeenState = {
  version: 1;
  users: Record<string, SeenUserState>;
};

export class JsonXhsSeenStore implements XhsSeenStore {
  private mutationQueue: Promise<void> = Promise.resolve();

  constructor(private readonly path: string) {}

  async hasBaseline(userId: string): Promise<boolean> {
    const state = await this.readState();
    return Boolean(state.users[userId]?.baselineAt);
  }

  async markBaseline(userId: string, noteIds: string[], observedAt: string): Promise<void> {
    await this.updateState((state) => {
      const user = ensureUserState(state, userId);
      user.baselineAt = observedAt;
      for (const noteId of noteIds) {
        user.notes[noteId] = user.notes[noteId] ?? {
          firstSeenAt: observedAt,
          lastSeenAt: observedAt
        };
      }
    });
  }

  async filterUnseen(userId: string, notes: XhsNoteSummary[]): Promise<XhsNoteSummary[]> {
    const state = await this.readState();
    const known = state.users[userId]?.notes ?? {};
    return notes.filter((note) => !known[note.id]);
  }

  async markSeen(userId: string, noteId: string, observedAt: string): Promise<void> {
    await this.updateState((state) => {
      const user = ensureUserState(state, userId);
      const existing = user.notes[noteId];
      user.notes[noteId] = {
        firstSeenAt: existing?.firstSeenAt ?? observedAt,
        lastSeenAt: observedAt
      };
    });
  }

  private async readState(): Promise<SeenState> {
    let raw: string;
    try {
      raw = await readFile(this.path, 'utf8');
    } catch (error) {
      if ((error as { code?: unknown }).code === 'ENOENT') {
        return createEmptyState();
      }
      throw error;
    }

    try {
      return normalizeSeenState(JSON.parse(raw) as unknown);
    } catch (error) {
      throw new Error(`Invalid XHS seen-state JSON at ${this.path}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async writeState(state: SeenState): Promise<void> {
    await mkdir(dirname(this.path), { recursive: true });
    const tempPath = `${this.path}.${process.pid}.${Date.now()}.tmp`;
    await writeFile(tempPath, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
    await rename(tempPath, this.path);
  }

  private async updateState(mutator: (state: SeenState) => void): Promise<void> {
    const previous = this.mutationQueue;
    let release: () => void = () => undefined;
    this.mutationQueue = new Promise<void>((resolve) => {
      release = resolve;
    });

    await previous;
    try {
      const state = await this.readState();
      mutator(state);
      await this.writeState(state);
    } finally {
      release();
    }
  }
}

export class InMemoryXhsSeenStore implements XhsSeenStore {
  private readonly state: SeenState = createEmptyState();

  async hasBaseline(userId: string): Promise<boolean> {
    return Boolean(this.state.users[userId]?.baselineAt);
  }

  async markBaseline(userId: string, noteIds: string[], observedAt: string): Promise<void> {
    const user = ensureUserState(this.state, userId);
    user.baselineAt = observedAt;
    for (const noteId of noteIds) {
      user.notes[noteId] = user.notes[noteId] ?? {
        firstSeenAt: observedAt,
        lastSeenAt: observedAt
      };
    }
  }

  async filterUnseen(userId: string, notes: XhsNoteSummary[]): Promise<XhsNoteSummary[]> {
    const known = this.state.users[userId]?.notes ?? {};
    return notes.filter((note) => !known[note.id]);
  }

  async markSeen(userId: string, noteId: string, observedAt: string): Promise<void> {
    const user = ensureUserState(this.state, userId);
    const existing = user.notes[noteId];
    user.notes[noteId] = {
      firstSeenAt: existing?.firstSeenAt ?? observedAt,
      lastSeenAt: observedAt
    };
  }
}

function normalizeSeenState(input: unknown): SeenState {
  if (!input || typeof input !== 'object') {
    return createEmptyState();
  }

  const candidate = input as Partial<SeenState>;
  const users = candidate.users && typeof candidate.users === 'object' ? candidate.users : {};
  return {
    version: 1,
    users
  };
}

function ensureUserState(state: SeenState, userId: string): SeenUserState {
  state.users[userId] = state.users[userId] ?? { notes: {} };
  return state.users[userId]!;
}

function createEmptyState(): SeenState {
  return {
    version: 1,
    users: {}
  };
}
