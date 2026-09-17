"""阶段 3：题块 -> 结构化题目。"""
from __future__ import annotations

import hashlib
import re

from normalize import clean_text, join_wrapped
from schema import (
    FILL_BLANK,
    MULTIPLE_CHOICE,
    Option,
    Question,
    SHORT_ANSWER,
    SINGLE_CHOICE,
    TRUE_FALSE,
)
from segment import OPTION_RE, RawQuestion

_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]{0,80}>")

TRUE_WORDS = {"对", "正确", "是", "√", "T", "true", "Y"}
FALSE_WORDS = {"错", "错误", "否", "×", "x", "F", "false", "N"}


def strip_html(s: str) -> tuple[str, bool]:
    """剥掉混入正文的 HTML 标签（全库 3 处），返回 (文本, 是否发生剥离)。"""
    cleaned = _HTML_TAG.sub("", s)
    return cleaned, cleaned != s


def merge_lines(lines) -> str:
    """把若干视觉行合并成一个段落，处理软换行。"""
    out = ""
    for ln in lines:
        out = join_wrapped(out, ln.text)
    return clean_text(out)


def normalize_answer(raw: str, n_options: int) -> tuple[object, str]:
    """把答案原文标准化，返回 (答案值, 推断出的题型)。

    单字母 -> "A" / single_choice
    多字母 -> ["A","C"] / multiple_choice
    对错词 -> True/False / true_false
    其余   -> 原文 / short_answer
    """
    s = clean_text(raw)
    if not s:
        return "", SHORT_ANSWER

    if s in TRUE_WORDS:
        return True, TRUE_FALSE
    if s in FALSE_WORDS:
        return False, TRUE_FALSE

    letters = re.findall(r"[A-Z]", s.upper())
    # 只有当答案里除字母外没有实质内容时，才当作选择题答案；
    # 否则 "A公司利润最高" 这类文字答案会被误判成多选 ["A"]。
    residue = re.sub(r"[A-Z\s,，、;；和与\.]", "", s.upper())
    if letters and not residue:
        uniq = sorted(set(letters))
        if len(uniq) == 1:
            return uniq[0], SINGLE_CHOICE
        return uniq, MULTIPLE_CHOICE

    return s, SHORT_ANSWER


def decide_type(answer_type: str, n_options: int, stem: str) -> str:
    """题型判定：答案结构为主，选项数与题干形态兜底。"""
    if answer_type in (TRUE_FALSE, MULTIPLE_CHOICE):
        return answer_type
    if answer_type == SINGLE_CHOICE:
        return SINGLE_CHOICE
    # 答案是自由文本
    if n_options == 0 and re.search(r"_{2,}|（\s*）|\(\s*\)", stem):
        return FILL_BLANK
    return SHORT_ANSWER


def make_id(section: str, number: int | None, stem: str, page: int, seen: set[str]) -> str:
    """稳定且唯一的 id。

    不用题号：本书题号在每个章节重置、且第 21 页起大面积缺失。
    用 章节+页码+题干 的哈希，重跑幂等；冲突时加后缀。
    """
    basis = f"{section}|{number}|{page}|{stem[:120]}"
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]
    sec = {"言语理解推理题": "yy", "资料分析题": "zl", "图形推理题": "tx"}.get(section, "qz")
    qid = f"{sec}-{digest}"
    if qid in seen:
        i = 2
        while f"{qid}-{i}" in seen:
            i += 1
        qid = f"{qid}-{i}"
    seen.add(qid)
    return qid


def build(raw: RawQuestion, seen: set[str]) -> tuple[Question, list[str]]:
    """把一个 RawQuestion 结构化，返回 (题目, 告警列表)。"""
    warnings: list[str] = []

    stem = merge_lines(raw.stem_lines)
    stem, had_html = strip_html(stem)
    if had_html:
        warnings.append("题干含 HTML 标签，已剥离")

    options: list[Option] = []
    for group in raw.option_lines:
        text = merge_lines(group)
        m = OPTION_RE.match(text)
        if not m:
            warnings.append(f"选项行解析失败: {text[:40]!r}")
            continue
        body, _ = strip_html(clean_text(m.group(2)))
        options.append(Option(key=m.group(1), text=body))

    explain = raw.explain_inline
    if raw.explain_lines:
        explain = join_wrapped(clean_text(explain), merge_lines(raw.explain_lines))
    explain, _ = strip_html(clean_text(explain))

    answer, ans_type = normalize_answer(raw.answer_raw, len(options))
    qtype = decide_type(ans_type, len(options), stem)

    if isinstance(answer, str) and answer and len(answer) == 1 and options:
        if answer not in {o.key for o in options}:
            warnings.append(f"答案 {answer} 不在选项 {[o.key for o in options]} 中")

    tags = [t for t in (raw.section,) if t]
    if not options and answer:
        tags.append("图片选项")

    q = Question(
        id=make_id(raw.section, raw.number, stem, raw.start[0], seen),
        type=qtype,
        stem=stem,
        options=options,
        answer=answer,
        explanation=explain,
        sourcePage=raw.start[0],
        tags=tags,
        number=raw.number,
    )
    return q, warnings
