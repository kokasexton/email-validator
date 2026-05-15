import { useState } from 'react';
import { Search, Server, Check, X, TriangleAlert as AlertTriangle, Minus } from 'lucide-react';
import { api } from '../lib/api';
import type { ValidationResult } from '../lib/api';
import { Badge } from '../components/Badge';
import { ScoreBar } from '../components/ScoreBar';
import { Spinner } from '../components/Spinner';
import s from './SingleValidate.module.css';

type Flag = { label: string; value: boolean | null; invert?: boolean; warn?: boolean };

function CheckRow({ label, value, invert, warn }: Flag) {
  const eff = invert ? !value : value;
  const icon = value === null ? <Minus size={12} strokeWidth={2.5} />
    : warn && value ? <AlertTriangle size={12} strokeWidth={2.5} />
    : eff ? <Check size={12} strokeWidth={2.5} />
    : <X size={12} strokeWidth={2.5} />;
  const cls = value === null ? 'neutral' : warn && value ? 'warn' : eff ? 'pass' : 'fail';
  return (
    <div className={`${s.row} ${s[cls]}`}>
      <span className={s.rowIcon}>{icon}</span>
      <span>{label}</span>
    </div>
  );
}

export function SingleValidate() {
  const [email, setEmail] = useState('');
  const [skipSmtp, setSkipSmtp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true); setErr(null); setResult(null);
    try {
      const res = await api.single(email.trim(), skipSmtp);
      setResult(res.result);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={s.page}>
      <h1 className={s.title}>Single Email Validation</h1>
      <p className={s.sub}>Full 4-stage check: syntax → disposable/role → DNS/MX → SMTP handshake</p>

      <div className={s.card}>
        <form onSubmit={submit} className={s.form}>
          <div className={s.inputWrap}>
            <Search size={15} className={s.icon} />
            <input
              className={s.input}
              type="email"
              placeholder="Enter email address..."
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoFocus
              autoComplete="off"
            />
          </div>
          <div className={s.row2}>
            <label className={s.check}>
              <input type="checkbox" checked={skipSmtp} onChange={e => setSkipSmtp(e.target.checked)} />
              Skip SMTP (DNS-only, faster)
            </label>
            <button className={s.btn} disabled={loading || !email.trim()}>
              {loading ? <><Spinner size={13} /> Validating…</> : 'Validate'}
            </button>
          </div>
        </form>
      </div>

      {err && <div className={s.errCard}><strong>Error:</strong> {err}</div>}

      {result && (
        <div className={`${s.result} anim-in`}>
          <div className={s.resultTop}>
            <div>
              <div className={s.emailLabel}>{result.email}</div>
              {result.failure_reason && (
                <div className={s.reason}>{result.failure_reason.replace(/_/g, ' ')}</div>
              )}
            </div>
            <Badge status={result.status} />
          </div>

          <div className={s.scoreRow}>
            <span className={s.scoreLbl}>Deliverability Score</span>
            <div className={s.scoreBar}><ScoreBar score={result.score} /></div>
          </div>

          <div className={s.checks}>
            <div className={s.checkGroup}>
              <div className={s.groupTitle}>Syntax & Quality</div>
              <CheckRow label="Valid syntax" value={result.regexp} />
              <CheckRow label="Not gibberish" value={result.gibberish} invert />
              <CheckRow label="Not disposable" value={result.disposable} invert />
              <CheckRow label="Not role-based" value={result.role_based} invert warn />
              <CheckRow label="Not webmail" value={result.webmail} invert warn />
            </div>
            <div className={s.checkGroup}>
              <div className={s.groupTitle}>Server Checks</div>
              <CheckRow label="MX records found" value={result.mx_records} />
              <CheckRow label="SMTP verified" value={result.smtp_check} />
              <CheckRow label="Not blocked" value={result.block} invert />
              <CheckRow label="Not accept-all" value={result.accept_all} invert warn />
              {result.smtp_server && (
                <div className={s.smtpRow}><Server size={11} />{result.smtp_server}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
