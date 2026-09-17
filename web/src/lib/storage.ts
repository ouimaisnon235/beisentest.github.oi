/**
 * localStorage 读写封装。
 * 隐私模式、站点数据被清除、或存储配额耗尽时访问会抛异常，
 * 所以每次读写都包 try/catch，失败时降级为「不持久化」而不是崩溃。
 */
const KEY = "beisen-quiz:v1";

export interface Persisted {
  seen: Record<string, true>;
  wrong: Record<string, true>;
  graded: Record<string, boolean>;
  picks: Record<string, string[]>;
  revealed: Record<string, true>;
}

export const EMPTY: Persisted = { seen: {}, wrong: {}, graded: {}, picks: {}, revealed: {} };

export function loadProgress(): Persisted {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...EMPTY };
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return { ...EMPTY, ...parsed };
  } catch {
    return { ...EMPTY };
  }
}

export function saveProgress(state: Persisted): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* 存不下就算了，不影响练习 */
  }
}

export function clearProgress(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* 同上 */
  }
}
