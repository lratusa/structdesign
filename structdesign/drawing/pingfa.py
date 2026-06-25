"""
平法（16G101）梁配筋图雏形 —— 集中标注 + 配筋立面 SVG。

生成可在浏览器/查看器直接打开的 SVG：梁立面 + 上下纵筋 + 箍筋 + 集中标注引出。
钢筋等级符号：HPB300=φ, HRB400=C, HRB500=E（平法常用）。DWG/DXF 后续接入。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List


# 钢筋牌号 → 平法符号
GRADE_SYM = {"HPB300": "φ", "HRB335": "B", "HRB400": "C", "HRB500": "E"}


def sym(grade: str) -> str:
    return GRADE_SYM.get(grade.upper(), "C")


@dataclass
class BeamPingfa:
    beam_id: str = "KL1"
    n_span: int = 1
    b: float = 300
    h: float = 600
    length_mm: float = 6000
    stirrup_grade: str = "HPB300"
    stirrup_d: int = 8
    s_dense: int = 100        # 加密区间距
    s_normal: int = 200       # 非加密区间距
    legs: int = 2
    top_through: str = "2C22"      # 上部通长筋
    support_top: str = "6C22"      # 支座上部筋(原位)
    bottom: str = "4C25"           # 下部纵筋(原位,跨中)
    side_bars: Optional[str] = "G4C12"   # 侧面构造/抗扭筋

    def concentrated_annotation(self) -> List[str]:
        """平法集中标注（多行）。"""
        lines = [f"{self.beam_id}({self.n_span}) {int(self.b)}×{int(self.h)}",
                 f"φ{self.stirrup_d}@{self.s_dense}/{self.s_normal}({self.legs})",
                 f"{self.top_through}"]
        if self.side_bars:
            lines.append(self.side_bars)
        return lines


def beam_svg(p: BeamPingfa) -> str:
    """生成梁配筋立面 SVG（含集中标注、原位标注、箍筋、尺寸）。"""
    # 画布
    margin = 60
    beam_px_len = 760
    scale = beam_px_len / p.length_mm
    beam_px_h = max(40, p.h * scale * 3)   # 竖向放大3倍便于看清
    W = beam_px_len + 2 * margin
    H = int(beam_px_h + 260)
    x0, y0 = margin, 150
    x1, y1 = x0 + beam_px_len, y0 + beam_px_h

    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="sans-serif">')
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')

    # 集中标注（左上，带引出线）
    ann = p.concentrated_annotation()
    ax, ay = x0 + 60, 30
    for i, line in enumerate(ann):
        weight = "bold" if i == 0 else "normal"
        s.append(f'<text x="{ax}" y="{ay + i*18}" font-size="15" font-weight="{weight}">{line}</text>')
    # 引出线指向梁
    s.append(f'<polyline points="{ax-8},{ay-12} {ax-30},{ay-12} {x0+beam_px_len*0.18},{y0}" '
             f'fill="none" stroke="black" stroke-width="1"/>')
    s.append(f'<circle cx="{x0+beam_px_len*0.18}" cy="{y0}" r="2.5" fill="black"/>')

    # 梁轮廓
    s.append(f'<rect x="{x0}" y="{y0}" width="{beam_px_len}" height="{beam_px_h}" '
             f'fill="#f5f5f5" stroke="black" stroke-width="1.5"/>')
    # 支座(柱)示意：两端及中间
    for k in range(p.n_span + 1):
        cx = x0 + beam_px_len * k / p.n_span
        s.append(f'<rect x="{cx-9}" y="{y1}" width="18" height="26" fill="#ccc" stroke="black"/>')

    # 上部纵筋（贯通线）
    s.append(f'<line x1="{x0+4}" y1="{y0+7}" x2="{x1-4}" y2="{y0+7}" stroke="#b00" stroke-width="2.2"/>')
    # 下部纵筋
    s.append(f'<line x1="{x0+4}" y1="{y1-7}" x2="{x1-4}" y2="{y1-7}" stroke="#06c" stroke-width="2.2"/>')

    # 箍筋（竖线）：两端加密，中部非加密
    dense_zone = beam_px_len * 0.18
    def draw_stirrups(xa, xb, step_mm):
        step_px = max(6, step_mm * scale)
        x = xa
        while x <= xb:
            s.append(f'<line x1="{x:.1f}" y1="{y0+3}" x2="{x:.1f}" y2="{y1-3}" stroke="#888" stroke-width="0.8"/>')
            x += step_px
    draw_stirrups(x0+6, x0+dense_zone, p.s_dense)
    draw_stirrups(x0+dense_zone, x1-dense_zone, p.s_normal)
    draw_stirrups(x1-dense_zone, x1-6, p.s_dense)

    # 原位标注：支座上部筋（梁顶，端部上方）
    s.append(f'<text x="{x0+10}" y="{y0-6}" font-size="13" fill="#b00">{p.support_top}</text>')
    s.append(f'<text x="{x1-90}" y="{y0-6}" font-size="13" fill="#b00">{p.support_top}</text>')
    # 跨中下部筋（梁底下方）
    s.append(f'<text x="{(x0+x1)/2-30}" y="{y1+20}" font-size="13" fill="#06c">{p.bottom}</text>')

    # 尺寸线
    yd = y1 + 48
    s.append(f'<line x1="{x0}" y1="{yd}" x2="{x1}" y2="{yd}" stroke="black" stroke-width="0.8"/>')
    for xx in (x0, x1):
        s.append(f'<line x1="{xx}" y1="{yd-5}" x2="{xx}" y2="{yd+5}" stroke="black" stroke-width="0.8"/>')
    s.append(f'<text x="{(x0+x1)/2-40}" y="{yd+16}" font-size="13">{int(p.length_mm)} mm</text>')

    # 图名
    s.append(f'<text x="{margin}" y="{H-14}" font-size="12" fill="#555">'
             f'平法配筋图(雏形) · {p.beam_id} · 上部红/下部蓝/箍筋灰 · GB 16G101</text>')
    s.append('</svg>')
    return "\n".join(s)


def save_beam_svg(p: BeamPingfa, path: str) -> str:
    svg = beam_svg(p)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return path
