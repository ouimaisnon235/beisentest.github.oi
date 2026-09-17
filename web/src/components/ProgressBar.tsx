import { useStats } from "../store/useQuizStore";

export function ProgressBar() {
  const s = useStats();
  const done = s.deckSize - s.remaining;
  const pct = s.deckSize ? (done / s.deckSize) * 100 : 0;

  return (
    <div className="progress">
      <div className="progress-track" role="progressbar" aria-valuenow={Math.round(pct)}
           aria-valuemin={0} aria-valuemax={100} aria-label="本轮练习进度">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-stats">
        <span>本轮 <b>{done}</b>/{s.deckSize}</span>
        <span className="sep">·</span>
        <span>剩余 <b>{s.remaining}</b></span>
        <span className="sep">·</span>
        <span>已练 <b>{s.seen}</b>/{s.total}</span>
        <span className="sep">·</span>
        <span className="ok">对 <b>{s.correct}</b></span>
        <span className="sep">·</span>
        <span className="bad">错 <b>{s.wrong}</b></span>
      </div>
    </div>
  );
}
