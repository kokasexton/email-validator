const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string;
const ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

// All API calls go to the deployed Edge Function
const BASE = `${SUPABASE_URL}/functions/v1/validate`;

export interface ValidationResult {
  email: string;
  status: 'valid' | 'invalid' | 'accept_all' | 'unknown';
  score: number;
  failure_reason: string | null;
  regexp: boolean;
  gibberish: boolean;
  disposable: boolean;
  webmail: boolean;
  role_based: boolean;
  mx_records: boolean;
  smtp_check: boolean;
  accept_all: boolean;
  block: boolean;
  smtp_server: string | null;
  error: string | null;
}

export interface ValidationJob {
  id: string;
  job_type: 'single' | 'batch';
  status: string;
  total_emails: number;
  processed_emails: number;
  valid_count: number;
  invalid_count: number;
  accept_all_count: number;
  unknown_count: number;
  original_filename: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface BulkResponse {
  job_id: string;
  total: number;
  filename?: string;
  results: ValidationResult[];
  summary: { valid: number; invalid: number; accept_all: number; unknown: number };
}

const defaultHeaders = {
  'Authorization': `Bearer ${ANON_KEY}`,
  'apikey': ANON_KEY,
};

async function call<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      ...defaultHeaders,
      ...(opts?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  health: () => call<{ status: string }>('/health'),

  single: (email: string, skipSmtp = false) =>
    call<{ job_id: string; result: ValidationResult }>('/validate/single', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, skip_smtp: skipSmtp }),
    }),

  bulk: (emails: string[], skipSmtp = false) =>
    call<BulkResponse>('/validate/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ emails, skip_smtp: skipSmtp }),
    }),

  csv: (file: File, skipSmtp = false, emailColumn?: string) => {
    const form = new FormData();
    form.append('file', file);
    let path = `/validate/csv?skip_smtp=${skipSmtp}`;
    if (emailColumn) path += `&email_column=${encodeURIComponent(emailColumn)}`;
    return call<BulkResponse>(path, {
      method: 'POST',
      headers: { ...defaultHeaders },
      body: form,
    });
  },

  jobs: (limit = 20, offset = 0) =>
    call<{ jobs: ValidationJob[] }>(`/jobs?limit=${limit}&offset=${offset}`),

  job: (id: string) =>
    call<{ job: ValidationJob; results: ValidationResult[] }>(`/jobs/${id}`),

  downloadCsv: (jobId: string) => {
    const url = `${BASE}/jobs/${jobId}/download?apikey=${ANON_KEY}`;
    window.open(url, '_blank');
  },
};
