import type { XhsNoteSummary, XhsWebhookPublisher } from './types.js';

export type XhsDiscordWebhookPayload = {
  content: string;
  embeds: Array<Record<string, unknown>>;
  allowed_mentions: { parse: string[] };
};

const DISCORD_WEBHOOK_BASE = 'https://discord.com/api/v10/webhooks';
const MAX_CONTENT_LENGTH = 1800;
const MAX_FIELD_LENGTH = 1024;

export class XhsDiscordWebhookPublisher implements XhsWebhookPublisher {
  constructor(
    private readonly webhookUrl: string,
    private readonly fetchImpl: typeof fetch = fetch
  ) {}

  async publish(note: XhsNoteSummary): Promise<void> {
    const response = await this.fetchImpl(this.webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(buildXhsDiscordWebhookPayload(note))
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(redactWebhookSecret(`Discord webhook failed: ${response.status} ${text}`, this.webhookUrl));
    }
  }
}

export function buildXhsDiscordWebhookUrl(id: string, token: string): string {
  return `${DISCORD_WEBHOOK_BASE}/${encodeURIComponent(id)}/${encodeURIComponent(token)}`;
}

export function buildXhsDiscordWebhookPayload(note: XhsNoteSummary): XhsDiscordWebhookPayload {
  const title = truncate(note.title || `XHS note ${note.id}`, 256);
  const description = note.excerpt ? truncate(note.excerpt, MAX_FIELD_LENGTH) : undefined;
  const embed: Record<string, unknown> = {
    title,
    url: note.url,
    color: 0xff2442,
    fields: [
      {
        name: 'User',
        value: truncate(note.authorName ? `${note.authorName} (${note.userId})` : note.userId, 256),
        inline: true
      },
      {
        name: 'Note ID',
        value: note.id,
        inline: true
      }
    ]
  };

  if (description) {
    embed.description = description;
  }

  if (note.publishedAt) {
    embed.timestamp = note.publishedAt;
  }

  const imageUrl = note.imageUrls?.find(Boolean);
  if (imageUrl) {
    embed.thumbnail = { url: imageUrl };
  }

  return {
    content: truncate(`New Xiaohongshu post: ${title}\n${note.url}`, MAX_CONTENT_LENGTH),
    embeds: [embed],
    allowed_mentions: { parse: [] }
  };
}

export function redactWebhookSecret(message: string, webhookUrl: string): string {
  try {
    const parsed = new URL(webhookUrl);
    const parts = parsed.pathname.split('/');
    const token = parts[parts.length - 1];
    if (token) {
      return message.split(token).join('[redacted-webhook-token]').split(webhookUrl).join('[redacted-webhook-url]');
    }
  } catch {
    return message.split(webhookUrl).join('[redacted-webhook-url]');
  }

  return message.split(webhookUrl).join('[redacted-webhook-url]');
}

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, Math.max(0, maxLength - 3))}...`;
}
