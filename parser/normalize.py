"""阶段 1：文本与版面归一化。

设计要点：**匹配用的文本和存储用的文本分开**。
全角转半角如果无脑用 NFKC，会把中文的「，」变成 ASCII 的「,」，
把正文改得面目全非。所以这里只做定向映射：字母、数字、冒号，
其余字符（尤其是中文标点）原样保留。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 版面常量（由 2025北森测评题库 实测得出，见 README「版式勘察」）
RIGHT_MARGIN = 524.3     # 正文右边界；满行会顶到这里
LEFT_MARGIN = 70.8       # 正文左边界
GAP_NEW_BLOCK = 15.0     # 题间距实测 33~34pt，题内行距 3.2~4.3pt，阈值取中间
FOOTER_TOP = 780.0       # 页脚水印所在高度
PAGE_HEIGHT = 842.0

# 定向全角→半角映射表
_FULLWIDTH = {}
for _a, _b in ((0xFF21, 0x41), (0xFF41, 0x61), (0xFF10, 0x30)):  # Ａ-Ｚ ａ-ｚ ０-９
    _n = 26 if _a != 0xFF10 else 10
    for _i in range(_n):
        _FULLWIDTH[_a + _i] = _b + _i
_FULLWIDTH[0xFF1A] = 0x3A   # ：-> :
_FULLWIDTH[0xFF0E] = 0x2E   # ．-> .


def normalize_for_match(s: str) -> str:
    """只用于正则匹配的归一化，不写回 questions.json。"""
    return s.translate(_FULLWIDTH)


def clean_text(s: str) -> str:
    """存储用的轻量清洗：压缩空白、去首尾空格。保留中文标点原貌。"""
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


_CJK = re.compile(r"[　-鿿＀-￯]")
_WORD_END = re.compile(r"[A-Za-z]$")
_WORD_START = re.compile(r"^[A-Za-z]")


def join_wrapped(prev: str, nxt: str) -> str:
    """合并 PDF 软换行。

    只在两侧都是拉丁字母时补空格（如 "(Pareto" + "efficiency)"）。
    实测全库仅 16 处这类边界，且绝大多数是选项行、本就不参与合并；
    数字侧一律不补，否则 "38.4" + "%的速度" 会被拆成 "38.4 %的速度"。
    """
    if not prev:
        return nxt
    if not nxt:
        return prev
    if _WORD_END.search(prev) and _WORD_START.match(nxt):
        return prev + " " + nxt
    return prev + nxt


@dataclass
class Line:
    """一个视觉行，带版面坐标。坐标是切分题块的主要依据。"""
    text: str
    page: int          # 1-based
    top: float
    bottom: float
    x0: float
    x1: float

    @property
    def match_text(self) -> str:
        return normalize_for_match(self.text)

    @property
    def is_full_width(self) -> bool:
        """是否满行。满行说明段落还没结束，用于跨页续接判断。"""
        return self.x1 >= RIGHT_MARGIN - 8.0


def is_watermark(img: dict) -> bool:
    """页脚水印：每页右下角固定的 106x32 图章，必须排除。"""
    return (
        img["x0"] > 460.0
        and img["top"] > FOOTER_TOP
        and img["width"] < 150.0
        and img["height"] < 60.0
    )


def extract_lines(page, page_no: int) -> list[Line]:
    """把 pdfplumber 的 word 聚合成带坐标的视觉行。"""
    words = page.extract_words(use_text_flow=True)
    buckets: dict[float, list] = {}
    for w in words:
        buckets.setdefault(round(w["top"], 0), []).append(w)

    lines: list[Line] = []
    for key in sorted(buckets):
        group = sorted(buckets[key], key=lambda w: w["x0"])
        text = clean_text("".join(w["text"] for w in group))
        if not text:
            continue
        lines.append(
            Line(
                text=text,
                page=page_no,
                top=key,
                bottom=max(w["bottom"] for w in group),
                x0=group[0]["x0"],
                x1=max(w["x1"] for w in group),
            )
        )
    return drop_page_furniture(lines)


def drop_page_furniture(lines: list[Line]) -> list[Line]:
    """丢弃页眉页脚噪声。本 PDF 无文字页码，但保留这层防御。"""
    return [ln for ln in lines if not (ln.top > FOOTER_TOP and re.fullmatch(r"\d{1,4}", ln.text))]
