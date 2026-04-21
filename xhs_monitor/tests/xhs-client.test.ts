import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildXhsBaseHeaders,
  buildXhsNoteUrl,
  mergeXhsNoteDetail,
  normalizeXhsUserPostedResponse,
  redactXhsCookie,
  XhsPcFeedClient
} from '../src/core/xhs/xhs-client.js';
import type { XhsRequestSigner } from '../src/core/xhs/types.js';

test('normalizeXhsUserPostedResponse maps user_posted fixtures to note summaries', () => {
  const notes = normalizeXhsUserPostedResponse(
    {
      success: true,
      data: {
        notes: [
          {
            note_id: 'note-1',
            display_title: 'Title',
            xsec_token: 'xsec',
            xsec_source: 'pc_user',
            cover: {
              url: 'https://cdn.example.test/cover.jpg'
            },
            user: {
              user_id: 'user-a',
              nickname: 'Author'
            }
          }
        ]
      }
    },
    'fallback-user'
  );

  assert.equal(notes.length, 1);
  assert.deepEqual(notes[0], {
    id: 'note-1',
    userId: 'user-a',
    title: 'Title',
    url: 'https://www.xiaohongshu.com/explore/note-1?xsec_token=xsec&xsec_source=pc_user',
    authorName: 'Author',
    imageUrls: ['https://cdn.example.test/cover.jpg'],
    xsecToken: 'xsec',
    xsecSource: 'pc_user'
  });
});

test('mergeXhsNoteDetail enriches note summaries without changing identity', () => {
  const merged = mergeXhsNoteDetail(
    {
      id: 'note-1',
      userId: 'user-a',
      title: 'Original',
      url: 'https://www.xiaohongshu.com/explore/note-1'
    },
    {
      data: {
        items: [
          {
            id: 'note-1',
            note_card: {
              title: 'Detailed',
              desc: 'Detailed body',
              time: 1776470400,
              image_list: [{ url: 'https://cdn.example.test/detail.jpg' }],
              user: { nickname: 'Author' }
            }
          }
        ]
      }
    }
  );

  assert.equal(merged.id, 'note-1');
  assert.equal(merged.userId, 'user-a');
  assert.equal(merged.url, 'https://www.xiaohongshu.com/explore/note-1');
  assert.equal(merged.title, 'Detailed');
  assert.equal(merged.excerpt, 'Detailed body');
  assert.deepEqual(merged.imageUrls, ['https://cdn.example.test/detail.jpg']);
});

test('XhsPcFeedClient sends signed user_posted requests and normalizes response', async () => {
  const signer: XhsRequestSigner = {
    async sign(input) {
      assert.match(input.apiPath, /\/api\/sns\/web\/v1\/user_posted/);
      return {
        'x-s': 'xs',
        'x-t': '1776470400000',
        'x-s-common': 'common'
      };
    }
  };
  const requests: Array<{ url: string; headers: Record<string, string> }> = [];
  const fetchImpl = (async (url: string | URL | Request, init?: RequestInit) => {
    requests.push({
      url: String(url),
      headers: init?.headers as Record<string, string>
    });
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          success: true,
          data: {
            notes: [
              {
                note_id: 'note-1',
                display_title: 'Title'
              }
            ]
          }
        };
      },
      async text() {
        return '';
      }
    } as Response;
  }) as typeof fetch;
  const client = new XhsPcFeedClient(
    {
      cookie: 'a1=abc; web_session=session',
      requestTimeoutMs: 15_000,
      apiProfile: 'xiaohongshu',
      apiBase: 'https://xhs.example.test',
      webBase: 'https://www.xiaohongshu.example.test'
    },
    {
      apiBase: 'https://xhs.example.test',
      signer,
      fetchImpl
    }
  );

  const notes = await client.listRecentPosts('user-a', 5);

  assert.equal(requests.length, 1);
  assert.match(requests[0]?.url ?? '', /user_posted/);
  assert.equal(requests[0]?.headers.cookie, 'a1=abc; web_session=session');
  assert.equal(requests[0]?.headers['x-s'], 'xs');
  assert.equal(notes[0]?.id, 'note-1');
});

test('buildXhsBaseHeaders includes cookie and trace headers', () => {
  const headers = buildXhsBaseHeaders('a1=abc');

  assert.equal(headers.cookie, 'a1=abc');
  assert.equal(Boolean(headers['x-b3-traceid']), true);
  assert.equal(Boolean(headers['x-xray-traceid']), true);
});

test('buildXhsNoteUrl and redactXhsCookie handle sensitive values', () => {
  assert.equal(
    buildXhsNoteUrl('note-1', 'xsec-token', 'pc_user'),
    'https://www.xiaohongshu.com/explore/note-1?xsec_token=xsec-token&xsec_source=pc_user'
  );
  assert.equal(redactXhsCookie('failed a1=abc', 'a1=abc'), 'failed [redacted-xhs-cookie]');
});

test('XhsPcFeedClient rednote profile fallback reports display-id style failures clearly', async () => {
  const fetchImpl = (async (url: string | URL | Request) => {
    if (String(url).includes('/api/sns/web/v1/user_posted')) {
      return {
        ok: false,
        status: 406,
        async text() {
          return '{"code":-1,"success":false}';
        }
      } as Response;
    }

    return {
      ok: false,
      status: 404,
      async text() {
        return '<script>window.__INITIAL_STATE__={"user":{"notes":[[],[],[],[],[]]}}</script>';
      }
    } as Response;
  }) as typeof fetch;
  const client = new XhsPcFeedClient(
    {
      cookie: 'a1=abc; web_session=session',
      requestTimeoutMs: 15_000,
      apiProfile: 'rednote',
      apiBase: 'https://webapi.rednote.example.test',
      webBase: 'https://www.rednote.example.test'
    },
    { fetchImpl }
  );

  await assert.rejects(() => client.listRecentPosts('display-id', 5), /internal \/user\/profile\/<id>/);
});
