#!/usr/bin/env python3
"""北森测评题库 PDF -> questions.json

用法:
    python parser/parse_pdf.py --input raw/xxx.pdf --out data/questions.json

流水线: 归一化(normalize) -> 题块切分(segment) -> 结构化(structure) -> 图片导出(images)
未能识别的残段全部写入 data/unmatched.txt，附页码与原因，方便人工回看。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pdfplumber
import pymupdf

from normalize import extract_lines
from schema import TYPE_LABELS
from segment import RawQuestion, segment
from structure import build, merge_lines

import images as img_mod

MERGE_MIN_LEN = 15   # 短于此长度的孤块不并入上一题，直接进回收池


def recycle(raws: list[RawQuestion]) -> tuple[list[RawQuestion], list[tuple[str, str]]]:
    """处理没有答案的孤块。

    公式较多的解析会因为行距变大被切开，这类残段要并回上一题；
    但只在**同章节**内合并 —— 章节首部的说明文字（如「图形题选项
    从上往下数」）若并入上一章节末题就是污染。
    """
    kept: list[RawQuestion] = []
    junk: list[tuple[str, str]] = []

    for raw in raws:
        if raw.answer_raw:
            kept.append(raw)
            continue

        text = merge_lines(raw.stem_lines)
        prev = kept[-1] if kept else None
        same_section = prev is not None and prev.section == raw.section
        mergeable = (
            prev is not None
            and same_section
            and prev.answer_raw
            and len(text) >= MERGE_MIN_LEN
            and not text.replace("-", "").replace("—", "").isdigit()
        )
        if mergeable:
            prev.explain_lines.extend(raw.stem_lines)
        else:
            reason = "章节说明或索引行" if not same_section or len(text) < MERGE_MIN_LEN else "无答案标记"
            junk.append((f"p{raw.start[0]}", f"[{reason}] {text}"))
    return kept, junk


def main() -> int:
    ap = argparse.ArgumentParser(description="解析北森测评题库 PDF")
    ap.add_argument("--input", required=True, help="输入 PDF 路径")
    ap.add_argument("--out", default="data/questions.json", help="输出 JSON 路径")
    ap.add_argument("--images", default=None, help="图片输出目录，默认 <out目录>/images")
    ap.add_argument("--no-images", action="store_true", help="跳过图片导出（快速迭代用）")
    args = ap.parse_args()

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    img_dir = args.images or os.path.join(out_dir, "images")
    os.makedirs(out_dir, exist_ok=True)

    print(f"[1/4] 读取 {args.input}")
    pdf = pdfplumber.open(args.input)
    lines = []
    page_images: dict[int, list[dict]] = {}
    for i, page in enumerate(pdf.pages):
        no = i + 1
        lines.extend(extract_lines(page, no))
        page_images[no] = page.images
        if no % 50 == 0:
            print(f"      ...已读 {no}/{len(pdf.pages)} 页")
    print(f"      共 {len(lines)} 个视觉行, {len(pdf.pages)} 页")

    print("[2/4] 切分题块")
    raws = segment(lines)
    raws, junk = recycle(raws)
    print(f"      切出 {len(raws)} 道题, 回收池 {len(junk)} 条")

    print("[3/4] 结构化")
    seen: set[str] = set()
    questions = []
    warn_log: list[tuple[str, str]] = []
    for raw in raws:
        q, warns = build(raw, seen)
        questions.append((q, raw))
        for w in warns:
            warn_log.append((f"p{raw.start[0]}", f"[{q.id}] {w}"))

    if args.no_images:
        print("[4/4] 跳过图片导出")
    else:
        print("[4/4] 导出图片")
        doc = pymupdf.open(args.input)
        assigned = img_mod.assign([r for _, r in questions], page_images)
        n_img = 0
        for idx, (q, raw) in enumerate(questions):
            whole = not q.options            # 图形推理题：整块截图
            paths = img_mod.export(assigned.get(idx, {}), q.id, doc, img_dir, whole_block=whole)
            if paths:
                q.images = paths
                # 题干里插入占位符，前端按顺序渲染
                marks = "".join(f"[图片{i}]" for i in range(1, len(paths) + 1))
                q.stem = (q.stem + marks) if q.stem else marks
                n_img += len(paths)
            if idx % 100 == 0 and idx:
                print(f"      ...已处理 {idx}/{len(questions)} 题")
        doc.close()
        print(f"      导出 {n_img} 张图片 -> {img_dir}")

    payload = [q.to_dict() for q, _ in questions]
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    unmatched_path = os.path.join(out_dir, "unmatched.txt")
    with open(unmatched_path, "w", encoding="utf-8") as fh:
        fh.write("# 未能结构化的残段与告警，供人工回看\n")
        fh.write(f"# 源文件: {args.input}\n\n")
        fh.write(f"## 回收池 ({len(junk)} 条)\n")
        for page, text in junk:
            fh.write(f"{page}\t{text}\n")
        fh.write(f"\n## 结构化告警 ({len(warn_log)} 条)\n")
        for page, text in warn_log:
            fh.write(f"{page}\t{text}\n")

    # ---- 统计报告 ----
    print("\n===== 解析结果 =====")
    print(f"题目总数: {len(payload)}")
    by_type = Counter(q["type"] for q in payload)
    for t, n in by_type.most_common():
        print(f"  {TYPE_LABELS.get(t, t)}: {n}")
    by_sec = Counter(q["tags"][0] if q["tags"] else "(无章节)" for q in payload)
    print("章节分布:")
    for s, n in by_sec.most_common():
        print(f"  {s}: {n}")

    # 完整率分两类口径统计：
    #   文字选择题 —— 题干 + 选项 + 答案 齐备才算完整
    #   图片选项题 —— 选项本就是图，有答案 + 有图即算完整
    text_q = [q for q in payload if q["options"]]
    img_q = [q for q in payload if not q["options"]]
    text_ok = [q for q in text_q if q["stem"] and q["answer"]]
    img_ok = [q for q in img_q if q["answer"] and q["images"]]

    print(f"带图题目: {sum(1 for q in payload if q['images'])}")
    print(f"有解析: {sum(1 for q in payload if q['explanation'])}")
    thin = [q for q in text_q if len(q["options"]) < 4]
    print(f"选项不足 4 个(原书即缺失): {len(thin)}")

    print("\n===== 完整率 =====")
    rates = []
    if text_q:
        r = len(text_ok) / len(text_q) * 100
        rates.append(r)
        print(f"文字选择题: {len(text_ok)}/{len(text_q)} = {r:.1f}%")
    if img_q:
        r = len(img_ok) / len(img_q) * 100
        rates.append(r)
        print(f"图片选项题: {len(img_ok)}/{len(img_q)} = {r:.1f}%")
    if rates and min(rates) < 95.0:
        print("  !! 低于 95% 验收线，请查看 unmatched.txt")
    print(f"\n输出: {args.out}")
    print(f"回收池: {unmatched_path} ({len(junk)} 残段, {len(warn_log)} 告警)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
