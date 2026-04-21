import { readFile } from 'node:fs/promises';

import { DEFAULT_RUNTIME_CONFIG, type RuntimeConfig } from '../core/config/runtime-config.js';
import { buildXhsDiscordWebhookUrl, redactWebhookSecret } from '../core/xhs/webhook-publisher.js';
import type { XhsMonitorRuntimeConfig } from '../core/xhs/types.js';

const REQUIRED_ENV_KEYS = [
  'DISCORD_BOT_TOKEN',
  'DISCORD_AUTHORIZATION',
  'DISCORD_APPLICATION_ID',
  'DISCORD_QUERY_CHANNEL_ID',
  'DISCORD_RESULT_CHANNEL_ID',
  'DISCORD_UW_BOT_USER_ID'
] as const;

export const GATEWAY_INTENTS = {
  GUILDS: 1 << 0,
  GUILD_MESSAGES: 1 << 9,
  MESSAGE_CONTENT: 1 << 15
} as const;

export type DiscordEnvKey = (typeof REQUIRED_ENV_KEYS)[number];

export type DiscordRuntimeEnvironment = RuntimeConfig & {
  discordBotToken: string;
  discordAuthorization: string;
  discordApplicationId: string;
  discordGuildId: string;
  discordGuildIds: string[];
  discordExecutionGuildId: string;
  discordQueryChannelId: string;
  discordResultChannelId: string;
  discordObservationChannelId: string;
  discordExecutionChannelId: string;
  discordUwBotUserId: string;
  gatewayIntents: number;
};

export async function loadDiscordRuntimeEnvironment(envPath = '.env'): Promise<DiscordRuntimeEnvironment> {
  const fileEnv = await readDotEnv(envPath);
  const merged = {
    ...fileEnv,
    ...process.env
  };

  for (const key of REQUIRED_ENV_KEYS) {
    if (!merged[key]?.trim()) {
      throw new Error(`missing required environment variable: ${key}`);
    }
  }

  const discordGuildIds = parseDiscordGuildIds(merged.DISCORD_GUILD_IDS, merged.DISCORD_GUILD_ID);
  if (!discordGuildIds.length) {
    throw new Error('missing required environment variable: DISCORD_GUILD_ID or DISCORD_GUILD_IDS');
  }

  const timeoutMs = parseOptionalInteger(merged.DISCORD_PROXY_TIMEOUT_MS, DEFAULT_RUNTIME_CONFIG.timeoutMs);
  const showMappedCommand = parseOptionalBoolean(merged.DISCORD_SHOW_MAPPED_COMMAND, DEFAULT_RUNTIME_CONFIG.showMappedCommand);
  const xhsMonitor = parseXhsMonitorEnvironment(merged);

  return {
    defaultQueryChannelId: merged.DISCORD_QUERY_CHANNEL_ID!,
    defaultResultChannelId: merged.DISCORD_RESULT_CHANNEL_ID!,
    uwAuthorId: merged.DISCORD_UW_BOT_USER_ID!,
    timeoutMs,
    showMappedCommand,
    discordBotToken: merged.DISCORD_BOT_TOKEN!,
    discordAuthorization: merged.DISCORD_AUTHORIZATION!,
    discordApplicationId: merged.DISCORD_APPLICATION_ID!,
    discordGuildId: discordGuildIds[0]!,
    discordGuildIds,
    discordExecutionGuildId: merged.DISCORD_EXECUTION_GUILD_ID?.trim() || discordGuildIds[0]!,
    discordQueryChannelId: merged.DISCORD_QUERY_CHANNEL_ID!,
    discordResultChannelId: merged.DISCORD_RESULT_CHANNEL_ID!,
    discordObservationChannelId: merged.DISCORD_OBSERVATION_CHANNEL_ID?.trim() || merged.DISCORD_QUERY_CHANNEL_ID!,
    discordExecutionChannelId: merged.DISCORD_EXECUTION_CHANNEL_ID?.trim() || merged.DISCORD_QUERY_CHANNEL_ID!,
    discordUwBotUserId: merged.DISCORD_UW_BOT_USER_ID!,
    gatewayIntents: GATEWAY_INTENTS.GUILDS | GATEWAY_INTENTS.GUILD_MESSAGES | GATEWAY_INTENTS.MESSAGE_CONTENT,
    ...(xhsMonitor ? { xhsMonitor } : {})
  };
}

async function readDotEnv(envPath: string): Promise<Record<string, string>> {
  try {
    const raw = await readFile(envPath, 'utf8');
    return parseDotEnv(raw);
  } catch {
    return {};
  }
}

export function parseDotEnv(content: string): Record<string, string> {
  const parsed: Record<string, string> = {};

  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }

    const separatorIndex = trimmed.indexOf('=');
    if (separatorIndex < 1) {
      continue;
    }

    const key = trimmed.slice(0, separatorIndex).trim();
    const value = trimmed.slice(separatorIndex + 1).trim().replace(/^['"]|['"]$/g, '');
    parsed[key] = value;
  }

  return parsed;
}

export function parseDiscordGuildIds(value: string | undefined, fallback?: string): string[] {
  const combined = [value, fallback].filter((entry): entry is string => Boolean(entry?.trim())).join(',');
  if (!combined) {
    return [];
  }

  return [...new Set(combined.split(',').map((entry) => entry.trim()).filter(Boolean))];
}

