import s from './ScoreBar.module.css';

function color(n: number) { return n >= 70 ? 'good' : n >= 40 ? 'mid' : 'poor'; }

export function ScoreBar({ score }: { score: number }) {
  const c = color(score);
  return (
    <div className={s.wrap}>
      <div className={s.track}><div className={`${s.fill} ${s[c]}`} style={{ width: `${score}%` }} /></div>
      <span className={`${s.num} ${s[c]}`}>{score}</span>
    </div>
  );
}
