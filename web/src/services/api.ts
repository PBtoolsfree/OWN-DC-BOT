const API_BASE = '/api';

async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(\`\${API_BASE}\${endpoint}\`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'x-csrf-token': '1', // Required by our CSRF protection
      ...options.headers,
    },
  });

  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (response.status === 403) {
    window.location.href = '/login?error=forbidden';
    throw new Error('Forbidden');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || 'An API error occurred');
  }

  return response.json();
}

export const api = {
  get: (endpoint: string) => fetchApi(endpoint),
  post: (endpoint: string, data: any) => fetchApi(endpoint, { method: 'POST', body: JSON.stringify(data) }),
  patch: (endpoint: string, data: any) => fetchApi(endpoint, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (endpoint: string) => fetchApi(endpoint, { method: 'DELETE' }),
};
