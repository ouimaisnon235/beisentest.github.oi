"""题块切分状态机的单元测试。

夹具直接构造带坐标的 Line，复刻 PDF 里的真实版式：
题内行距约 4pt，题间距约 33pt。
"""
import pytest

from normalize import Line
from segment import ANSWER_RE, OPTION_RE, is_block_break, segment

LINE_H = 12.0
TIGHT = 4.0      # 题内行距
LOOSE = 33.0     # 题间距


class Builder:
    """按版面规则顺次堆行，省得手算坐标。"""

    def __init__(self, page=1, top=70.0):
        self.page, self.cursor, self.lines = page, top, []

    def add(self, text, gap=TIGHT, x1=300.0):
        self.cursor += gap
        ln = Line(text=text, page=self.page, top=self.cursor,
                  bottom=self.cursor + LINE_H, x0=70.8, x1=x1)
        self.cursor += LINE_H
        self.lines.append(ln)
        return self

    def newpage(self, top=70.0):
        self.page += 1
        self.cursor = top - TIGHT
        return self


def question(b, stem="题干内容", opts=("A:甲", "B:乙", "C:丙", "D:丁"),
             answer="正确答案:B", expl="解析:因为如此", lead=LOOSE):
    b.add(stem, gap=lead, x1=524.3)
    for o in opts:
        b.add(o)
    if answer:
        b.add(answer, x1=120.9)
    if expl:
        b.add(expl, x1=180.0)
    return b


class TestMarkerRegexes:
    def test_option_marker(self):
        assert OPTION_RE.match("A:高新科技").group(1) == "A"

    def test_answer_marker(self):
        assert ANSWER_RE.match("正确答案:D").group(1) == "D"

    def test_bare_answer_marker(self):
        # 跨页时「正确」二字丢失，全库出现 3 次
        assert ANSWER_RE.match("答案:A").group(1) == "A"

    def test_answer_word_inside_explanation_is_not_a_marker(self):
        # 「故正确答案为B。」出现在解析正文里，不能命中
        assert ANSWER_RE.match("答案为B。") is None
        assert ANSWER_RE.match("答案选C。") is None


class TestBlockBreak:
    def test_large_gap_is_a_break(self):
        a = Line("上一行", 1, 100.0, 112.0, 70.8, 200.0)
        b = Line("下一行", 1, 145.0, 157.0, 70.8, 300.0)
        assert is_block_break(a, b)

    def test_tight_gap_is_not(self):
        a = Line("上一行", 1, 100.0, 112.0, 70.8, 200.0)
        b = Line("下一行", 1, 116.0, 128.0, 70.8, 300.0)
        assert not is_block_break(a, b)

    def test_cross_page_full_width_continues(self):
        # 上页末行顶到右边界 => 段落没完 => 续接
        a = Line("未完的一行", 1, 700.0, 712.0, 70.8, 524.3)
        b = Line("续接内容", 2, 70.0, 82.0, 70.8, 524.3)
        assert not is_block_break(a, b)

    def test_cross_page_short_line_breaks(self):
        a = Line("解析:结束了。", 1, 700.0, 712.0, 70.8, 150.0)
        b = Line("新题干开始", 2, 70.0, 82.0, 70.8, 524.3)
        assert is_block_break(a, b)


