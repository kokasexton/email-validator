import s from './Badge.module.css';

type Status = 'valid' | 'invalid' | 'accept_all' | 'unknown';

const LABEL: Record<Status, string> = { valid: 'Valid', invalid: 'Invalid', accept_all: 'Accept All', unknown: 'Unknown' };

export function Badge({ status, sm }: { status: Status; sm?: boolean }) {
  return <span className={`${s.badge} ${s[status]} ${sm ? s.sm : ''}`}>{LABEL[status]}</span>;
}
