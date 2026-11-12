import type {
  Answer,
  Member,
  CreateMemberPayload,
  DocumentLimits,
  DocumentRecord,
  RegisterPayload,
  TokenResponse,
  User,
} from './types';
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public uncertain = false,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
export const isCancelled = (error: unknown) =>
  error instanceof DOMException && error.name === 'AbortError';
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}
function detailMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail))
    return detail
      .map((item) => (typeof item?.msg === 'string' ? item.msg : 'Invalid input'))
      .join('; ');
  return undefined;
}
export class ApiClient {
  constructor(
    private token?: string,
    private onUnauthorized?: () => void,
    private timeoutMs = 120_000,
  ) {}
  private async request<T>(
    path: string,
    options: { method?: string; body?: unknown; signal?: AbortSignal } = {},
  ): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const relay = () => controller.abort();
    options.signal?.addEventListener('abort', relay, { once: true });
    if (options.signal?.aborted) controller.abort();
    const headers = new Headers();
    if (this.token) headers.set('Authorization', `Bearer ${this.token}`);
    const form = options.body instanceof FormData;
    if (options.body !== undefined && !form) headers.set('Content-Type', 'application/json');
    try {
      const response = await fetch(`/api${path}`, {
        method: options.method || 'GET',
        headers,
        body:
          options.body === undefined
            ? undefined
            : form
              ? (options.body as FormData)
              : JSON.stringify(options.body),
        signal: controller.signal,
        credentials: 'omit',
      });
      const payload: unknown = await response.json().catch(() => null);
      if (options.signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
      if (!response.ok) {
        if (response.status === 401 && this.token) this.onUnauthorized?.();
        const uncertain =
          !!options.method &&
          options.method !== 'GET' &&
          response.status >= 500 &&
          response.status !== 503;
        const fallback = uncertain
          ? 'The service could not confirm the result. Refresh before trying again.'
          : response.status === 503
            ? 'The service is temporarily unavailable. Try again later.'
            : `Request failed (${response.status}).`;
        throw new ApiError(
          detailMessage(
            payload && typeof payload === 'object' && 'detail' in payload
              ? payload.detail
              : undefined,
          ) || fallback,
          response.status,
          uncertain,
        );
      }
      if (payload === null)
        throw new ApiError(
          'The server returned an unreadable response. Refresh before trying the action again.',
          response.status,
          true,
        );
      return payload as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (options.signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
      const mutation = options.method && options.method !== 'GET';
      if (controller.signal.aborted)
        throw new ApiError(
          mutation
            ? 'The request timed out and may have completed. Refresh the list before trying again.'
            : 'The request timed out. Please try refreshing.',
          0,
          !!mutation,
        );
      throw new ApiError(
        mutation
          ? 'The connection was lost and the result is uncertain. Refresh before trying again.'
          : 'Could not reach the service. Check your connection and try refreshing.',
        0,
        !!mutation,
      );
    } finally {
      clearTimeout(timer);
      options.signal?.removeEventListener('abort', relay);
    }
  }
  login(email: string, password: string, signal?: AbortSignal) {
    return this.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
      signal,
    });
  }
  register(body: RegisterPayload, signal?: AbortSignal) {
    return this.request<TokenResponse>('/auth/register', { method: 'POST', body, signal });
  }
  me(signal?: AbortSignal) {
    return this.request<User>('/users/me', { signal });
  }
  documents(signal?: AbortSignal) {
    return this.request<DocumentRecord[]>('/documents/list', { signal });
  }
  limits(signal?: AbortSignal) {
    return this.request<DocumentLimits>('/documents/limits', { signal });
  }
  upload(file: File, signal?: AbortSignal) {
    const body = new FormData();
    body.append('file', file);
    return this.request<DocumentRecord>('/documents/upload', { method: 'POST', body, signal });
  }
  removeDocument(id: number, signal?: AbortSignal) {
    return this.request<{ message: string }>(`/documents/${id}`, { method: 'DELETE', signal });
  }
  members(signal?: AbortSignal) {
    return this.request<Member[]>('/users/get_all_users', { signal });
  }
  createMember(body: CreateMemberPayload, signal?: AbortSignal) {
    return this.request<Member>('/users/create_user', { method: 'POST', body, signal });
  }
  removeMember(id: number, signal?: AbortSignal) {
    return this.request<{ message: string }>(`/users/delete_user/${id}`, {
      method: 'DELETE',
      signal,
    });
  }
  ask(question: string, signal?: AbortSignal) {
    return this.request<Answer>('/chat/generate', { method: 'POST', body: { question }, signal });
  }
}