class TestSegment:
    def test_two_plain_questions(self):
        b = Builder()
        question(b, stem="第一题题干", answer="正确答案:B", lead=0.0)
        question(b, stem="第二题题干", answer="正确答案:C")
        qs = segment(b.lines)
        assert len(qs) == 2
        assert qs[0].answer_raw == "B"
        assert qs[1].answer_raw == "C"
        assert len(qs[0].option_lines) == 4

    def test_empty_explanation_then_next_question(self):
        b = Builder()
        question(b, stem="第一题", expl="解析:", lead=0.0)
        question(b, stem="第二题", answer="正确答案:D")
        qs = segment(b.lines)
        assert len(qs) == 2
        assert qs[0].explain_inline == ""
        assert "第二题" in "".join(l.text for l in qs[1].stem_lines)

    def test_multiline_explanation_is_kept_together(self):
        b = Builder()
        question(b, stem="第一题", expl="解析:第一步分析", lead=0.0)
        b.add("第二步对比选项，因此选B。", x1=400.0)   # 紧跟的续行
        question(b, stem="第二题")
        qs = segment(b.lines)
        assert len(qs) == 2
        assert len(qs[0].explain_lines) == 1

    def test_question_number_lines_are_captured(self):
        b = Builder()
        b.add("1", gap=0.0, x1=80.0)
        question(b, stem="有题号的题", lead=TIGHT)
        qs = segment(b.lines)
        assert qs[0].number == 1
        assert "有题号" in "".join(l.text for l in qs[0].stem_lines)

    def test_question_number_closes_previous_question(self):
        b = Builder()
        question(b, stem="第一题", expl="解析:", lead=0.0)
        b.add("7", gap=TIGHT, x1=80.0)      # 小间距，只能靠题号断开
        question(b, stem="第二题", lead=TIGHT)
        qs = segment(b.lines)
        assert len(qs) == 2
        assert qs[1].number == 7

    def test_image_question_without_text_options(self):
        # 图形推理题：题干一句话，没有任何选项行
        b = Builder()
        b.add("问号处的图形应该是：", gap=0.0, x1=180.0)
        b.add("正确答案:C", x1=120.0)
        b.add("解析:旋转规律", x1=180.0)
        qs = segment(b.lines)
        assert len(qs) == 1
        assert qs[0].option_lines == []
        assert qs[0].answer_raw == "C"

    def test_question_with_no_stem_at_all(self):
        # 整道题都画在图里，首个文本行就是答案
        b = Builder()
        b.add("正确答案:D", gap=0.0, x1=120.0)
        b.add("解析:黑加白的黑", x1=200.0)
        qs = segment(b.lines)
        assert len(qs) == 1
        assert qs[0].stem_lines == []
        assert qs[0].answer_pos[0] == 1          # 记录了答案行位置，供图片归属用

    def test_option_text_wraps_to_next_line(self):
        b = Builder()
        b.add("题干", gap=0.0, x1=524.3)
        b.add("A:这是一个很长的选项", x1=524.3)
        b.add("需要换行继续写完", x1=300.0)
        b.add("B:短选项", x1=200.0)
        b.add("正确答案:A", x1=120.0)
        qs = segment(b.lines)
        assert len(qs[0].option_lines) == 2
        assert len(qs[0].option_lines[0]) == 2   # 首个选项吃到了续行

    def test_section_header_splits_and_tags(self):
        b = Builder()
        b.add("言语理解推理题", gap=0.0, x1=180.0)
        question(b, stem="言语题")
        b.add("资料分析题", gap=LOOSE, x1=150.0)
        question(b, stem="资料题")
        qs = segment(b.lines)
        assert [q.section for q in qs] == ["言语理解推理题", "资料分析题"]

    def test_answer_split_across_pages(self):
        # p276 末尾是题干，p277 开头只剩「答案:A」
        b = Builder()
        b.add("问号处的图形应该是：", gap=0.0, x1=180.0)
        b.newpage()
        b.add("答案:A", gap=0.0, x1=120.0)
        b.add("解析:每行横着看", x1=200.0)
        qs = segment(b.lines)
        assert len(qs) == 1
        assert qs[0].answer_raw == "A"

    def test_stem_continues_across_pages(self):
        b = Builder()
        b.add("题干上半段一直写到右边界", gap=0.0, x1=524.3)
        b.newpage()
        b.add("题干下半段", gap=0.0, x1=300.0)
        b.add("A:甲")
        b.add("B:乙")
        b.add("正确答案:A", x1=120.0)
        qs = segment(b.lines)
        assert len(qs) == 1
        assert len(qs[0].stem_lines) == 2

    def test_answer_position_is_recorded(self):
        b = Builder()
        question(b, stem="题干", lead=0.0)
        qs = segment(b.lines)
        assert qs[0].answer_pos[0] == 1
        assert qs[0].answer_pos[1] > 0
