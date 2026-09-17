"""归一化与版面判定的单元测试。"""
import pytest

from normalize import (
    Line,
    clean_text,
    drop_page_furniture,
    is_watermark,
    join_wrapped,
    normalize_for_match,
)


def mkline(text, page=1, top=100.0, bottom=112.0, x0=70.8, x1=300.0):
    return Line(text=text, page=page, top=top, bottom=bottom, x0=x0, x1=x1)


class TestNormalizeForMatch:
    def test_fullwidth_letters_and_digits(self):
        assert normalize_for_match("Ａ：１２") == "A:12"

    def test_fullwidth_option_marker(self):
        assert normalize_for_match("Ｄ：选项") == "D:选项"

    def test_chinese_punctuation_is_preserved(self):
        # 关键：不能用 NFKC，否则「，」会变成 ASCII 逗号，正文面目全非
        src = "转化过程，接着详细介绍。"
        assert normalize_for_match(src) == src


class TestJoinWrapped:
    def test_cjk_joins_without_space(self):
        assert join_wrapped("转化过程，", "接着详细介绍") == "转化过程，接着详细介绍"

    def test_latin_words_get_a_space(self):
        assert join_wrapped("帕累托效率(Pareto", "efficiency)") == "帕累托效率(Pareto efficiency)"

    def test_digit_then_percent_stays_glued(self):
        # 回归：早期版本会切成 "38.4 %的速度"
        assert join_wrapped("增长38.4", "%的速度") == "增长38.4%的速度"

    def test_digits_are_not_split(self):
        assert join_wrapped("1234", "5678") == "12345678"

    def test_empty_operands(self):
        assert join_wrapped("", "甲") == "甲"
        assert join_wrapped("甲", "") == "甲"


class TestCleanText:
    def test_collapses_runs_of_spaces(self):
        assert clean_text("a    b") == "a b"

    def test_strips_edges_and_nbsp(self):
        assert clean_text("   题干 ") == "题干"


class TestWatermark:
    def test_footer_stamp_is_watermark(self):
        assert is_watermark({"x0": 469.2, "top": 789.9, "width": 106.0, "height": 32.0})

    def test_chart_in_body_is_not(self):
        assert not is_watermark({"x0": 70.8, "top": 197.4, "width": 440.3, "height": 228.7})

    def test_wide_footer_graphic_is_not(self):
        assert not is_watermark({"x0": 470.0, "top": 790.0, "width": 400.0, "height": 32.0})


class TestFullWidthLine:
    def test_line_reaching_right_margin(self):
        assert mkline("x", x1=524.3).is_full_width

    def test_short_line(self):
        assert not mkline("正确答案:C", x1=120.9).is_full_width


class TestPageFurniture:
    def test_drops_bottom_page_number(self):
        lines = [mkline("正文", top=100.0), mkline("128", top=800.0, bottom=812.0)]
        assert [l.text for l in drop_page_furniture(lines)] == ["正文"]

    def test_keeps_question_number_in_body(self):
        # 题号也是纯数字行，但位置在正文区，不能误删
        lines = [mkline("16", top=300.0, bottom=312.0)]
        assert len(drop_page_furniture(lines)) == 1
