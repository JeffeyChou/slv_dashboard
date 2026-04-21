export interface Logger {
  info(message: string, metadata?: Record<string, unknown>): void;
  error(message: string, metadata?: Record<string, unknown>): void;
}

export type LogEntry = {
  level: 'info' | 'error';
  message: string;
  metadata: Record<string, unknown> | undefined;
};

export class InMemoryLogger implements Logger {
  public readonly entries: LogEntry[] = [];

  info(message: string, metadata?: Record<string, unknown>): void {
    this.entries.push({ level: 'info', message, metadata });
  }

  error(message: string, metadata?: Record<string, unknown>): void {
    this.entries.push({ level: 'error', message, metadata });
  }
}
