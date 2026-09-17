export type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "fill_blank"
  | "short_answer";

export interface Option {
  key: string;
  text: string;
}

export interface Question {
  id: string;
  type: QuestionType;
  stem: string;
  options: Option[];
  answer: string | string[] | boolean;
  explanation: string;
  sourcePage: number;
  tags: string[];
  images: string[];
  number: number | null;
}

export const TYPE_LABELS: Record<QuestionType, string> = {
  single_choice: "单选题",
  multiple_choice: "多选题",
  true_false: "判断题",
  fill_blank: "填空题",
  short_answer: "简答题",
};

/** 图形推理题没有文字选项。原书说明「选项从上往下数，分别为 A,B,C,D,E」。 */
export const IMAGE_OPTION_KEYS = ["A", "B", "C", "D", "E"];

export function answerKeys(q: Question): string[] {
  if (Array.isArray(q.answer)) return [...q.answer].sort();
  if (typeof q.answer === "string") return q.answer ? [q.answer] : [];
  return [q.answer ? "T" : "F"];
}

export function isCorrect(q: Question, picks: string[]): boolean {
  const want = answerKeys(q);
  const got = [...picks].sort();
  return want.length === got.length && want.every((k, i) => k === got[i]);
}
