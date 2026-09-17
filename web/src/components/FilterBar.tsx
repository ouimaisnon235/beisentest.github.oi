import { shallow } from "zustand/shallow";

import { useQuizStore } from "../store/useQuizStore";
import { TYPE_LABELS, type QuestionType } from "../types";

export function FilterBar() {
  const { filters, allSections, allTypes, setFilters, reshuffle, resetProgress, wrongCount } =
    useQuizStore(
      (s) => ({
        filters: s.filters,
        allSections: s.allSections,
        allTypes: s.allTypes,
        setFilters: s.setFilters,
        reshuffle: s.reshuffle,
        resetProgress: s.resetProgress,
        wrongCount: Object.keys(s.wrong).length,
      }),
      shallow,
    );

  const toggle = <T extends string>(list: T[], value: T): T[] =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const noFilters =
    !filters.sections.length && !filters.types.length && !filters.wrongOnly;

  return (
    <div className="filters">
      <div className="filter-row">
        <span className="filter-label">题库分类</span>
        <div className="chips">
          {allSections.map((sec) => (
            <label key={sec} className={`chip ${filters.sections.includes(sec) ? "on" : ""}`}>
              <input
                type="checkbox"
                checked={filters.sections.includes(sec)}
                onChange={() => setFilters({ sections: toggle(filters.sections, sec) })}
              />
              {sec}
            </label>
          ))}
        </div>
      </div>

      {allTypes.length > 1 && (
        <div className="filter-row">
          <span className="filter-label">题型</span>
          <div className="chips">
            {allTypes.map((t) => (
              <label key={t} className={`chip ${filters.types.includes(t) ? "on" : ""}`}>
                <input
                  type="checkbox"
                  checked={filters.types.includes(t)}
                  onChange={() => setFilters({ types: toggle(filters.types, t) as QuestionType[] })}
                />
                {TYPE_LABELS[t]}
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="filter-row">
        <div className="chips">
          <label className={`chip accent ${filters.wrongOnly ? "on" : ""}`}>
            <input
              type="checkbox"
              checked={filters.wrongOnly}
              onChange={() => setFilters({ wrongOnly: !filters.wrongOnly })}
            />
            只看错题 ({wrongCount})
          </label>
          <button className="btn ghost" onClick={reshuffle}>重新洗牌</button>
          <button
            className="btn ghost"
            disabled={noFilters}
            onClick={() => setFilters({ sections: [], types: [], wrongOnly: false })}
          >
            重置筛选
          </button>
          <button
            className="btn ghost danger"
            onClick={() => {
              if (confirm("清空所有答题记录和错题本？此操作不可撤销。")) resetProgress();
            }}
          >
            清空记录
          </button>
        </div>
      </div>
    </div>
  );
}
