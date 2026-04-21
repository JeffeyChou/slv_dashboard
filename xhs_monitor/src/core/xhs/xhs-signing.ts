import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { createContext, runInContext } from 'node:vm';

import type { XhsRequestSigner } from './types.js';

type SpiderSignerExport = {
  get_request_headers_params?: (
    apiPath: string,
    body: unknown,
    a1: string,
    method: 'GET' | 'POST'
  ) => {
    xs?: unknown;
    xt?: unknown;
    xs_common?: unknown;
  };
};

export class SpiderXhsScriptSigner implements XhsRequestSigner {
  private loadedScript: Promise<SpiderSignerExport> | undefined;

  constructor(private readonly scriptPath: string) {}

  async sign(input: {
    apiPath: string;
    body?: unknown;
    method: 'GET' | 'POST';
    cookie: string;
  }): Promise<Record<string, string>> {
    const a1 = parseCookieValue(input.cookie, 'a1');
    if (!a1) {
      throw new Error('XHS cookie is missing required a1 value for request signing');
    }

    const signer = await this.loadScript();
    const signFn = signer.get_request_headers_params;
    if (!signFn) {
      throw new Error('XHS signer script does not export get_request_headers_params');
    }

    const signed = signFn(input.apiPath, input.body ?? '', a1, input.method);
    if (typeof signed.xs !== 'string' || typeof signed.xt !== 'number' || typeof signed.xs_common !== 'string') {
      throw new Error('XHS signer script returned an invalid signature payload');
    }

    return {
      'x-s': signed.xs,
      'x-t': String(signed.xt),
      'x-s-common': signed.xs_common
    };
  }

  private loadScript(): Promise<SpiderSignerExport> {
    this.loadedScript = this.loadedScript ?? loadSpiderSignerScript(this.scriptPath);
    return this.loadedScript;
  }
}

export function parseCookieValue(cookie: string, key: string): string | undefined {
  for (const part of cookie.split(';')) {
    const separatorIndex = part.indexOf('=');
    if (separatorIndex < 1) {
      continue;
    }

    const name = part.slice(0, separatorIndex).trim();
    if (name === key) {
      return part.slice(separatorIndex + 1).trim();
    }
  }

  return undefined;
}

async function loadSpiderSignerScript(scriptPath: string): Promise<SpiderSignerExport> {
  const source = await readFile(scriptPath, 'utf8');
  const module = { exports: {} as SpiderSignerExport };
  const context: Record<string, unknown> = {
    module,
    exports: module.exports,
    require: createSignerRequire(),
    console: {
      log() {},
      warn() {},
      error() {},
      info() {},
      debug() {}
    },
    Date,
    Math,
    Array,
    Set,
    Function,
    RegExp,
    Object,
    JSON,
    Error,
    String,
    Symbol,
    Proxy,
    Reflect,
    Uint8Array,
    TextEncoder,
    performance: globalThis.performance,
    encodeURIComponent,
    unescape,
    parseInt
  };
  context.global = context;
  context.globalThis = context;
  context.window = context;

  runInContext(source, createContext(context), {
    timeout: 5000,
    filename: scriptPath
  });

  return module.exports;
}

function createSignerRequire(): ((id: string) => unknown) & { main?: unknown } {
  const requireFn = ((id: string) => {
    if (id === 'crypto-js') {
      return {
        MD5(value: unknown) {
          return {
            toString() {
              return createHash('md5').update(String(value)).digest('hex');
            }
          };
        }
      };
    }

    throw new Error(`Unsupported XHS signer script require: ${id}`);
  }) as ((id: string) => unknown) & { main?: unknown };

  requireFn.main = undefined;
  return requireFn;
}