export function parseXhsMonitorEnvironment(env: Record<string, string | undefined>): XhsMonitorRuntimeConfig | undefined {
  const userIds = parseCsvList(env.XHS_MONITOR_USER_IDS);
  if (!userIds.length) {
    return undefined;
  }

  const cookie = requireTrimmed(env.XHS_COOKIE, 'XHS_COOKIE');
  const webhook = parseXhsWebhookTarget(env);
  const apiProfile = parseXhsApiProfile(env.XHS_API_PROFILE);
  const defaultEndpoints = resolveXhsDefaultEndpoints(apiProfile);
  const intervalMinutes = parsePositiveInteger(env.XHS_MONITOR_INTERVAL_MINUTES, 30, 'XHS_MONITOR_INTERVAL_MINUTES');
  const jitterMinutes = parseNonNegativeInteger(env.XHS_MONITOR_JITTER_MINUTES, 5, 'XHS_MONITOR_JITTER_MINUTES');
  if (jitterMinutes >= intervalMinutes) {
    throw new Error('XHS_MONITOR_JITTER_MINUTES must be less than XHS_MONITOR_INTERVAL_MINUTES');
  }

  const signerScriptPath = env.XHS_SIGNER_SCRIPT_PATH?.trim();
  return {
    userIds,
    cookie,
    webhook,
    apiProfile,
    apiBase: env.XHS_API_BASE?.trim() || defaultEndpoints.apiBase,
    webBase: env.XHS_WEB_BASE?.trim() || defaultEndpoints.webBase,
    intervalMs: intervalMinutes * 60_000,
    jitterMs: jitterMinutes * 60_000,
    statePath: env.XHS_MONITOR_STATE_PATH?.trim() || '.data/xhs-seen.json',
    sendBaseline: parseOptionalBoolean(env.XHS_MONITOR_SEND_BASELINE, false),
    maxNotesPerScan: parsePositiveInteger(env.XHS_MONITOR_MAX_NOTES_PER_SCAN, 10, 'XHS_MONITOR_MAX_NOTES_PER_SCAN'),
    requestTimeoutMs: parsePositiveInteger(env.XHS_MONITOR_REQUEST_TIMEOUT_MS, 15_000, 'XHS_MONITOR_REQUEST_TIMEOUT_MS'),
    minUserGapMs: parsePositiveInteger(env.XHS_MONITOR_MIN_USER_GAP_SECONDS, 3, 'XHS_MONITOR_MIN_USER_GAP_SECONDS') * 1000,
    ...(signerScriptPath ? { signerScriptPath } : {})
  };
}

export function parseXhsApiProfile(value: string | undefined): XhsMonitorRuntimeConfig['apiProfile'] {
  const normalized = value?.trim().toLowerCase();
  if (!normalized || normalized === 'xiaohongshu') {
    return 'xiaohongshu';
  }
  if (normalized === 'rednote') {
    return 'rednote';
  }

  throw new Error('XHS_API_PROFILE must be xiaohongshu or rednote');
}

function resolveXhsDefaultEndpoints(profile: XhsMonitorRuntimeConfig['apiProfile']): Pick<XhsMonitorRuntimeConfig, 'apiBase' | 'webBase'> {
  if (profile === 'rednote') {
    return {
      apiBase: 'https://webapi.rednote.com',
      webBase: 'https://www.rednote.com'
    };
  }

  return {
    apiBase: 'https://edith.xiaohongshu.com',
    webBase: 'https://www.xiaohongshu.com'
  };
}

export function parseCsvList(value: string | undefined): string[] {
  if (!value?.trim()) {
    return [];
  }

  return [...new Set(value.split(',').map((entry) => entry.trim()).filter(Boolean))];
}

export function parseXhsWebhookTarget(env: Record<string, string | undefined>): XhsMonitorRuntimeConfig['webhook'] {
  const fullUrl = env.XHS_DISCORD_WEBHOOK_URL?.trim();
  if (fullUrl) {
    return {
      url: fullUrl,
      redactedUrl: redactWebhookSecret(fullUrl, fullUrl)
    };
  }

  const id = env.XHS_DISCORD_WEBHOOK_ID?.trim() || env.XHS_WEBHOOK_ID?.trim();
  const token = env.XHS_DISCORD_WEBHOOK_TOKEN?.trim() || env.XHS_WEBHOOK_TOKEN?.trim();
  if (id && token) {
    const url = buildXhsDiscordWebhookUrl(id, token);
    return {
      url,
      redactedUrl: redactWebhookSecret(url, url)
    };
  }

  if (token && !id) {
    throw new Error('XHS_DISCORD_WEBHOOK_TOKEN requires XHS_DISCORD_WEBHOOK_ID');
  }

  throw new Error('missing required XHS webhook config: XHS_DISCORD_WEBHOOK_URL or XHS_DISCORD_WEBHOOK_ID + XHS_DISCORD_WEBHOOK_TOKEN');
}

function requireTrimmed(value: string | undefined, key: string): string {
  if (!value?.trim()) {
    throw new Error(`missing required environment variable: ${key}`);
  }

  return value.trim();
}

export function parseOptionalBoolean(value: string | undefined, fallback: boolean): boolean {
  if (!value) {
    return fallback;
  }

  const normalized = value.trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(normalized)) {
    return true;
  }
  if (['0', 'false', 'no', 'off'].includes(normalized)) {
    return false;
  }

  return fallback;
}

export function parseOptionalInteger(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parsePositiveInteger(value: string | undefined, fallback: number, key: string): number {
  const parsed = parseOptionalInteger(value, fallback);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${key} must be a positive integer`);
  }
  return parsed;
}

function parseNonNegativeInteger(value: string | undefined, fallback: number, key: string): number {
  const parsed = parseOptionalInteger(value, fallback);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`${key} must be a non-negative integer`);
  }
  return parsed;
}
