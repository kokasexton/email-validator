import { useEffect, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Download, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import type { ValidationJob, ValidationResult } from '../lib/api';
import { Badge } from '../components/Badge';
import { ScoreBar } from '../components/ScoreBar';
import { Spinner } from '../components/Spinner';
import s from './History.module.css';

export function History() {
  const { jobId } = useParams();
  return jobId ? <JobDetail jobId={jobId} /> : <JobList />;
}

function JobList() {
  const [jobs, setJobs] = useState<ValidationJob[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => { setLoading(true); api.jobs(50).then(r => setJobs(r.jobs)).finally(() => setLoading(false)); };
  useEffect(load, []);

  return (
    <div className={s.page}>
      <div className={s.hdr}>
        <div><h1 className={s.title}>Validation History</h1><p className={s.sub}>All jobs, newest first</p></div>
        <button className={s.refresh} onClick={load} disabled={loading}>
          <RefreshCw size={13} className={loading ? s.spin : ''} /> Refresh
        </button>
      </div>

      <div className={s.tableCard}>
        {loading ? (
          <div className={s.center}><Spinner /> Loading…</div>
        ) : jobs.length === 0 ? (
          <div className={s.center}>No history yet.</div>
        ) : (
          <>
            <div className={s.thead}>
              <span>ID</span><span>Type</span><span>File</span><span>Total</span><span>Valid</span><span>Invalid</span><span>Accept All</span><span>Date</span>
            </div>
            {jobs.map(j => (
              <Link key={j.id} to={`/history/${j.id}`} className={s.trow}>
                <span className={s.jobId}>{j.id.slice(0, 8)}…</span>
                <span><span className={`${s.type} ${j.job_type === 'single' ? s.single : s.batch}`}>{j.job_type}</span></span>
                <span className={s.fname}>{j.original_filename || '—'}</span>
                <span className={s.mono}>{j.total_emails}</span>
                <span className={s.mono} style={{ color: 'var(--success-600)' }}>{j.valid_count}</span>
                <span className={s.mono} style={{ color: 'var(--error-600)' }}>{j.invalid_count}</span>
                <span className={s.mono} style={{ color: 'var(--warning-600)' }}>{j.accept_all_count}</span>
                <span className={s.date}>{new Date(j.created_at).toLocaleString()}</span>
              </Link>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function JobDetail({ jobId }: { jobId: string }) {
  const navigate = useNavigate();
  const [job, setJob] = useState<ValidationJob | null>(null);
  const [results, setResults] = useState<ValidationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    api.job(jobId).then(d => { setJob(d.job); setResults(d.results); }).finally(() => setLoading(false));
  }, [jobId]);

  const shown = filter === 'all' ? results : results.filter(r => r.status === filter);

  return (
    <div className={s.page}>
      <div className={s.hdr}>
        <div className={s.hdrL}>
          <button className={s.back} onClick={() => navigate('/history')}><ArrowLeft size={13} /> Back</button>
          <div><h1 className={s.title}>Job Detail</h1><p className={s.sub} style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{jobId}</p></div>
        </div>
        <button className={s.dlBtn} onClick={() => api.downloadCsv(jobId)}><Download size={12} /> Export CSV</button>
      </div>

      {loading ? (
        <div className={s.center}><Spinner /> Loading…</div>
      ) : job ? (
        <>
          <div className={s.stats}>
            {[['Total', job.total_emails, 'var(--neutral-700)'], ['Valid', job.valid_count, 'var(--success-600)'],
              ['Invalid', job.invalid_count, 'var(--error-600)'], ['Accept All', job.accept_all_count, 'var(--warning-600)'],
              ['Unknown', job.unknown_count, 'var(--neutral-400)']].map(([l, v, c]) => (
              <div key={l as string} className={s.stat}>
                <div className={s.statNum} style={{ color: c as string }}>{v as number}</div>
                <div className={s.statLbl}>{l as string}</div>
              </div>
            ))}
          </div>

          <div className={s.filters}>
            {['all', 'valid', 'invalid', 'accept_all', 'unknown'].map(f => (
              <button key={f} className={`${s.filterBtn} ${filter === f ? s.activeFilter : ''}`} onClick={() => setFilter(f)}>
                {f === 'all' ? `All (${results.length})` : `${f.replace('_', ' ')} (${results.filter(r => r.status === f).length})`}
              </button>
            ))}
          </div>

          <div className={s.tableCard}>
            <div className={s.detailHead}>
              <span>Email</span><span>Status</span><span>Score</span><span>Reason</span><span>MX</span><span>SMTP</span><span>Disp.</span>
            </div>
            {shown.map((r, i) => (
              <div key={i} className={s.detailRow}>
                <span className={s.email}>{r.email}</span>
                <span><Badge status={r.status} sm /></span>
                <span className={s.scoreCell}><ScoreBar score={r.score} /></span>
                <span className={s.reason}>{r.failure_reason?.replace(/_/g, ' ') || '—'}</span>
                <span className={r.mx_records ? s.yes : s.no}>{r.mx_records ? 'y' : 'n'}</span>
                <span className={r.smtp_check ? s.yes : s.no}>{r.smtp_check ? 'y' : 'n'}</span>
                <span className={r.disposable ? s.no : s.yes}>{r.disposable ? 'y' : 'n'}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className={s.center}>Job not found.</div>
      )}
    </div>
  );
}
