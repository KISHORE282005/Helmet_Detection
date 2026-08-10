/** Thin fetch wrapper. Every call funnels through `request` so error handling
 *  and JSON decoding live in one place. */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) {
        detail = Array.isArray(body.detail)
          ? body.detail.map((d: { msg?: string }) => d.msg ?? String(d)).join(', ')
          : String(body.detail);
      }
    } catch {
      /* the body was not JSON — keep the status line */
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) => {
    const query = params
      ? Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== null && v !== '')
          .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
          .join('&')
      : '';
    return request<T>(query ? `${path}?${query}` : path);
  },
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, file: File, onProgress?: (fraction: number) => void) =>
    new Promise<T>((resolve, reject) => {
      // XHR rather than fetch: upload progress matters for multi-hundred-MB
      // CCTV files and fetch cannot report it.
      const form = new FormData();
      form.append('file', file);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', path);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) onProgress(event.loaded / event.total);
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText) as T);
        } else {
          let detail = `${xhr.status} ${xhr.statusText}`;
          try {
            detail = JSON.parse(xhr.responseText).detail ?? detail;
          } catch {
            /* keep the status line */
          }
          reject(new ApiError(xhr.status, detail));
        }
      };
      xhr.onerror = () => reject(new ApiError(0, 'Network error during upload'));
      xhr.send(form);
    }),
};

/** Media is served through the API so paths stay confined to output/. */
export const mediaUrl = (kind: 'evidence' | 'poster' | 'report', name: string, download = false) =>
  `/api/media/${kind}/${encodeURIComponent(name)}${download ? '?download=true' : ''}`;

export const reportExportUrl = (
  period: string,
  format: 'xlsx' | 'csv' | 'pdf',
  anchor?: string,
) => `/api/reports/${period}/export?format=${format}${anchor ? `&anchor=${anchor}` : ''}`;
