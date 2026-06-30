/**
 * API client with JWT token management and error handling.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getToken(): string | null {
  return localStorage.getItem('access_token');
}

function setTokens(access: string, refresh: string): void {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

function clearTokens(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

async function refreshToken(): Promise<boolean> {
  const refresh = localStorage.getItem('refresh_token');
  if (!refresh) return false;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && retry) {
    const refreshed = await refreshToken();
    if (refreshed) {
      return request<T>(path, options, false);
    }
    clearTokens();
    window.location.href = '/login';
    throw new ApiError(401, 'Session expired');
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const data = await res.json();

  if (!res.ok) {
    throw new ApiError(res.status, data.detail || 'Request failed');
  }

  return data as T;
}

/* ── Auth ───────────────────────────────────────────────────── */

import type {
  TokenResponse,
  User,
  ActSummary,
  SectionDetail,
  SectionSummary,
  SearchResponse,
  ChatResponse,
  ConversationSummary,
  ConversationDetail,
  SearchHistoryItem,
} from '../types';

export const authApi = {
  register: (email: string, password: string, full_name: string) =>
    request<User>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    }),

  login: async (email: string, password: string) => {
    const data = await request<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setTokens(data.access_token, data.refresh_token);
    return data;
  },

  logout: () => {
    clearTokens();
  },

  me: () => request<User>('/api/v1/auth/me'),
};

/* ── Acts ───────────────────────────────────────────────────── */

export const actsApi = {
  list: () => request<ActSummary[]>('/api/v1/acts'),

  get: (slug: string) => request<ActSummary & { sections: SectionSummary[] }>(
    `/api/v1/acts/${slug}`,
  ),

  getSection: (slug: string, number: string) =>
    request<SectionDetail>(`/api/v1/acts/${slug}/sections/${number}`),
};

/* ── Search ─────────────────────────────────────────────────── */

export const searchApi = {
  search: (query: string, act_filter?: string, top_k = 8) =>
    request<SearchResponse>('/api/v1/search', {
      method: 'POST',
      body: JSON.stringify({ query, act_filter, top_k }),
    }),

  history: () => request<SearchHistoryItem[]>('/api/v1/search/history'),
};

/* ── Chat ───────────────────────────────────────────────────── */

export const chatApi = {
  send: (message: string, conversation_id?: string) =>
    request<ChatResponse>('/api/v1/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id }),
    }),

  conversations: () =>
    request<ConversationSummary[]>('/api/v1/chat/conversations'),

  conversation: (id: string) =>
    request<ConversationDetail>(`/api/v1/chat/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<void>(`/api/v1/chat/conversations/${id}`, { method: 'DELETE' }),
};

export { getToken, setTokens, clearTokens };
