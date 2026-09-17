import { useEffect } from "react";
import { shallow } from "zustand/shallow";

import { FilterBar } from "./components/FilterBar";
import { InfiniteScroller } from "./components/InfiniteScroller";
import { ProgressBar } from "./components/ProgressBar";
import { QuestionCard } from "./components/QuestionCard";
import { useQuizStore, useStats } from "./store/useQuizStore";

export default function App() {
  const { status, error, load, drawn, byId, drawMore, reshuffle } = useQuizStore(
    (s) => ({
      status: s.status,
      error: s.error,
      load: s.load,
      drawn: s.drawn,
      byId: s.byId,
      drawMore: s.drawMore,
      reshuffle: s.reshuffle,
    }),
    shallow,
  );
  const stats = useStats();

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <h1>北森测评题库</h1>
          <p className="tagline">随机不重复 · 滚动练习</p>
        </div>
      </header>

      <div className="controls">
        <div className="controls-inner">
          <FilterBar />
          <ProgressBar />
        </div>
      </div>

      <main className="feed">
        {status === "loading" && <p className="notice">正在载入题库…</p>}

        {status === "error" && (
          <div className="notice error">
            <b>题库载入失败</b>
            <p>{error}</p>
          </div>
        )}

        {status === "ready" && stats.empty && (
          <div className="notice">
            当前筛选条件下没有题目。
            {useQuizStore.getState().filters.wrongOnly && "（错题本还是空的，先去做几道题吧。）"}
          </div>
        )}

        {drawn.map((id) => byId[id] && <QuestionCard key={id} q={byId[id]} />)}

        {status === "ready" && !stats.empty && (
          <>
            <InfiniteScroller onReachEnd={drawMore} disabled={stats.roundDone} />
            {stats.roundDone && (
              <div className="round-end">
                <p>
                  已完成一轮 —— 本轮 <b>{stats.deckSize}</b> 道题全部出现过，没有重复。
                </p>
                <button
                  className="btn"
                  onClick={() => {
                    reshuffle();
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  重新洗牌，再来一轮
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
