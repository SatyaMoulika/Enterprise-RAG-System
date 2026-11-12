import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError } from './client';
const json = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
afterEach(() => vi.restoreAllMocks());
describe('HTTP boundary', () => {
  it('sends bearer credentials only in the header and omits cookies', async () => {
    const fetcher = vi.fn().mockResolvedValue(json([]));
    vi.stubGlobal('fetch', fetcher);
    await new ApiClient('secret-token').documents();
    const [path, options] = fetcher.mock.calls[0];
    expect(path).toBe('/api/documents/list');
    expect(options.headers.get('Authorization')).toBe('Bearer secret-token');
    expect(options.credentials).toBe('omit');
    expect(path).not.toContain('secret-token');
  });
  it('lets the browser supply the multipart boundary', async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ id: 1, title: 'policy.txt' }));
    vi.stubGlobal('fetch', fetcher);
    await new ApiClient('token').upload(new File(['content'], 'policy.txt'));
    const options = fetcher.mock.calls[0][1];
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.headers.has('Content-Type')).toBe(false);
  });
  it('expires an authenticated session on 401 but not a failed login', async () => {
    const expired = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => Promise.resolve(json({ detail: 'Expired' }, 401))),
    );
    await expect(new ApiClient('token', expired).documents()).rejects.toMatchObject({
      status: 401,
    });
    expect(expired).toHaveBeenCalledTimes(1);
    await expect(
      new ApiClient(undefined, expired).login('x@example.com', 'wrong'),
    ).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledTimes(1);
  });
  it('shows validation messages without echoing raw server input', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          json({ detail: [{ msg: 'Password is too short', input: 'private-password' }] }, 422),
        ),
    );
    await expect(new ApiClient().login('x@example.com', 'short')).rejects.toThrow(
      'Password is too short',
    );
  });
  it('does not automatically retry a mutation after a lost connection', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('network failed'));
    vi.stubGlobal('fetch', fetcher);
    await expect(new ApiClient('token').removeDocument(4)).rejects.toMatchObject({
      uncertain: true,
      status: 0,
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('distinguishes a deliberate abort from a failed request', async () => {
    const abort = new AbortController();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        (_url, options) =>
          new Promise((_resolve, reject) => {
            options.signal.addEventListener('abort', () =>
              reject(new DOMException('Aborted', 'AbortError')),
            );
          }),
      ),
    );
    const result = new ApiClient().documents(abort.signal);
    abort.abort();
    await expect(result).rejects.toMatchObject({ name: 'AbortError' });
  });
  it('times out a mutation with an uncertain-result warning', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation(
          (_url, options) =>
            new Promise((_resolve, reject) =>
              options.signal.addEventListener('abort', () =>
                reject(new DOMException('Aborted', 'AbortError')),
              ),
            ),
        ),
    );
    const request = new ApiClient('token', undefined, 10).removeDocument(1);
    const expected = expect(request).rejects.toMatchObject({ uncertain: true, status: 0 });
    await vi.advanceTimersByTimeAsync(11);
    await expected;
  });
  it('treats unreadable successful mutation responses as uncertain', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not json', { status: 200 })));
    await expect(new ApiClient('token').removeDocument(1)).rejects.toBeInstanceOf(ApiError);
  });
});
it('marks gateway failures on mutations as uncertain', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('Gateway timeout', { status: 504 })),
  );
  await expect(new ApiClient('token').removeDocument(1)).rejects.toMatchObject({
    uncertain: true,
    status: 504,
  });
});
