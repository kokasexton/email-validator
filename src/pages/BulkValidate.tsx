import { useState, useRef, useCallback } from 'react';
import { Upload, FileText, X, Download, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../lib/api';
import type { ValidationResult, BulkResponse } from '../lib/api';
import { Badge } from '../components/Badge';
import { ScoreBar } from '../components/ScoreBar';
import { Spinner } from '../components/Spinner';
import s from './BulkValidate.module.css';

export function BulkValidate() {
  const [mode, setMode] = useState<'csv' | 'paste'>('csv');
  const [file, setFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState('');
  const [skipSmtp, setSkipSmtp] = useState(false);
  const [drag, setDrag] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<BulkResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f?.name.endsWith('.csv')) setFile(f);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null); setResp(null); setLoading(true);
    try {
      if (mode === 'csv' && file) {
        setResp(await api.csv(file, skipSmtp));
      } else {
        const emails = pasted.split(/[\n,;]+/).map(x => x.trim()).filter(Boolean);
        if (!emails.length) { setErr('No emails found.'); return; }
        if (emails.length > 500) { setErr('Paste mode supports up to 500 emails. Use CSV for more.'); return; }
        setResp(await api.bulk(emails, skipSmtp));
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={s.page}>
      <h1 className={s.title}>Bulk / CSV Validation</h1>
      <p className={s.sub}>Upload a CSV or paste emails — validate up to 10,000 at once with full SMTP checks</p>

      <div className={s.card}>
        <div className={s.tabs}>
          {(['csv', 'paste'] as const).map(m => (
            <button key={m} type="button"
              className={`${s.tab} ${mode === m ? s.activeTab : ''}`}
              onClick={() => setMode(m)}>
              {m === 'csv' ? <><FileText size={13} /> CSV Upload</> : <><Upload size={13} /> Paste Emails</>}
            </button>
          ))}
        </div>
        <form onSubmit={submit} className={s.form}>
          {mode === 'csv' ? (
            <div
              className={`${s.drop} ${drag ? s.dragging : ''} ${file ? s.hasFile : ''}`}
              onDragOver={e => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              onClick={() => fileRef.current?.click()}
            >
              <input ref={fileRef} type="file" accept=".csv" style={{ display: 'none' }} onChange={e => setFile(e.target.files?.[0] || null)} />
              {file ? (
                <div className={s.fileRow}>
                  <FileText size={18} className={s.fileIcon} />
                  <div><div className={s.fileName}>{file.name}</div><div className={s.fileSize}>{(file.size / 1024).toFixed(1)} KB</div></div>
                  <button type="button" className={s.clear} onClick={e => { e.stopPropagation(); setFile(null); }}><X size={13} /></button>
                </div>
              ) : (
                <div className={s.dropInner}>
                  <Upload size={26} className={s.dropIcon} />
                  <div className={s.dropText}>Drop CSV here or <span className={s.browse}>browse</span></div>
                  <div className={s.dropHint}>Auto-detects email column · Up to 10,000 rows</div>
                </div>
              )}
            </div>
          ) : (
            <textarea className={s.textarea} rows={7}
              placeholder="Paste emails one per line or comma-separated..."
              value={pasted} onChange={e => setPasted(e.target.value)} />
          )}
          <div className={s.formFoot}>
            <label className={s.check}>
              <input type="checkbox" checked={skipSmtp} onChange={e => setSkipSmtp(e.target.checked)} />
              Skip SMTP (DNS-only, much faster)
            </label>
            <button className={s.btn} disabled={loading || (mode === 'csv' ? !file : !pasted.trim())}>
              {loading ? <><Spinner size={13} /> Validating…</> : 'Start Validation'}
            </button>
          </div>
        </form>
      </div>

      {err && <div className={s.errCard}><strong>Error:</strong> {err}</div>}

      {resp && (
        <div className={`${s.results} anim-in`}>
          <div className={s.summary}>
            {([
              ['valid', resp.summary.valid, 'var(--success-500)'],
              ['invalid', resp.summary.invalid, 'var(--error-500)'],
              ['accept_all', resp.summary.accept_all, 'var(--warning-500)'],
              ['unknown', resp.summary.unknown, 'var(--neutral-400)'],
            ] as [string, number, string][]).map(([k, v, c]) => (
              <div key={k} className={s.sumCard}>
                <div className={s.sumNum} style={{ color: c }}>{v}</div>
                <div className={s.sumLbl}>{k.replace('_', ' ')}</div>
                <div className={s.sumBar}><div className={s.sumFill} style={{ width: resp.total > 0 ? `${(v / resp.total) * 100}%` : 0, background: c }} /></div>
              </div>
            ))}
          </div>

          <div className={s.tableHdr}>
            <div className={s.tableHdrL}>
              <span className={s.count}>{resp.total.toLocaleString()} results</span>
              {resp.filename && <span className={s.fname}>{resp.filename}</span>}
            </div>
            <button className={s.dlBtn} type="button" onClick={() => resp.job_id && api.downloadCsv(resp.job_id)}>
              <Download size={12} /> Export CSV
            </button>
          </div>

          <div className={s.tableBody}>
            <div className={s.thead}>
              <span>Email</span><span>Status</span><span>Score</span><span>Reason</span><span></span>
            </div>
            {resp.results.map((r, i) => (
              <div key={i}>
                <div className={s.trow} onClick={() => setExpanded(expanded === r.email ? null : r.email)}>
                  <span className={s.emailCell}>{r.email}</span>
                  <span><Badge status={r.status} sm /></span>
                  <span className={s.scoreCell}><ScoreBar score={r.score} /></span>
                  <span className={s.reasonCell}>{r.failure_reason?.replace(/_/g, ' ') || '—'}</span>
                  <span className={s.chevron}>{expanded === r.email ? <ChevronUp size={12} /> : <ChevronDown size={12} />}</span>
                </div>
                {expanded === r.email && <ExpandedRow result={r} />}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ExpandedRow({ result }: { result: ValidationResult }) {
  const flags = [
    { l: 'Syntax', v: result.regexp, ok: true },
    { l: 'Gibberish', v: result.gibberish, ok: false },
    { l: 'Disposable', v: result.disposable, ok: false },
    { l: 'Role-based', v: result.role_based, ok: false },
    { l: 'Webmail', v: result.webmail, neutral: true },
    { l: 'MX Records', v: result.mx_records, ok: true },
    { l: 'SMTP', v: result.smtp_check, ok: true },
    { l: 'Accept-all', v: result.accept_all, neutral: true },
    { l: 'Blocked', v: result.block, ok: false },
  ];
  return (
    <div className={s.expanded}>
      {flags.map(f => {
        const cls = f.neutral ? (f.v ? s.fWarn : s.fOk) : (f.ok ? (f.v ? s.fOk : s.fFail) : (f.v ? s.fFail : s.fOk));
        return <span key={f.l} className={`${s.flag} ${cls}`}>{f.l}: {f.v ? 'yes' : 'no'}</span>;
      })}
    </div>
  );
}
