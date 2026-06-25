"""
平法梁配筋图 DXF 导出（含批量整楼出图）。

复用 BeamPingfa 数据，画成 DXF 实体：梁轮廓、上/下纵筋、箍筋、集中标注、原位标注、尺寸。
图层：BEAM(轮廓) / REBAR_TOP / REBAR_BOT / STIRRUP / TEXT / DIM。
"""
from __future__ import annotations
from typing import List
from .dxf import DXFDoc
from .pingfa import BeamPingfa


def draw_beam(doc: DXFDoc, p: BeamPingfa, x0=0.0, y0=0.0):
    """在 doc 上以 (x0,y0) 为梁左下角画一根梁(真实 mm 尺度)。"""
    L = p.length_mm
    h = p.h
    # 轮廓
    doc.add_rect(x0, y0, L, h, layer="BEAM")
    # 上/下纵筋
    doc.add_line(x0 + 30, y0 + h - 30, x0 + L - 30, y0 + h - 30, layer="REBAR_TOP")
    doc.add_line(x0 + 30, y0 + 30, x0 + L - 30, y0 + 30, layer="REBAR_BOT")
    # 箍筋：两端加密 s_dense，中部 s_normal
    dense = L * 0.2

    def stirrups(xa, xb, s):
        x = xa
        while x <= xb:
            doc.add_line(x, y0 + 20, x, y0 + h - 20, layer="STIRRUP")
            x += s
    stirrups(x0 + 40, x0 + dense, p.s_dense)
    stirrups(x0 + dense, x0 + L - dense, p.s_normal)
    stirrups(x0 + L - dense, x0 + L - 40, p.s_dense)
    # 集中标注(梁上方，每行文字高度~120mm 便于真实尺度查看)
    th = max(80, h * 0.18)
    ann = p.concentrated_annotation()
    for i, line in enumerate(ann):
        doc.add_text(x0 + L * 0.1, y0 + h + 60 + (len(ann) - i) * (th * 1.4), line, height=th, layer="TEXT")
    # 原位标注
    doc.add_text(x0 + 40, y0 + h + 30, p.support_top, height=th * 0.9, layer="TEXT")
    doc.add_text(x0 + L - 40 - th * 4, y0 + h + 30, p.support_top, height=th * 0.9, layer="TEXT")
    doc.add_text(x0 + L / 2 - th * 2, y0 - th * 1.6, p.bottom, height=th * 0.9, layer="TEXT")
    # 尺寸线
    yd = y0 - th * 3
    doc.add_line(x0, yd, x0 + L, yd, layer="DIM")
    doc.add_text(x0 + L / 2 - th * 2, yd + 20, f"{int(L)}", height=th * 0.9, layer="DIM")


def beam_dxf(p: BeamPingfa) -> DXFDoc:
    doc = DXFDoc()
    draw_beam(doc, p)
    return doc


def batch_beams_dxf(beams: List[BeamPingfa], v_gap=1500.0) -> DXFDoc:
    """整楼批量：多根梁竖向排布到一张 DXF。"""
    doc = DXFDoc()
    y = 0.0
    for p in beams:
        draw_beam(doc, p, x0=0.0, y0=y)
        y += p.h + v_gap
    return doc
