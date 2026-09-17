"""图片抽取：把 PDF 里的图表 / 图形选项渲染成 PNG。

**归属规则**：一张图属于「它下方第一个『正确答案』行」所在的题。

这条规则来自实际版式 —— 图表和图形选项永远排在题干之后、答案之前。
用它而不是「题块起止区间」，是因为图形推理题里有一批题**连题干文字
都没有**（整道题都画在图里），这类题的首个文本行就是「正确答案:X」，
按区间算会把自己的图全部漏掉、同时让上一题多吃一张。

两类题渲染方式不同：

* **资料分析题** —— 题干配 1~2 张图表，选项是文字。逐图渲染，
  题干末尾插入 ``[图片N]`` 占位，前端渲染 ``<img>``。
* **图形推理题** —— 选项本身就是图。把该题在同一页上所有图片的并集
  区域整块渲染成一张 PNG，与原书视觉一致；`options` 留空，前端提供
  A/B/C/D/E 纯字母按钮作答。

渲染用 PyMuPDF 而非抽取原始图片流：原始流可能带蒙版/透明通道、或被
拆成多个 XObject，直接渲染区域更稳。
"""
from __future__ import annotations

import os

import pymupdf as fitz
from PIL import Image

from normalize import is_watermark

ZOOM = 2.0          # 2x ≈ 144 DPI，兼顾清晰度与体积
PAD = 3.0           # 渲染区域外扩，避免切掉描边
PNG_COLORS = 256    # 调色板量化。图表和线稿色彩本就有限，实测体积降到 ~37%


def assign(questions, page_images: dict[int, list[dict]]) -> dict[int, dict[int, list[dict]]]:
    """把全部图片分配给题目。

    返回 {题目下标: {页码: [图片, ...]}}。
    """
    # 收集所有非水印图片，按文档顺序（页码, 纵向中心）排序
    items = []
    for page_no, imgs in page_images.items():
        for im in imgs:
            if is_watermark(im):
                continue
            items.append(((page_no, (im["top"] + im["bottom"]) / 2.0), page_no, im))
    items.sort(key=lambda t: t[0])

    # 答案行位置构成的有序分界线
    bounds = []
    for idx, q in enumerate(questions):
        pos = q.answer_pos if q.answer_pos[0] else q.end
        if pos[0]:
            bounds.append((pos, idx))
    bounds.sort()

    out: dict[int, dict[int, list[dict]]] = {}
    b = 0
    for key, page_no, im in items:
        while b < len(bounds) and bounds[b][0] < key:
            b += 1
        if b >= len(bounds):
            b = len(bounds) - 1          # 末尾的图归最后一题
        idx = bounds[b][1]
        out.setdefault(idx, {}).setdefault(page_no, []).append(im)

    for per_page in out.values():
        for imgs in per_page.values():
            imgs.sort(key=lambda im: (im["top"], im["x0"]))
    return out


def _render(doc, page_no: int, rect: tuple[float, float, float, float], out_path: str) -> None:
    page = doc[page_no - 1]
    pix = page.get_pixmap(clip=fitz.Rect(*rect), matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img.quantize(colors=PNG_COLORS, method=Image.MEDIANCUT).save(out_path, optimize=True)


def export(groups: dict[int, list[dict]], qid: str, doc, out_dir: str, whole_block: bool) -> list[str]:
    """导出一道题的图片，返回相对 data/ 的路径列表。"""
    if not groups:
        return []

    os.makedirs(out_dir, exist_ok=True)
    paths: list[str] = []

    for page_no, imgs in sorted(groups.items()):
        if whole_block:
            rect = (
                min(im["x0"] for im in imgs) - PAD,
                min(im["top"] for im in imgs) - PAD,
                max(im["x1"] for im in imgs) + PAD,
                max(im["bottom"] for im in imgs) + PAD,
            )
            name = f"{qid}-p{page_no}.png"
            _render(doc, page_no, rect, os.path.join(out_dir, name))
            paths.append(f"images/{name}")
        else:
            for k, im in enumerate(imgs, 1):
                rect = (im["x0"] - PAD, im["top"] - PAD, im["x1"] + PAD, im["bottom"] + PAD)
                name = f"{qid}-p{page_no}-{k}.png"
                _render(doc, page_no, rect, os.path.join(out_dir, name))
                paths.append(f"images/{name}")
    return paths
