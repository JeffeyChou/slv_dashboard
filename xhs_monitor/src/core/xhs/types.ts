export type XhsWebhookTarget = {
  url: string;
  redactedUrl: string;
};

export type XhsMonitorRuntimeConfig = {
  userIds: string[];
  cookie: string;
  webhook: XhsWebhookTarget;
  apiProfile: 'xiaohongshu' | 'rednote';
  apiBase: string;
  webBase: string;
  intervalMs: number;
  jitterMs: number;
  statePath: string;
  sendBaseline: boolean;
  maxNotesPerScan: number;
  requestTimeoutMs: number;
  minUserGapMs: number;
  signerScriptPath?: string;
};

export type XhsNoteSummary = {
  id: string;
  userId: string;
  title: string;
  url: string;
  authorName?: string;
  excerpt?: string;
  publishedAt?: string;
  imageUrls?: string[];
  xsecToken?: string;
  xsecSource?: string;
};

export type XhsScanResult = {
  userId: string;
  fetched: number;
  baselineSeeded: boolean;
  published: number;
  skippedKnown: number;
  publishFailures: number;
  duplicateRisk: number;
};

export type XhsFeedClient = {
  listRecentPosts(userId: string, limit: number): Promise<XhsNoteSummary[]>;
};

export type XhsSeenStore = {
  hasBaseline(userId: string): Promise<boolean>;
  markBaseline(userId: string, noteIds: string[], observedAt: string): Promise<void>;
  filterUnseen(userId: string, notes: XhsNoteSummary[]): Promise<XhsNoteSummary[]>;
  markSeen(userId: string, noteId: string, observedAt: string): Promise<void>;
};

export type XhsWebhookPublisher = {
  publish(note: XhsNoteSummary): Promise<void>;
};

export type XhsRequestSigner = {
  sign(input: {
    apiPath: string;
    body?: unknown;
    method: 'GET' | 'POST';
    cookie: string;
  }): Promise<Record<string, string>>;
};
