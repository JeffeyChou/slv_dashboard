import { randomUUID } from 'node:crypto';

import type { XhsFeedClient, XhsMonitorRuntimeConfig, XhsNoteSummary, XhsRequestSigner } from './types.js';

type XhsClientOptions = {
  apiBase?: string;
  webBase?: string;
  signer?: XhsRequestSigner;
  fetchImpl?: typeof fetch;
};

const DEFAULT_XHS_API_BASE = 'https://edith.xiaohongshu.com';
const DEFAULT_XHS_WEB_BASE = 'https://www.xiaohongshu.com';
const DEFAULT_USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36';

export class XhsPcFeedClient implements XhsFeedClient {
  private readonly apiBase: string;
  private readonly webBase: string;
  private readonly signer: XhsRequestSigner | undefined;
  private readonly fetchImpl: typeof fetch;

  constructor(
    private readonly config: Pick<XhsMonitorRuntimeConfig, 'cookie' | 'requestTimeoutMs' | 'apiProfile' | 'apiBase' | 'webBase'>,
    options: XhsClientOptions = {}
  ) {
    this.apiBase = options.apiBase ?? config.apiBase ?? DEFAULT_XHS_API_BASE;
    this.webBase = options.webBase ?? config.webBase ?? DEFAULT_XHS_WEB_BASE;
    this.signer = options.signer;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  async listRecentPosts(userId: string, limit: number): Promise<XhsNoteSummary[]> {
    if (this.config.apiProfile === 'rednote' && !this.signer) {
      return this.listRecentPostsFromProfilePage(userId, limit);
    }

    const params = new URLSearchParams({
      num: String(Math.min(Math.max(limit, 1), 30)),
      cursor: '',
      user_id: userId,
      image_formats: 'jpg,webp,avif',
      xsec_token: '',
      xsec_source: 'pc_user'
    });
    const apiPath = `/api/sns/web/v1/user_posted?${params.toString()}`;
    try {
      const response = await this.requestJson(apiPath, 'GET');
      return normalizeXhsUserPostedResponse(response, userId).slice(0, limit);
    } catch (error) {
      if (this.config.apiProfile !== 'rednote') {
        throw error;
      }

      return this.listRecentPostsFromProfilePage(userId, limit, error);
    }
  }

  async fetchNoteDetail(note: XhsNoteSummary): Promise<XhsNoteSummary> {
    const body = {
      source_note_id: note.id,
      image_formats: ['jpg', 'webp', 'avif'],
      extra: {
        need_body_topic: '1'
      },
      xsec_source: note.xsecSource ?? 'pc_user',
      xsec_token: note.xsecToken ?? ''
    };
    const response = await this.requestJson('/api/sns/web/v1/feed', 'POST', body);
    return mergeXhsNoteDetail(note, response);
  }

  private async requestJson(apiPath: string, method: 'GET' | 'POST', body?: unknown): Promise<unknown> {
    const signedHeaders = this.signer
      ? await this.signer.sign({
          apiPath,
          body,
          method,
          cookie: this.config.cookie
        })
      : {};
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.config.requestTimeoutMs);

    try {
      const response = await this.fetchImpl(`${this.apiBase}${apiPath}`, {
        method,
        headers: {
          ...buildXhsBaseHeaders(this.config.cookie),
          ...signedHeaders
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
        signal: controller.signal
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(redactXhsCookie(`XHS API ${method} ${apiPath} failed: ${response.status} ${text}`, this.config.cookie));
      }

      const json = (await response.json()) as unknown;
      if (isXhsFailureResponse(json)) {
        throw new Error(redactXhsCookie(`XHS API ${method} ${apiPath} failed: ${json.msg}`, this.config.cookie));
      }

      return json;
    } finally {
      clearTimeout(timeout);
    }
  }

  private async listRecentPostsFromProfilePage(userId: string, limit: number, apiError?: unknown): Promise<XhsNoteSummary[]> {
    const profileUrl = `${this.webBase.replace(/\/$/, '')}/user/profile/${encodeURIComponent(userId)}`;
    const response = await this.fetchImpl(profileUrl, {
      headers: buildXhsProfilePageHeaders(this.config.cookie, this.webBase)
    });
    const html = await response.text();
    const notes = extractXhsProfilePageNotes(html, userId).slice(0, limit);
    if (response.ok && notes.length) {
      return notes;
    }

    const apiMessage = apiError ? `${apiError instanceof Error ? apiError.message : String(apiError)} ` : '';
    throw new Error(
      redactXhsCookie(
        [
          `${apiMessage}RedNote profile fallback failed: status=${response.status}, notes=${notes.length}.`,
          'If the configured value is a RedNote display ID, replace it with the internal /user/profile/<id> value from the web profile URL.'
        ].join(' '),
        this.config.cookie
      )
    );
  }
}

export function buildXhsBaseHeaders(cookie: string): Record<string, string> {
  return {
    accept: 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'cache-control': 'no-cache',
    'content-type': 'application/json;charset=UTF-8',
    origin: 'https://www.xiaohongshu.com',
    pragma: 'no-cache',
    referer: 'https://www.xiaohongshu.com/',
    'sec-ch-ua': '"Chromium";v="122", "Google Chrome";v="122", "Not(A:Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': DEFAULT_USER_AGENT,
    'x-b3-traceid': randomUUID().replace(/-/g, '').slice(0, 16),
    'x-mns': 'unload',
    'x-xray-traceid': randomUUID().replace(/-/g, ''),
    cookie
  };
}

export function buildXhsProfilePageHeaders(cookie: string, webBase = DEFAULT_XHS_WEB_BASE): Record<string, string> {
  return {
    accept: 'text/html',
    'accept-language': 'en-US,en;q=0.9',
    'user-agent': DEFAULT_USER_AGENT,
    ...(cookie ? { cookie } : {})
  };
}

export function normalizeXhsUserPostedResponse(response: unknown, fallbackUserId: string): XhsNoteSummary[] {
  const notes = readArray(response, ['data', 'notes']);
  return notes.map((note) => normalizeXhsNoteSummary(note, fallbackUserId)).filter((note): note is XhsNoteSummary => Boolean(note));
}

export function mergeXhsNoteDetail(base: XhsNoteSummary, response: unknown): XhsNoteSummary {
  const items = readArray(response, ['data', 'items']);
  const detail = items[0] ?? readObject(response, ['data', 'item']) ?? response;
  const normalized = normalizeXhsNoteSummary(detail, base.userId);
  if (!normalized) {
    return base;
  }

  return {
    id: base.id,
    userId: base.userId,
    title: normalized.title,
    url: base.url,
    ...optionalString('authorName', normalized.authorName ?? base.authorName),
    ...optionalString('excerpt', normalized.excerpt ?? base.excerpt),
    ...optionalString('publishedAt', normalized.publishedAt ?? base.publishedAt),
    ...optionalArray('imageUrls', normalized.imageUrls ?? base.imageUrls),
    ...optionalString('xsecToken', normalized.xsecToken ?? base.xsecToken),
    ...optionalString('xsecSource', normalized.xsecSource ?? base.xsecSource)
  };
}

export function extractXhsProfilePageNotes(html: string, fallbackUserId: string): XhsNoteSummary[] {
  const state = extractInitialState(html);
  const userState = readObject(state, ['user']);
  const notesByTab = readArray(userState, ['notes']);
  const postedNotes = Array.isArray(notesByTab[0]) ? notesByTab[0] as unknown[] : [];
  return postedNotes.map((note) => normalizeXhsNoteSummary(note, fallbackUserId)).filter((note): note is XhsNoteSummary => Boolean(note));
}

export function buildXhsNoteUrl(noteId: string, xsecToken?: string, xsecSource?: string): string {
  const url = new URL(`https://www.xiaohongshu.com/explore/${noteId}`);
  if (xsecToken) {
    url.searchParams.set('xsec_token', xsecToken);
  }
  if (xsecSource) {
    url.searchParams.set('xsec_source', xsecSource);
  }
  return url.toString();
}

export function redactXhsCookie(message: string, cookie: string): string {
  return message.split(cookie).join('[redacted-xhs-cookie]');
}

function normalizeXhsNoteSummary(input: unknown, fallbackUserId: string): XhsNoteSummary | undefined {
  if (!input || typeof input !== 'object') {
    return undefined;
  }

  const note = input as Record<string, unknown>;
  const noteCard = readObject(note, ['note_card']);
  const user = readObject(noteCard, ['user']) ?? readObject(note, ['user']);
  const id =
    readString(note, 'note_id') ??
    readString(note, 'noteId') ??
    readString(note, 'id') ??
    readString(noteCard, 'note_id') ??
    readString(noteCard, 'noteId');
  if (!id) {
    return undefined;
  }

  const xsecToken = readString(note, 'xsec_token') ?? readString(note, 'xsecToken') ?? readString(noteCard, 'xsecToken');
  const xsecSource = readString(note, 'xsec_source') ?? readString(note, 'xsecSource') ?? 'pc_user';
  const userId = readString(user, 'user_id') ?? readString(user, 'userId') ?? readString(user, 'id') ?? fallbackUserId;
  const title =
    readString(note, 'display_title') ??
    readString(note, 'displayTitle') ??
    readString(note, 'title') ??
    readString(noteCard, 'display_title') ??
    readString(noteCard, 'displayTitle') ??
    readString(noteCard, 'title') ??
    'Untitled XHS note';
  const excerpt = readString(noteCard, 'desc') ?? readString(noteCard, 'description') ?? readString(note, 'desc') ?? readString(noteCard, 'content');
  const publishedAt = normalizeXhsTimestamp(readNumber(noteCard, 'time') ?? readNumber(note, 'time'));
  const imageUrls = collectImageUrls(note, noteCard);
  const authorName = readString(user, 'nickname') ?? readString(user, 'nickName');

  return {
    id,
    userId,
    title,
    url: buildXhsNoteUrl(id, xsecToken, xsecSource),
    ...(authorName ? { authorName } : {}),
    ...(excerpt ? { excerpt } : {}),
    ...(publishedAt ? { publishedAt } : {}),
    ...(imageUrls.length ? { imageUrls } : {}),
    ...(xsecToken ? { xsecToken } : {}),
    ...(xsecSource ? { xsecSource } : {})
  };
}

function extractInitialState(html: string): unknown {
  const match = html.match(/<script>window\.__INITIAL_STATE__=(.*?)<\/script>/s);
  if (!match?.[1]) {
    return {};
  }

  try {
    return JSON.parse(match[1].replace(/undefined/g, 'null')) as unknown;
  } catch {
    return {};
  }
}

function collectImageUrls(...objects: Array<Record<string, unknown> | undefined>): string[] {
  const urls: string[] = [];
  for (const object of objects) {
    if (!object) {
      continue;
    }

    const cover = readObject(object, ['cover']);
    const coverUrl =
      readString(cover, 'url') ??
      readString(cover, 'urlDefault') ??
      readString(cover, 'urlPre') ??
      readString(cover, 'url_pre') ??
      readString(object, 'cover');
    if (coverUrl) {
      urls.push(coverUrl);
    }

    const images = [...readArray(object, ['image_list']), ...readArray(object, ['imageList'])];
    for (const image of images) {
      const imageObject = image && typeof image === 'object' ? (image as Record<string, unknown>) : undefined;
      const url = readString(imageObject, 'url') ?? readString(imageObject, 'urlDefault') ?? readString(imageObject, 'urlPre') ?? readString(imageObject, 'url_pre');
      if (url) {
        urls.push(url);
      }
    }
  }

  return [...new Set(urls)];
}

function normalizeXhsTimestamp(value: number | undefined): string | undefined {
  if (!value || !Number.isFinite(value)) {
    return undefined;
  }

  const ms = value > 10_000_000_000 ? value : value * 1000;
  return new Date(ms).toISOString();
}

function optionalString<K extends string>(key: K, value: string | undefined): Partial<Record<K, string>> {
  return value ? { [key]: value } as Record<K, string> : {};
}

function optionalArray<K extends string>(key: K, value: string[] | undefined): Partial<Record<K, string[]>> {
  return value?.length ? { [key]: value } as Record<K, string[]> : {};
}

function readObject(input: unknown, path: string[]): Record<string, unknown> | undefined;
function readObject(input: Record<string, unknown> | undefined, key: string): Record<string, unknown> | undefined;
function readObject(input: unknown, pathOrKey: string[] | string): Record<string, unknown> | undefined {
  const value = Array.isArray(pathOrKey) ? readPath(input, pathOrKey) : input?.[pathOrKey as keyof typeof input];
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
}

function readArray(input: unknown, path: string[]): unknown[] {
  const value = readPath(input, path);
  return Array.isArray(value) ? value : [];
}

function readString(input: Record<string, unknown> | undefined, key: string): string | undefined {
  const value = input?.[key];
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function readNumber(input: Record<string, unknown> | undefined, key: string): number | undefined {
  const value = input?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function readPath(input: unknown, path: string[]): unknown {
  let current = input;
  for (const key of path) {
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

function isXhsFailureResponse(input: unknown): input is { success: false; msg: string } {
  if (!input || typeof input !== 'object') {
    return false;
  }

  const response = input as { success?: unknown; msg?: unknown };
  return response.success === false && typeof response.msg === 'string';
}
