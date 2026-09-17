"""阶段 2：把视觉行切成题块。

切分策略是「锚点 + 间距」混合，不是纯正则：

* `正确答案:` / `答案:` 是**闭合锚点** —— 它一定标志题干与选项已经结束。
* 版面**垂直间距**用来判断「解析结束、下一题题干开始」。这是本 PDF
  里唯一能区分二者的信号：题内行距 3.2~4.3pt，题间距 33~34pt。
* 跨页时没有间距可用，改看上一页末行**是否满行**：满行说明段落未完，
  属于续接；不满行说明段落收尾，下一页是新题。

纯间距切分会把「题干 / 图表 / 选项」切成三块（实测 924 块 vs 629 题），
纯正则又定不出解析与下一题题干的分界，两者必须结合。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from normalize import GAP_NEW_BLOCK, Line

SECTION_TITLES = {"言语理解推理题", "资料分析题", "图形推理题"}

OPTION_RE = re.compile(r"^([A-Z])\s*:\s*(.*)$")
# 「正确」二字在 3 处跨页时丢失，只剩裸「答案:」，所以前缀是可选的。
# 必须锚定行首且冒号紧跟，否则会误命中解析正文里的「故正确答案为B。」
ANSWER_RE = re.compile(r"^(?:正确)?答案\s*:\s*(.*)$")
EXPLAIN_RE = re.compile(r"^解析\s*:\s*(.*)$")
QNUM_RE = re.compile(r"^\d{1,4}$")


@dataclass
class RawQuestion:
    """一道题的原始行集合，尚未做文本合并与题型判定。"""
    section: str = ""
    number: int | None = None
    stem_lines: list[Line] = field(default_factory=list)
    option_lines: list[list[Line]] = field(default_factory=list)
    answer_raw: str = ""
    explain_lines: list[Line] = field(default_factory=list)
    explain_inline: str = ""
    start: tuple[int, float] = (0, 0.0)        # (page, top)
    end: tuple[int, float] = (0, 0.0)          # 下一题起点
    answer_pos: tuple[int, float] = (0, 0.0)   # 「正确答案」行位置，图片归属的分界线
    notes: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.stem_lines and not self.option_lines and not self.answer_raw


def is_block_break(prev: Line, cur: Line) -> bool:
    """判断 cur 是否开启了一个新的版面块。"""
    if cur.page != prev.page:
        # 跨页：上一页末行满行 => 段落未结束 => 续接
        return not prev.is_full_width
    return (cur.top - prev.bottom) > GAP_NEW_BLOCK


def segment(lines: list[Line]) -> list[RawQuestion]:
    """行序列 -> 题块序列。"""
    out: list[RawQuestion] = []
    cur = RawQuestion()
    state = "STEM"
    prev: Line | None = None
    section = ""

    def flush() -> None:
        nonlocal cur, state
        if not cur.is_empty:
            if prev is not None:
                cur.end = (prev.page, prev.bottom)
            out.append(cur)
        cur = RawQuestion(section=section)
        state = "STEM"

    for ln in lines:
        text = ln.match_text

        if text in SECTION_TITLES:
            flush()
            section = text
            cur.section = section
            prev = ln
            continue

        # --- 解析累积态：靠间距 / 题号判断何时收尾 ---
        if state == "EXPLAIN":
            if QNUM_RE.match(text) or (prev is not None and is_block_break(prev, ln)):
                flush()
                # 落到下面按 STEM 重新处理这一行
            else:
                cur.explain_lines.append(ln)
                prev = ln
                continue

        # 刚读完「正确答案」，期待紧跟一行「解析:」
        if state == "AWAIT_EXPLAIN":
            m = EXPLAIN_RE.match(text)
            if m:
                cur.explain_inline = m.group(1)
                state = "EXPLAIN"
                prev = ln
                continue
            flush()  # 没有解析行，直接进入下一题

        if state == "STEM":
            if QNUM_RE.match(text):
                if cur.stem_lines or cur.option_lines:
                    flush()
                cur.number = int(text)
                if not cur.start[0]:
                    cur.start = (ln.page, ln.top)
                prev = ln
                continue
            m = ANSWER_RE.match(text)
            if m:
                # 无文字选项（图形推理题）也走这条路
                if not cur.start[0]:
                    cur.start = (ln.page, ln.top)
                cur.answer_raw = m.group(1)
                cur.answer_pos = (ln.page, ln.top)
                state = "AWAIT_EXPLAIN"
                prev = ln
                continue
            m = OPTION_RE.match(text)
            if m:
                if not cur.start[0]:
                    cur.start = (ln.page, ln.top)
                cur.option_lines.append([ln])
                state = "OPTIONS"
                prev = ln
                continue
            if not cur.start[0]:
                cur.start = (ln.page, ln.top)
            cur.stem_lines.append(ln)
            prev = ln
            continue

        if state == "OPTIONS":
            m = ANSWER_RE.match(text)
            if m:
                cur.answer_raw = m.group(1)
                cur.answer_pos = (ln.page, ln.top)
                state = "AWAIT_EXPLAIN"
                prev = ln
                continue
            m = OPTION_RE.match(text)
            if m:
                cur.option_lines.append([ln])
                prev = ln
                continue
            # 选项文本换行续接
            if cur.option_lines:
                cur.option_lines[-1].append(ln)
            else:
                cur.stem_lines.append(ln)
            prev = ln
            continue

    flush()

    # 回填每题的结束位置 = 下一题的起点，用于把图片归到正确的题
    for a, b in zip(out, out[1:]):
        if b.start[0]:
            a.end = b.start
    return [q for q in out if not q.is_empty]
