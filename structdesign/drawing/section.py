"""
截面大样（梁/柱横截面 SVG）—— 显示纵筋点位、箍筋、尺寸标注。
"""
from __future__ import annotations


def section_svg(b, h, n_top, n_bot, d_main, stirrup_d=8, cover=25,
                title="截面大样", n_side=0) -> str:
    """矩形截面配筋大样。n_top/n_bot 顶/底纵筋根数，n_side 每侧腰筋数。"""
    scale = min(360.0 / b, 360.0 / h)
    W, H = b * scale + 160, h * scale + 120
    x0, y0 = 80, 60
    bw, bh = b * scale, h * scale
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
         f'viewBox="0 0 {W:.0f} {H:.0f}" font-family="sans-serif">',
         f'<rect width="{W:.0f}" height="{H:.0f}" fill="white"/>',
         f'<text x="{x0}" y="30" font-size="15" font-weight="bold">{title}　{int(b)}×{int(h)}</text>']
    # 截面轮廓
    s.append(f'<rect x="{x0}" y="{y0}" width="{bw:.1f}" height="{bh:.1f}" '
             f'fill="#f7f7f7" stroke="black" stroke-width="2"/>')
    # 箍筋(内边框)
    c = cover * scale
    s.append(f'<rect x="{x0+c:.1f}" y="{y0+c:.1f}" width="{bw-2*c:.1f}" height="{bh-2*c:.1f}" '
             f'fill="none" stroke="#c33" stroke-width="1.5"/>')
    # 纵筋点位
    r = max(3, d_main * scale / 2)
    def row(n, yy, color):
        if n <= 0:
            return
        xs0, xs1 = x0 + c + r, x0 + bw - c - r
        for i in range(n):
            xx = xs0 if n == 1 else xs0 + (xs1 - xs0) * i / (n - 1)
            s.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="{r:.1f}" fill="{color}"/>')
    row(n_top, y0 + c + r, "#06c")
    row(n_bot, y0 + bh - c - r, "#b00")
    # 腰筋(两侧)
    if n_side > 0:
        ys0, ys1 = y0 + c + r, y0 + bh - c - r
        for i in range(1, n_side + 1):
            yy = ys0 + (ys1 - ys0) * i / (n_side + 1)
            s.append(f'<circle cx="{x0+c+r:.1f}" cy="{yy:.1f}" r="{r*0.8:.1f}" fill="#999"/>')
            s.append(f'<circle cx="{x0+bw-c-r:.1f}" cy="{yy:.1f}" r="{r*0.8:.1f}" fill="#999"/>')
    # 尺寸
    s.append(f'<text x="{x0+bw/2-20:.1f}" y="{y0+bh+28:.1f}" font-size="13">{int(b)}</text>')
    s.append(f'<text x="{x0-50:.1f}" y="{y0+bh/2:.1f}" font-size="13">{int(h)}</text>')
    s.append(f'<text x="{x0}" y="{H-12:.0f}" font-size="11" fill="#555">'
             f'上{n_top}D{int(d_main)} 下{n_bot}D{int(d_main)} 箍D{int(stirrup_d)}</text>')
    s.append('</svg>')
    return "\n".join(s)


def save_section_svg(path, **kw):
    with open(path, "w", encoding="utf-8") as f:
        f.write(section_svg(**kw))
    return path
