import { memo, type ReactNode } from "react";

import { useQuizStore } from "../store/useQuizStore";
import { IMAGE_OPTION_KEYS, TYPE_LABELS, type Question, answerKeys } from "../types";

const IMG_PLACEHOLDER = /\[图片(\d+)\]/g;

/** 把题干里的 [图片N] 占位符替换成真正的 <img>。 */
function Stem({ q }: { q: Question }) {
  const parts: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  IMG_PLACEHOLDER.lastIndex = 0;

  while ((m = IMG_PLACEHOLDER.exec(q.stem)) !== null) {
    if (m.index > last) parts.push(q.stem.slice(last, m.index));
    const src = q.images[Number(m[1]) - 1];
    if (src) {
      parts.push(
        <img
          key={`${q.id}-img-${m[1]}`}
          className="stem-img"
          src={`${import.meta.env.BASE_URL}data/${src}`}
          alt={`第 ${q.sourcePage} 页题目配图 ${m[1]}`}
          loading="lazy"
        />,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < q.stem.length) parts.push(q.stem.slice(last));

  return <div className="stem">{parts.length ? parts : <em className="muted">（题目内容见配图）</em>}</div>;
}

export const QuestionCard = memo(function QuestionCard({ q }: { q: Question }) {
  const picks = useQuizStore((s) => s.picks[q.id]);
  const graded = useQuizStore((s) => s.graded[q.id]);
  const revealed = useQuizStore((s) => s.revealed[q.id]);
  const togglePick = useQuizStore((s) => s.togglePick);
  const submit = useQuizStore((s) => s.submit);
  const reveal = useQuizStore((s) => s.reveal);

  const chosen = picks ?? [];
  const correct = answerKeys(q);
  const isGraded = graded !== undefined;
  // 图形推理题没有文字选项，用纯字母按钮作答
  const keys = q.options.length ? q.options.map((o) => o.key) : IMAGE_OPTION_KEYS;

  const stateOf = (key: string): string => {
    if (!isGraded) return chosen.includes(key) ? "picked" : "";
    if (correct.includes(key)) return "right";
    if (chosen.includes(key)) return "wrong";
    return "";
  };

  return (
    <article data-qid={q.id} className={`card ${isGraded ? (graded ? "card-ok" : "card-bad") : ""}`}>
      <header className="card-head">
        <span className="badge">{TYPE_LABELS[q.type]}</span>
        {q.tags[0] && <span className="badge soft">{q.tags[0]}</span>}
        <span className="page">P{q.sourcePage}</span>
        {isGraded && (
          <span className={`verdict ${graded ? "ok" : "bad"}`}>{graded ? "答对" : "答错"}</span>
        )}
      </header>

      <Stem q={q} />

      {q.options.length > 0 ? (
        <ul className="options">
          {q.options.map((o) => (
            <li key={o.key}>
              <button
                className={`option ${stateOf(o.key)}`}
                onClick={() => togglePick(q.id, o.key)}
                disabled={isGraded}
              >
                <span className="option-key">{o.key}</span>
                <span className="option-text">{o.text}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="letter-row" role="group" aria-label="选择答案">
          {keys.map((k) => (
            <button
              key={k}
              className={`letter ${stateOf(k)}`}
              onClick={() => togglePick(q.id, k)}
              disabled={isGraded}
            >
              {k}
            </button>
          ))}
        </div>
      )}

      <footer className="card-foot">
        {!isGraded && (
          <button className="btn" disabled={!chosen.length} onClick={() => submit(q.id)}>
            提交答案
          </button>
        )}
        {!revealed && (
          <button className="btn ghost" onClick={() => reveal(q.id)}>
            显示答案 / 解析
          </button>
        )}
      </footer>

      {revealed && (
        <div className="reveal">
          <p className="answer">
            正确答案：<b>{correct.join("、") || "（原书未给出）"}</b>
          </p>
          {q.explanation ? (
            <p className="explanation">{q.explanation}</p>
          ) : (
            <p className="explanation muted">原书未提供解析。</p>
          )}
        </div>
      )}
    </article>
  );
});
