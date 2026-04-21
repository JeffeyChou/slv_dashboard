import type { XhsMonitorRuntimeConfig } from '../xhs/types.js';

export type RuntimeConfig = {
  defaultQueryChannelId: string;
  defaultResultChannelId: string;
  uwAuthorId: string;
  timeoutMs: number;
  showMappedCommand: boolean;
  xhsMonitor?: XhsMonitorRuntimeConfig;
};

export const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
  defaultQueryChannelId: 'uw-query-channel',
  defaultResultChannelId: 'uw-results-channel',
  uwAuthorId: 'uw-bot',
  timeoutMs: 120_000,
  showMappedCommand: true
};
