declare module 'node:test' {
  const test: (name: string, fn: () => unknown | Promise<unknown>) => void;
  export default test;
}

declare module 'node:assert/strict' {
  const assert: {
    equal(actual: unknown, expected: unknown, message?: string): void;
    deepEqual(actual: unknown, expected: unknown, message?: string): void;
    match(value: string, regexp: RegExp, message?: string): void;
    throws(fn: () => unknown, error?: RegExp | ((error: unknown) => boolean)): void;
    rejects(fn: () => Promise<unknown>, error?: RegExp | ((error: unknown) => boolean)): Promise<void>;
  };
  export default assert;
}

declare module 'node:crypto' {
  export function randomUUID(): string;
  export function createHash(algorithm: string): {
    update(input: string): ReturnType<typeof createHash>;
    digest(encoding: 'hex'): string;
  };
}

declare module 'node:buffer' {
  export const Buffer: {
    from(input: ArrayBuffer | string, encoding?: string): Buffer;
    isBuffer(input: unknown): boolean;
    concat(chunks: Buffer[]): Buffer;
  };
}

declare module 'zlib' {
  export function inflateSync(input: Buffer): Buffer;
  export function createInflate(): {
    on(event: 'data', listener: (chunk: Buffer) => void): void;
    once(event: 'error', listener: (error: Error) => void): void;
    off(event: 'error', listener: (error: Error) => void): void;
    write(input: Buffer, callback?: (error?: Error | null) => void): void;
  };
}


declare module 'node:fs/promises' {
  export function readFile(path: string, encoding: string): Promise<string>;
  export function writeFile(path: string, data: string, encoding: string): Promise<void>;
  export function mkdir(path: string, options?: { recursive?: boolean }): Promise<string | undefined>;
  export function rename(oldPath: string, newPath: string): Promise<void>;
}

declare module 'node:path' {
  export function dirname(path: string): string;
}

declare namespace NodeJS {
  interface ProcessEnv {
    [key: string]: string | undefined;
  }
}

declare const process: {
  argv: string[];
  env: NodeJS.ProcessEnv;
  platform: string;
  pid: number;
  exitCode?: number;
};

declare module 'node:vm' {
  export function createContext(contextObject: Record<string, unknown>): Record<string, unknown>;
  export function runInContext(
    code: string,
    contextifiedObject: Record<string, unknown>,
    options?: { timeout?: number; filename?: string }
  ): unknown;
}


declare module 'ws' {
  export type RawData = string | Buffer | ArrayBuffer | Buffer[];
  export default class WebSocket {
    constructor(url: string);
    send(data: string): void;
    on(event: 'message', listener: (data: RawData, isBinary: boolean) => void): void;
    on(event: 'close', listener: (code: number, reason: Buffer) => void): void;
    on(event: 'error', listener: (error: Error) => void): void;
  }
}

type Buffer = {
  toString(): string;
  length: number;
  subarray(start: number, end?: number): Buffer;
  equals(other: Buffer): boolean;
};
