"""questions.json 的数据契约。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# 题型。本题库实测全部为 single_choice，其余类型保留定义，
# 以便同一套解析器/前端处理其他题库。
SINGLE_CHOICE = "single_choice"
MULTIPLE_CHOICE = "multiple_choice"
TRUE_FALSE = "true_false"
FILL_BLANK = "fill_blank"
SHORT_ANSWER = "short_answer"

ALL_TYPES = [SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE, FILL_BLANK, SHORT_ANSWER]

TYPE_LABELS = {
    SINGLE_CHOICE: "单选题",
    MULTIPLE_CHOICE: "多选题",
    TRUE_FALSE: "判断题",
    FILL_BLANK: "填空题",
    SHORT_ANSWER: "简答题",
}


@dataclass
class Option:
    key: str
    text: str


@dataclass
class Question:
    id: str
    type: str
    stem: str
    options: list[Option] = field(default_factory=list)
    answer: Any = ""                       # str | list[str] | bool
    explanation: str = ""
    sourcePage: int = 0
    tags: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)   # 相对 data/ 的路径
    number: int | None = None              # 原书题号，可能为空

    def to_dict(self) -> dict:
        d = asdict(self)
        d["options"] = [asdict(o) if not isinstance(o, dict) else o for o in self.options]
        return d
