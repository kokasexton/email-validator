import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import s from './ApiDocs.module.css';

const BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';

function CopyBtn({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button className={s.copy} onClick={() => { navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1600); }}>
      {ok ? <Check size={11} /> : <Copy size={11} />}
    </button>
  );
}

function Block({ label, code }: { label: string; code: string }) {
  return (
    <div className={s.block}>
      {label && <div className={s.blockLbl}>{label}</div>}
      <div className={s.codeWrap}><pre className={s.code}>{code}</pre><CopyBtn text={code} /></div>
    </div>
  );
}

function Endpoint({ method, path, desc, req, res, notes }: {
  method: 'GET' | 'POST'; path: string; desc: string;
  req?: string; res: string; notes?: string[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className={s.ep}>
      <button className={s.epHdr} onClick={() => setOpen(o => !o)}>
        <span className={`${s.method} ${s[method.toLowerCase() as 'get' | 'post']}`}>{method}</span>
        <span className={s.path}>{path}</span>
        <span className={s.desc}>{desc}</span>
        <span className={s.tog}>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className={s.epBody}>
          {notes?.map((n, i) => <p key={i} className={s.note}>{n}</p>)}
          {req && <Block label="Request Body (JSON)" code={req} />}
          <Block label="Response (JSON)" code={res} />
        </div>
      )}
    </div>
  );
}

export function ApiDocs() {
  return (
    <div className={s.page}>
      <h1 className={s.title}>API Reference</h1>
      <p className={s.sub}>Integrate email validation into any app via REST. Base URL: <code className={s.ic}>{BASE}</code></p>

      <div className={s.section}>
        <div className={s.sectionTitle}>Quick Start</div>
        <Block label="Validate single email" code={`curl -X POST ${BASE}/api/validate/single \\\n  -H "Content-Type: application/json" \\\n  -d '{"email": "user@example.com"}'`} />
        <Block label="Validate bulk emails" code={`curl -X POST ${BASE}/api/validate/bulk \\\n  -H "Content-Type: application/json" \\\n  -d '{"emails": ["a@example.com", "b@example.com"]}'`} />
        <Block label="Upload CSV file" code={`curl -X POST ${BASE}/api/validate/csv -F "file=@leads.csv"`} />
      </div>

      <div className={s.section}>
        <div className={s.sectionTitle}>Endpoints</div>
        <Endpoint method="GET" path="/api/health" desc="Health check"
          res={`{ "status": "ok", "version": "2.0.0" }`} />
        <Endpoint method="POST" path="/api/validate/single" desc="Validate one email"
          req={`{ "email": "user@example.com", "skip_smtp": false }`}
          res={`{\n  "job_id": "uuid",\n  "result": {\n    "email": "user@example.com",\n    "status": "valid",\n    "score": 90,\n    "failure_reason": null,\n    "regexp": true, "gibberish": false,\n    "disposable": false, "webmail": false, "role_based": false,\n    "mx_records": true, "smtp_check": true,\n    "accept_all": false, "block": false,\n    "smtp_server": "mail.example.com"\n  }\n}`} />
        <Endpoint method="POST" path="/api/validate/bulk" desc="Validate up to 500 emails (JSON)"
          req={`{ "emails": ["a@example.com", "b@test.com"], "skip_smtp": false }`}
          res={`{ "job_id": "uuid", "total": 2, "results": [...],\n  "summary": { "valid": 1, "invalid": 1, "accept_all": 0, "unknown": 0 } }`}
          notes={['Maximum 500 emails. Use CSV upload for larger batches.']} />
        <Endpoint method="POST" path="/api/validate/csv" desc="Upload CSV (multipart/form-data)"
          res={`{ "job_id": "uuid", "total": 500, "filename": "leads.csv",\n  "results": [...], "summary": { ... } }`}
          notes={['Field: file — .csv file required.', 'Query: skip_smtp=true — skip SMTP checks.', 'Query: email_column=<name> — override auto-detection.', 'Max 10,000 rows.']} />
        <Endpoint method="GET" path="/api/validate/csv/{job_id}/download" desc="Download results as CSV"
          res={`email,status,score,...\nuser@example.com,valid,90,...`}
          notes={['Returns CSV file attachment.']} />
        <Endpoint method="GET" path="/api/jobs" desc="List recent jobs (params: limit, offset)"
          res={`{ "jobs": [{ "id": "uuid", "job_type": "batch", "total_emails": 100, ... }] }`} />
        <Endpoint method="GET" path="/api/jobs/{job_id}" desc="Get job + all results"
          res={`{ "job": { ... }, "results": [ ... ] }`} />
      </div>

      <div className={s.section}>
        <div className={s.sectionTitle}>Status Values</div>
        <div className={s.statusGrid}>
          {[
            { v: 'valid', d: 'Passed all checks including SMTP handshake.', bg: 'var(--success-50)', c: 'var(--success-700)' },
            { v: 'invalid', d: 'Failed a hard check (bad syntax, domain not found, SMTP rejected).', bg: 'var(--error-50)', c: 'var(--error-600)' },
            { v: 'accept_all', d: 'Domain accepts all mail — mailbox existence unconfirmed.', bg: 'var(--warning-50)', c: 'var(--warning-600)' },
            { v: 'unknown', d: 'SMTP inconclusive due to timeout or transient error.', bg: 'var(--neutral-100)', c: 'var(--neutral-500)' },
          ].map(x => (
            <div key={x.v} className={s.statusCard} style={{ background: x.bg }}>
              <code className={s.statusCode} style={{ color: x.c }}>{x.v}</code>
              <p className={s.statusDesc}>{x.d}</p>
            </div>
          ))}
        </div>
      </div>

      <div className={s.section}>
        <div className={s.sectionTitle}>Score (0–100)</div>
        <div className={s.scoreRows}>
          {[
            ['+20', 'Valid syntax'], ['+10', 'Not gibberish'], ['+10', 'Not disposable'],
            ['+20', 'MX records found'], ['+30', 'SMTP verified'], ['+10', 'Not blocked'],
            ['−10', 'Accept-all domain penalty'],
          ].map(([pts, lbl]) => (
            <div key={lbl} className={s.scoreRow}>
              <code className={`${s.pts} ${pts.startsWith('+') ? s.pos : s.neg}`}>{pts}</code>
              <span>{lbl}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
