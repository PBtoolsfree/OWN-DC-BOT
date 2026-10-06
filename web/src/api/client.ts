/**
 * Centralized API Client with standard error transformation
 */

export class ApiError extends Error {
  status: number;
  data: any;
  detail: string;
  response?: { data: { detail: string; error?: string } };

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
    this.detail = message;
    this.response = { data: { detail: message, error: message } };
  }
}

const API_BASE = '/api/v1';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
  } catch (err: any) {
    throw new ApiError('Could not connect to server. Check network connection.', 0);
  }

  if (response.status === 401) {
    // Session expired or unauthorized
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login?error=session_expired';
    }
    throw new ApiError('Session expired. Please log in again.', 401);
  }

  if (response.status === 403) {
    throw new ApiError('Access denied: You do not have permission for this resource.', 403);
  }

  if (response.status === 429) {
    let msg = 'Rate limit exceeded. Please wait a moment.';
    try {
      const errJson = await response.json();
      if (errJson.detail) msg = errJson.detail;
    } catch (_) {
      // Ignore JSON parse error on 429
    }
    throw new ApiError(msg, 429);
  }

  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred.';
    let parsedData: any = null;
    try {
      const errJson = await response.json();
      parsedData = errJson;
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      } else if (errJson.message) {
        errorDetail = errJson.message;
      } else if (errJson.error) {
        errorDetail = errJson.error;
      }
    } catch (_) {
      errorDetail = `Request failed with status ${response.status}`;
    }
    throw new ApiError(errorDetail, response.status, parsedData);
  }

  // Handle 204 or empty response
  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  return response.text() as unknown as T;
}

export const apiClient = {
  get: <T>(endpoint: string, headers?: Record<string, string>) =>
    request<T>(endpoint, { method: 'GET', headers }),

  post: <T>(endpoint: string, data?: any, headers?: Record<string, string>) =>
    request<T>(endpoint, {
      method: 'POST',
      body: data !== undefined ? JSON.stringify(data) : undefined,
      headers,
    }),

  put: <T>(endpoint: string, data?: any, headers?: Record<string, string>) =>
    request<T>(endpoint, {
      method: 'PUT',
      body: data !== undefined ? JSON.stringify(data) : undefined,
      headers,
    }),

  delete: <T>(endpoint: string, headers?: Record<string, string>) =>
    request<T>(endpoint, { method: 'DELETE', headers }),
};
