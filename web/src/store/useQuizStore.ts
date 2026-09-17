import { create } from "zustand";
import { shallow } from "zustand/shallow";

import { shuffle } from "../lib/shuffle";
import { EMPTY, clearProgress, loadProgress, saveProgress } from "../lib/storage";
import { type Question, type QuestionType, isCorrect } from "../types";

/** 触底一次补多少题。太小会频繁触发，太大会一次塞爆 DOM。 */
export const BATCH = 15;

export interface Filters {
  sections: string[];
  types: QuestionType[];
  wrongOnly: boolean;
}

interface QuizState {
  status: "loading" | "ready" | "error";
  error: string;

  all: Question[];
  byId: Record<string, Question>;
  allSections: string[];
  allTypes: QuestionType[];

  filters: Filters;

  /** 本轮的「牌堆」：筛选集洗牌后的 id 序列，不放回。 */
  deck: string[];
  /** 已经从牌堆里发出去多少张。 */
  cursor: number;
  /** 当前渲染的题目 id。 */
  drawn: string[];

  seen: Record<string, true>;
  wrong: Record<string, true>;
  graded: Record<string, boolean>;
  picks: Record<string, string[]>;
  revealed: Record<string, true>;

  load: () => Promise<void>;
  setFilters: (patch: Partial<Filters>) => void;
  reshuffle: () => void;
  drawMore: () => void;
  togglePick: (id: string, key: string) => void;
  submit: (id: string) => void;
  reveal: (id: string) => void;
  resetProgress: () => void;
}

function matches(q: Question, f: Filters, wrong: Record<string, true>): boolean {
  if (f.wrongOnly && !wrong[q.id]) return false;
  if (f.types.length && !f.types.includes(q.type)) return false;
  if (f.sections.length) {
    const sec = q.tags[0] ?? "";
    if (!f.sections.includes(sec)) return false;
  }
  return true;
}

function persist(s: QuizState): void {
  saveProgress({
    seen: s.seen,
    wrong: s.wrong,
    graded: s.graded,
    picks: s.picks,
    revealed: s.revealed,
  });
}

export const useQuizStore = create<QuizState>((set, get) => ({
  status: "loading",
  error: "",
  all: [],
  byId: {},
  allSections: [],
  allTypes: [],
  filters: { sections: [], types: [], wrongOnly: false },
  deck: [],
  cursor: 0,
  drawn: [],
  ...EMPTY,

  async load() {
    try {
      const url = `${import.meta.env.BASE_URL}data/questions.json`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status} — ${url}`);
      const all = (await res.json()) as Question[];

      const byId: Record<string, Question> = {};
      const sections = new Set<string>();
      const types = new Set<QuestionType>();
      for (const q of all) {
        byId[q.id] = q;
        if (q.tags[0]) sections.add(q.tags[0]);
        types.add(q.type);
      }

      const saved = loadProgress();
      set({
        status: "ready",
        all,
        byId,
        allSections: [...sections],
        allTypes: [...types],
        ...saved,
      });
      get().reshuffle();
    } catch (err) {
      set({
        status: "error",
        error:
          err instanceof Error
            ? `${err.message}。请先运行解析器生成 data/questions.json，再执行 npm run dev。`
            : String(err),
      });
    }
  },

  setFilters(patch) {
    set({ filters: { ...get().filters, ...patch } });
    get().reshuffle();
  },

  /** 重建牌堆：按当前筛选取 id、洗牌、发第一批。 */
  reshuffle() {
    const { all, filters, wrong } = get();
    const pool = all.filter((q) => matches(q, filters, wrong)).map((q) => q.id);
    const deck = shuffle(pool);
    set({ deck, cursor: 0, drawn: [] });
    get().drawMore();
  },

  drawMore() {
    const { deck, cursor, seen } = get();
    if (cursor >= deck.length) return;
    const next = deck.slice(cursor, cursor + BATCH);
    const nextSeen = { ...seen };
    for (const id of next) nextSeen[id] = true;
    set({ cursor: cursor + next.length, drawn: [...get().drawn, ...next], seen: nextSeen });
    persist(get());
  },

  togglePick(id, key) {
    const { byId, picks, graded } = get();
    if (graded[id] !== undefined) return; // 已提交，不允许改
    const q = byId[id];
    const cur = picks[id] ?? [];
    const multi = q.type === "multiple_choice";
    const next = multi
      ? cur.includes(key)
        ? cur.filter((k) => k !== key)
        : [...cur, key]
      : [key];
    set({ picks: { ...picks, [id]: next } });
    persist(get());
  },

  submit(id) {
    const { byId, picks, graded, wrong, revealed } = get();
    const chosen = picks[id] ?? [];
    if (!chosen.length || graded[id] !== undefined) return;

    const ok = isCorrect(byId[id], chosen);
    const nextWrong = { ...wrong };
    if (ok) delete nextWrong[id];
    else nextWrong[id] = true;

    set({
      graded: { ...graded, [id]: ok },
      wrong: nextWrong,
      revealed: { ...revealed, [id]: true },
    });
    persist(get());
  },

  reveal(id) {
    set({ revealed: { ...get().revealed, [id]: true } });
    persist(get());
  },

  resetProgress() {
    clearProgress();
    set({ ...EMPTY });
    get().reshuffle();
  },
}));

/** 派生统计，供进度条使用。用 shallow 比较，避免每次 store 变动都重渲染。 */
export function useStats() {
  return useQuizStore((s) => {
    const graded = Object.values(s.graded);
    return {
      total: s.all.length,
      seen: Object.keys(s.seen).length,
      correct: graded.filter(Boolean).length,
      wrong: Object.keys(s.wrong).length,
      deckSize: s.deck.length,
      remaining: Math.max(0, s.deck.length - s.cursor),
      roundDone: s.deck.length > 0 && s.cursor >= s.deck.length,
      empty: s.deck.length === 0,
    };
  }, shallow);
}
