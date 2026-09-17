"""结构化层（题型判定 / 答案标准化 / id 生成）的单元测试。"""
import pytest

from normalize import Line
from schema import (
    FILL_BLANK,
    MULTIPLE_CHOICE,
    SHORT_ANSWER,
    SINGLE_CHOICE,
    TRUE_FALSE,
)
from segment import segment
from structure import build, decide_type, make_id, merge_lines, normalize_answer, strip_html


class TestNormalizeAnswer:
    @pytest.mark.parametrize("raw", ["A", "D", "E"])
    def test_single_letter(self, raw):
        assert normalize_answer(raw, 4) == (raw, SINGLE_CHOICE)

    @pytest.mark.parametrize("raw,want", [
        ("ACD", ["A", "C", "D"]),
        ("A、C、D", ["A", "C", "D"]),
        ("A C D", ["A", "C", "D"]),
        ("D,A,C", ["A", "C", "D"]),      # 排序
        ("AAC", ["A", "C"]),             # 去重
    ])
    def test_multi_letter(self, raw, want):
        assert normalize_answer(raw, 4) == (want, MULTIPLE_CHOICE)

    @pytest.mark.parametrize("raw", ["对", "正确", "是", "√", "T"])
    def test_true_words(self, raw):
        assert normalize_answer(raw, 0) == (True, TRUE_FALSE)

    @pytest.mark.parametrize("raw", ["错", "错误", "否", "×", "F"])
    def test_false_words(self, raw):
        assert normalize_answer(raw, 0) == (False, TRUE_FALSE)

    def test_free_text_answer_is_not_mistaken_for_choices(self):
        # 回归：早期版本把 "A公司利润最高" 抽成多选 ["A"]
        value, kind = normalize_answer("A公司利润最高", 0)
        assert value == "A公司利润最高"
        assert kind == SHORT_ANSWER

    def test_empty_answer(self):
        assert normalize_answer("", 4) == ("", SHORT_ANSWER)

    def test_whitespace_padded_letter(self):
        assert normalize_answer("  B  ", 4) == ("B", SINGLE_CHOICE)


class TestDecideType:
    def test_choice_wins(self):
        assert decide_type(SINGLE_CHOICE, 4, "题干") == SINGLE_CHOICE

    def test_true_false_wins(self):
        assert decide_type(TRUE_FALSE, 0, "题干") == TRUE_FALSE

    def test_blank_markers_make_fill_blank(self):
        assert decide_type(SHORT_ANSWER, 0, "最适合填入____的是") == FILL_BLANK
        assert decide_type(SHORT_ANSWER, 0, "一定要做到（　）广泛了解") == FILL_BLANK

    def test_plain_text_falls_back_to_short_answer(self):
        assert decide_type(SHORT_ANSWER, 0, "请简述原因") == SHORT_ANSWER


class TestStripHtml:
    def test_removes_tags_found_in_the_pdf(self):
        out, changed = strip_html('名片</span><em class="em inline"><span>拾获')
        assert out == "名片拾获"
        assert changed

    def test_leaves_plain_text_alone(self):
        out, changed = strip_html("增长率 = (第二年-第一年)/第一年")
        assert out == "增长率 = (第二年-第一年)/第一年"
        assert not changed

    def test_does_not_eat_math_comparisons(self):
        out, _ = strip_html("A>C>F>D")
        assert out == "A>C>F>D"


class TestMergeLines:
    def test_soft_wrap_merge(self):
        lines = [
            Line("前半句，", 1, 100.0, 112.0, 70.8, 524.3),
            Line("后半句。", 1, 116.0, 128.0, 70.8, 200.0),
        ]
        assert merge_lines(lines) == "前半句，后半句。"


class TestMakeId:
    def test_is_deterministic(self):
        a = make_id("言语理解推理题", 1, "题干内容", 1, set())
        b = make_id("言语理解推理题", 1, "题干内容", 1, set())
        assert a == b

    def test_section_prefix(self):
        assert make_id("资料分析题", 1, "x", 1, set()).startswith("zl-")
        assert make_id("图形推理题", 1, "x", 1, set()).startswith("tx-")

    def test_collision_gets_suffixed(self):
        seen = set()
        first = make_id("图形推理题", None, "问号处应当是：", 270, seen)
        second = make_id("图形推理题", None, "问号处应当是：", 270, seen)
        assert first != second
        assert second.endswith("-2")


class TestBuildEndToEnd:
    def _lines(self, rows):
        out, top = [], 70.0
        for text, gap, x1 in rows:
            top += gap
            out.append(Line(text, 1, top, top + 12.0, 70.8, x1))
            top += 12.0
        return out

    def test_full_question(self):
        rows = [
            ("这是题干，问下面哪个对:", 0.0, 524.3),
            ("A:甲选项", 4.0, 200.0),
            ("B:乙选项", 4.0, 200.0),
            ("正确答案:B", 4.0, 120.0),
            ("解析:因为乙对。", 4.0, 180.0),
        ]
        raw = segment(self._lines(rows))[0]
        q, warnings = build(raw, set())
        assert q.type == SINGLE_CHOICE
        assert q.stem == "这是题干，问下面哪个对:"
        assert [(o.key, o.text) for o in q.options] == [("A", "甲选项"), ("B", "乙选项")]
        assert q.answer == "B"
        assert q.explanation == "因为乙对。"
        assert q.sourcePage == 1
        assert warnings == []

    def test_answer_outside_options_is_flagged(self):
        rows = [
            ("题干:", 0.0, 300.0),
            ("A:甲", 4.0, 200.0),
            ("B:乙", 4.0, 200.0),
            ("正确答案:D", 4.0, 120.0),
        ]
        raw = segment(self._lines(rows))[0]
        _, warnings = build(raw, set())
        assert any("不在选项" in w for w in warnings)

    def test_image_question_is_tagged(self):
        rows = [
            ("问号处的图形应该是：", 0.0, 180.0),
            ("正确答案:C", 4.0, 120.0),
        ]
        raw = segment(self._lines(rows))[0]
        q, _ = build(raw, set())
        assert q.options == []
        assert "图片选项" in q.tags
        assert q.answer == "C"
