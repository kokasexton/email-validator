import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CircleCheck as CheckCircle, Circle as XCircle, Circle as HelpCircle, ArrowRight, Zap, Layers, Clock } from 'lucide-react';
import { api } from '../lib/api';
import type { ValidationJob } from '../lib/api';
import s from './Dashboard.module.css';

export function Dashboard() {
  const [jobs, setJobs] = useState<ValidationJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.jobs(10).then(r => setJobs(r.jobs)).finally(() => setLoading(false));
  }, []);

  const totals = jobs.reduce(
    (a, j) => ({ emails: a.emails + j.total_emails, valid: a.valid + j.valid_count, invalid: a.invalid + j.invalid_count }),
    { emails: 0, valid: 0, invalid: 0 }
  );
  const rate = totals.emails > 0 ? Math.round((totals.valid / totals.emails) * 100) : 0;

  return (
    <div className={s.page}>
      <header className={s.hdr}>
        <h1 className={s.title}>Dashboard</h1>
        <p className={s.sub}>Email validation overview and quick actions</p>
      </header>

      <div className={s.stats}>
        {[
          { icon: <Zap size={17} />, value: loading ? '—' : totals.emails.toLocaleString(), label: 'Emails Validated', bg: 'var(--primary-50)', fg: 'var(--primary-600)' },
          { icon: <CheckCircle size={17} />, value: loading ? '—' : totals.valid.toLocaleString(), label: 'Valid', bg: 'var(--success-50)', fg: 'var(--success-600)' },
          { icon: <XCircle size={17} />, value: loading ? '—' : totals.invalid.toLocaleString(), label: 'Invalid', bg: 'var(--error-50)', fg: 'var(--error-600)' },
          { icon: <HelpCircle size={17} />, value: loading ? '—' : `${rate}%`, label: 'Deliverability', bg: 'var(--accent-50)', fg: 'var(--accent-600)' },
        ].map(c => (
          <div key={c.label} className={s.stat}>
            <span className={s.statIcon} style={{ background: c.bg, color: c.fg }}>{c.icon}</span>
            <div><div className={s.statVal}>{c.value}</div><div className={s.statLbl}>{c.label}</div></div>
          </div>
        ))}
      </div>

      <div className={s.actions}>
        {[
          { to: '/single', icon: <CheckCircle size={22} />, title: 'Validate Single Email', desc: 'Full syntax, DNS & SMTP check on one address' },
          { to: '/bulk',   icon: <Layers size={22} />,       title: 'Bulk / CSV Import',   desc: 'Upload a CSV or paste emails — up to 10,000 at once' },
          { to: '/history',icon: <Clock size={22} />,        title: 'Validation History',  desc: 'Browse past jobs and download results' },
        ].map(a => (
          <Link key={a.to} to={a.to} className={s.action}>
            <span className={s.actionIcon}>{a.icon}</span>
            <div className={s.actionBody}>
              <div className={s.actionTitle}>{a.title}</div>
              <div className={s.actionDesc}>{a.desc}</div>
            </div>
            <ArrowRight size={15} className={s.arrow} />
          </Link>
        ))}
      </div>

      <section className={s.recent}>
        <div className={s.recentHdr}>
          <span className={s.recentTitle}>Recent Jobs</span>
          <Link to="/history" className={s.viewAll}>View all <ArrowRight size={12} /></Link>
        </div>
        {loading ? (
          <div className={s.empty}>Loading...</div>
        ) : jobs.length === 0 ? (
          <div className={s.empty}>No jobs yet. <Link to="/single" className={s.link}>Validate your first email</Link></div>
        ) : (
          <div className={s.table}>
            <div className={s.thead}>
              <span>Type</span><span>Total</span><span>Valid</span><span>Invalid</span><span>Accept All</span><span>Date</span>
            </div>
            {jobs.map(j => (
              <Link key={j.id} to={`/history/${j.id}`} className={s.trow}>
                <span><span className={`${s.type} ${j.job_type === 'single' ? s.single : s.batch}`}>{j.job_type}</span></span>
                <span className={s.mono}>{j.total_emails}</span>
                <span className={s.mono} style={{ color: 'var(--success-600)' }}>{j.valid_count}</span>
                <span className={s.mono} style={{ color: 'var(--error-600)' }}>{j.invalid_count}</span>
                <span className={s.mono} style={{ color: 'var(--warning-600)' }}>{j.accept_all_count}</span>
                <span className={s.date}>{new Date(j.created_at).toLocaleDateString()}</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
