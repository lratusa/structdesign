"""出图：建模+计算结果 → CAD 配筋平面图（DXF）+ 预览(PNG)+ 出版(PDF)。

含：轴网+轴号、柱(KZ编号，详见柱表)、梁**逐跨原位标注**(集中标注 + 跨中下部筋 + 支座上部负筋)、
墙(Q)、**柱表**(KZ 截面/纵筋/箍筋/轴压比汇总)。平法代号 KZ/KL/Q 为国标，文字 ASCII（CAD/预览均清晰）。
"""
from __future__ import annotations
import ezdxf

C_AXIS, C_COL, C_BEAM, C_WALL = 1, 2, 3, 5
RGB_W = (255, 255, 255)
RGB_Y = (255, 230, 120)
RGB_G = (140, 230, 150)


def _san(s):
    return str(s).replace("×", "x").replace("－", "-")


def _governing(result, with_rebar):
    cols, beams, walls = {}, {}, {}
    if not (result and with_rebar):
        return cols, beams, walls
    for m in result.members:
        body = m["id"][1:].split("_")
        if m["kind"] == "柱":
            k = (body[0], body[1])
            if k not in cols or m.get("rho", 0) > cols[k].get("rho", 0):
                cols[k] = m
        elif m["kind"] == "墙":
            k = (body[0], body[1])
            if k not in walls or m.get("mu", 0) > walls[k].get("mu", 0):
                walls[k] = m
        elif m["kind"] == "梁":
            bi = body[0]
            if bi not in beams or m.get("As", 0) > beams[bi].get("As", 0):
                beams[bi] = m
    return cols, beams, walls


def _txt(msp, x, y, s, h, layer, rgb=RGB_W, align="MIDDLE_CENTER"):
    t = msp.add_text(_san(s), dxfattribs={"layer": layer, "height": h})
    t.dxf.true_color = ezdxf.rgb2int(rgb)
    t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment[align])
    return t


def _col_schedule(project, cols_r):
    """按(截面,纵筋)归并 → KZ1.. ；返回 {(kx,ky):name}, 表行 list。"""
    name_of = {}
    groups, order = {}, []
    for c in project.floor.columns:
        key2 = (str(round(c.x)), str(round(c.y)))
        m = cols_r.get(key2)
        gkey = (m["sec"], m["bars"]) if m else (f"{int(c.b)}x{int(c.h)}", "-")
        if gkey not in groups:
            groups[gkey] = {"sec": gkey[0], "bars": gkey[1],
                            "mu": (m.get("mu", 0) if m else 0), "n": 0,
                            "stirrup": (m.get("stirrup", "C8@100/200") if m else "C8@100/200")}
            order.append(gkey)
        groups[gkey]["n"] += 1
        if m:
            groups[gkey]["mu"] = max(groups[gkey]["mu"], m.get("mu", 0))
        name_of[key2] = None  # 占位，下面填
    for i, gkey in enumerate(order):
        groups[gkey]["name"] = f"KZ{i+1}"
    for c in project.floor.columns:
        key2 = (str(round(c.x)), str(round(c.y)))
        m = cols_r.get(key2)
        gkey = (m["sec"], m["bars"]) if m else (f"{int(c.b)}x{int(c.h)}", "-")
        name_of[key2] = groups[gkey]["name"]
    rows = [(groups[k]["name"], groups[k]["sec"], groups[k]["bars"],
             groups[k]["stirrup"], f"{groups[k]['mu']:.2f}", groups[k]["n"]) for k in order]
    return name_of, rows


def _wall_schedule(project, walls_r):
    """墙施工图：按(截面,竖向分布筋,水平分布筋,边缘构件纵筋)归并 → Q1.. ；返回 {(mx,my):name}, 表行。"""
    name_of = {}
    groups, order = {}, []
    for w in project.floor.walls:
        mx, my = (w.x1 + w.x2) / 2.0, (w.y1 + w.y2) / 2.0
        key2 = (str(round(mx)), str(round(my)))
        m = walls_r.get(key2)
        if m:
            gkey = (m["sec"], m.get("vdist", "-"), m.get("hdist", "-"), m.get("bars", "-"))
            grp = dict(sec=m["sec"], vdist=m.get("vdist", "-"), hdist=m.get("hdist", "-"),
                       be=m.get("bars", "-"), mu=m.get("mu", 0.0), be_len=m.get("be_len", 0.0))
        else:
            L = ((w.x2 - w.x1) ** 2 + (w.y2 - w.y1) ** 2) ** 0.5
            gkey = (f"{int(w.t)}x{int(L)}", "-", "-", "-")
            grp = dict(sec=gkey[0], vdist="-", hdist="-", be="-", mu=0.0, be_len=0.0)
        if gkey not in groups:
            groups[gkey] = dict(grp, n=0); order.append(gkey)
        groups[gkey]["n"] += 1
        groups[gkey]["mu"] = max(groups[gkey]["mu"], grp["mu"])
        name_of[key2] = None
    for i, gkey in enumerate(order):
        groups[gkey]["name"] = f"Q{i+1}"
    for w in project.floor.walls:
        mx, my = (w.x1 + w.x2) / 2.0, (w.y1 + w.y2) / 2.0
        key2 = (str(round(mx)), str(round(my)))
        m = walls_r.get(key2)
        if m:
            gkey = (m["sec"], m.get("vdist", "-"), m.get("hdist", "-"), m.get("bars", "-"))
        else:
            L = ((w.x2 - w.x1) ** 2 + (w.y2 - w.y1) ** 2) ** 0.5
            gkey = (f"{int(w.t)}x{int(L)}", "-", "-", "-")
        name_of[key2] = groups[gkey]["name"]
    rows = [(groups[k]["name"], groups[k]["sec"], groups[k]["vdist"], groups[k]["hdist"],
             groups[k]["be"], f"{groups[k]['mu']:.2f}", groups[k]["n"]) for k in order]
    return name_of, rows


def _beam_schedule(beams_r):
    """跨构件钢筋归并：相同(截面+上/下纵筋+箍筋)的梁 → 同一 KL 编号。返回表行。"""
    groups, order = {}, []
    for m in beams_r.values():
        thru = m.get("thru", "")
        top = (f"{thru}/{m.get('bars_top','-')}" if thru else m.get("bars_top", "-"))
        gkey = (m["sec"], top, m.get("bars_bot", "-"), m.get("stirrup", "-"))
        if gkey not in groups:
            groups[gkey] = dict(sec=gkey[0], top=gkey[1], bot=gkey[2], stir=gkey[3], n=0)
            order.append(gkey)
        groups[gkey]["n"] += 1
    rows = []
    for i, k in enumerate(order):
        g = groups[k]
        rows.append((f"KL{i+1}", g["sec"], g["top"], g["bot"], g["stir"], g["n"]))
    return rows


def _perp(b):
    dx, dy = b.x2 - b.x1, b.y2 - b.y1
    L = (dx * dx + dy * dy) ** 0.5 or 1.0
    return (-dy / L, dx / L)


def _rev_cloud(msp, x0, y0, x1, y1, r, layer="FAIL"):
    """修订云线（不达标处常用标识）：沿矩形外框画外凸圆弧串(bulge)，红色。"""
    import math
    pts = []

    def edge(ax, ay, bx, by):
        L = math.hypot(bx - ax, by - ay)
        n = max(int(L / (1.6 * r)), 1)
        for k in range(n):
            t = k / n
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    edge(x0, y0, x1, y0); edge(x1, y0, x1, y1)
    edge(x1, y1, x0, y1); edge(x0, y1, x0, y0)        # CCW
    poly = [(px, py, 0.0, 0.0, 0.5) for (px, py) in pts]   # bulge=0.5 外凸
    try:
        msp.add_lwpolyline(poly, format="xyseb", close=True,
                           dxfattribs={"layer": layer, "color": 1})
    except Exception:
        msp.add_lwpolyline([(p[0], p[1]) for p in pts], close=True,
                           dxfattribs={"layer": layer, "color": 1})


def _mark_fail(msp, x0, y0, x1, y1, note, H):
    """云线 + 红色引注，标识一处不达标。"""
    pad = H * 1.0
    _rev_cloud(msp, x0 - pad, y0 - pad, x1 + pad, y1 + pad, H * 0.9)
    _txt(msp, (x0 + x1) / 2, y1 + pad + H * 1.1, note, H * 0.9, "FAIL", (255, 70, 70))


def export_plan(project, result, dxf_path, png_path=None, pdf_path=None, with_rebar=True):
    fl = project.floor
    cols_r, beams_r, walls_r = _governing(result, with_rebar)

    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    gx = sorted(project.grid.x) or sorted({round(c.x) for c in fl.columns})
    gy = sorted(project.grid.y) or sorted({round(c.y) for c in fl.columns})
    x0, x1 = (min(gx), max(gx)) if gx else (0, 0)
    y0, y1 = (min(gy), max(gy)) if gy else (0, 0)
    span = max(x1 - x0, y1 - y0, 1000)
    H = span / 90.0          # 字高(略减, 更清爽)
    bub = span / 28.0
    off = bub * 2.4
    # 轴线点画线比例(让点画线在 mm 图上可见)
    doc.header["$LTSCALE"] = max(span / 260.0, 12.0)
    AX = (150, 150, 165)     # 轴线: 暗灰蓝(不抢眼)
    for name, c, lt in [("AXIS", 8, "CENTER"), ("COLUMN", C_COL, "CONTINUOUS"),
                        ("BEAM", C_BEAM, "CONTINUOUS"), ("WALL", C_WALL, "CONTINUOUS"),
                        ("SLAB", 4, "CONTINUOUS"), ("SBOT", 3, "CONTINUOUS"),
                        ("STOP", 1, "CONTINUOUS"), ("TEXT", 7, "CONTINUOUS"),
                        ("TABLE", 7, "CONTINUOUS"), ("TITLE", 7, "CONTINUOUS"),
                        ("FRAME", 7, "CONTINUOUS"), ("FAIL", 1, "CONTINUOUS")]:
        if name not in doc.layers:
            try:
                doc.layers.add(name, color=c, linetype=lt)
            except Exception:
                doc.layers.add(name, color=c)

    # 轴网 + 轴号(点画线、暗色)
    for i, x in enumerate(gx):
        msp.add_line((x, y0 - off), (x, y1 + off), dxfattribs={"layer": "AXIS", "color": 8})
        for yy in (y0 - off, y1 + off):
            msp.add_circle((x, yy), bub, dxfattribs={"layer": "AXIS", "color": 8, "linetype": "CONTINUOUS"})
            _txt(msp, x, yy, str(i + 1), bub * 0.9, "AXIS", AX)
    for k, y in enumerate(gy):
        msp.add_line((x0 - off, y), (x1 + off, y), dxfattribs={"layer": "AXIS", "color": 8})
        for xx in (x0 - off, x1 + off):
            msp.add_circle((xx, y), bub, dxfattribs={"layer": "AXIS", "color": 8, "linetype": "CONTINUOUS"})
            _txt(msp, xx, y, chr(ord("A") + k), bub * 0.9, "AXIS", AX)

    # 楼板（轮廓 + LB 编号 + 底筋；详见板表）
    slabs = getattr(result, "slabs", []) if result else []
    for sd in slabs:
        x0s = min(sd["x1"], sd["x2"]); y0s = min(sd["y1"], sd["y2"])
        ws = abs(sd["x2"] - sd["x1"]); hs = abs(sd["y2"] - sd["y1"])
        msp.add_lwpolyline([(x0s, y0s), (x0s + ws, y0s), (x0s + ws, y0s + hs), (x0s, y0s + hs)],
                           close=True, dxfattribs={"layer": "SLAB"})
        _txt(msp, x0s + ws / 2, y0s + hs / 2 + H * 0.9,
             f"{sd['name']} h={sd['t']}", H * 0.85, "SLAB", RGB_W)
        # 平法 B/T 注写：B=板底贯通筋, T=支座板面负筋
        _txt(msp, x0s + ws / 2, y0s + hs / 2 - H * 0.2,
             f"B:X{sd['bars_x']} Y{sd['bars_y']}", H * 0.7, "SBOT", (150, 240, 160))
        _txt(msp, x0s + ws / 2, y0s + hs / 2 - H * 1.3,
             f"T:{sd.get('bars_x_top', sd['bars_x'])}", H * 0.7, "STOP", (255, 175, 95))

    # 墙（Q 编号，详见墙表；端部绘边缘构件区段）
    wname_of, wrows = _wall_schedule(project, walls_r)
    for w in fl.walls:
        msp.add_lwpolyline([(w.x1, w.y1), (w.x2, w.y2)],
                           dxfattribs={"layer": "WALL", "const_width": w.t})
        mx, my = (w.x1 + w.x2) / 2, (w.y1 + w.y2) / 2
        wm = walls_r.get((str(round(mx)), str(round(my))))
        nm = wname_of.get((str(round(mx)), str(round(my))), f"Q{int(w.t)}")
        _txt(msp, mx, my + w.t, nm, H, "WALL", RGB_W)
        # 墙两端边缘构件(GBZ/YBZ)区段——加粗短段
        be_len = (wm.get("be_len", 0.0) if wm else 0.0) or max(w.t, 400)
        L = ((w.x2 - w.x1) ** 2 + (w.y2 - w.y1) ** 2) ** 0.5 or 1.0
        ux, uy = (w.x2 - w.x1) / L, (w.y2 - w.y1) / L
        for (ex, ey, sgn) in [(w.x1, w.y1, 1), (w.x2, w.y2, -1)]:
            bx, by = ex + sgn * ux * be_len, ey + sgn * uy * be_len
            msp.add_lwpolyline([(ex, ey), (bx, by)],
                               dxfattribs={"layer": "WALL", "const_width": w.t * 1.6})

    # 梁：逐跨原位标注（按轴线归并为连续梁 KLn）
    _draw_beams(msp, fl, beams_r, H)

    # 柱：方框 + KZ 编号（详见柱表）
    name_of, rows = _col_schedule(project, cols_r)
    for c in fl.columns:
        msp.add_lwpolyline(
            [(c.x - c.b / 2, c.y - c.h / 2), (c.x + c.b / 2, c.y - c.h / 2),
             (c.x + c.b / 2, c.y + c.h / 2), (c.x - c.b / 2, c.y + c.h / 2)],
            close=True, dxfattribs={"layer": "COLUMN"})
        nm = name_of.get((str(round(c.x)), str(round(c.y))), f"{int(c.b)}x{int(c.h)}")
        _txt(msp, c.x, c.y, nm, H * 0.95, "COLUMN", RGB_Y)

    # ---- 不达标构件标识（修订云线 + 红色引注；承载力/构造不满足处） ----
    n_fail = 0
    for c in fl.columns:
        m = cols_r.get((str(round(c.x)), str(round(c.y))))
        if m and not m.get("ok", True):
            nm = name_of.get((str(round(c.x)), str(round(c.y))), "KZ")
            rs = f"{nm} 轴压比{m.get('mu',0):.2f}超限" if m.get("mu", 0) > 0.85 else f"{nm} 配筋超限"
            _mark_fail(msp, c.x - c.b / 2, c.y - c.h / 2, c.x + c.b / 2, c.y + c.h / 2, rs, H)
            n_fail += 1
    for w in fl.walls:
        mx, my = (w.x1 + w.x2) / 2, (w.y1 + w.y2) / 2
        m = walls_r.get((str(round(mx)), str(round(my))))
        if m and not m.get("ok", True):
            wxa, wya = min(w.x1, w.x2) - w.t, min(w.y1, w.y2) - w.t
            wxb, wyb = max(w.x1, w.x2) + w.t, max(w.y1, w.y2) + w.t
            _mark_fail(msp, wxa, wya, wxb, wyb,
                       f"{wname_of.get((str(round(mx)),str(round(my))),'Q')} 轴压比超限", H)
            n_fail += 1
    for bi, b in enumerate(fl.beams):
        m = beams_r.get(str(bi))
        if m and not m.get("ok", True):
            bxa, bya = min(b.x1, b.x2), min(b.y1, b.y2)
            bxb, byb = max(b.x1, b.x2), max(b.y1, b.y2)
            _mark_fail(msp, bxa - H, bya - H, bxb + H, byb + H, "KL 承载力超限", H)
            n_fail += 1
    if n_fail:
        _txt(msp, x0, y0 - off - bub * 1.2,
             f"▲ 红色云线处 {n_fail} 个构件承载力/构造不满足，需加大截面或配筋（详见计算书）",
             H * 0.95, "FAIL", (255, 70, 70), align="MIDDLE_LEFT")

    # ---- 明细表（plan 下方，左列依次堆叠；表宽限制为 0.62·span 以便右侧放说明） ----
    tw_tbl = span * 0.62
    tbl_top = y0 - off - bub * 3.2
    _draw_col_table(msp, rows, x0, tbl_top, tw_tbl, H)
    cur = tbl_top - (len(rows) + 2) * (H * 2.3) - H * 3.0
    if slabs:
        seen, srows = set(), []
        for sd in slabs:
            if sd["name"] not in seen:
                seen.add(sd["name"])
                srows.append((sd["name"], f"{int(sd['Lx']*1000)}x{int(sd['Ly']*1000)}",
                              sd["t"], sd["kind"], sd["bars_x"], sd["bars_y"], sd["qty"]))
        scw = [tw_tbl * f for f in (0.10, 0.18, 0.08, 0.12, 0.16, 0.16, 0.10)]
        _table(msp, x0, cur, scw, H, "SLAB SCHEDULE / 板表",
               ["Mark", "LxxLy", "h", "Type", "X-btm", "Y-btm", "Qty"], srows)
        cur = cur - (len(srows) + 2) * (H * 2.3) - H * 3.0
    if wrows:
        wcw = [tw_tbl * f for f in (0.09, 0.16, 0.18, 0.18, 0.17, 0.10, 0.08)]
        _table(msp, x0, cur, wcw, H, "WALL SCHEDULE / 墙表 (Q: bw x lw)",
               ["Mark", "bw x lw", "V-dist", "H-dist", "Edge bars", "n_ratio", "Qty"], wrows)
        cur = cur - (len(wrows) + 2) * (H * 2.3) - H * 3.0
    brows = _beam_schedule(beams_r)
    if brows:
        bcw = [tw_tbl * f for f in (0.10, 0.15, 0.24, 0.21, 0.20, 0.10)]
        _table(msp, x0, cur, bcw, H,
               f"BEAM SCHEDULE / 梁表 ({len(beams_r)}->{len(brows)} marks)",
               ["Mark", "b x h", "Top thru+supt", "Bottom", "Stirrup", "Qty"], brows)
        cur = cur - (len(brows) + 2) * (H * 2.3) - H * 3.0
    tk = getattr(result, "takeoff", None) if result else None
    if tk:
        _draw_takeoff_table(msp, tk, x0, cur, tw_tbl, H)
        cur = cur - (9 + 2) * (H * 2.2) - H * 3.0
    tables_bottom = cur

    # ---- 设计说明（右列，与表格不重叠） ----
    nt = getattr(result, "notes", None) if result else None
    if nt:
        _draw_notes(msp, nt, x0 + tw_tbl + span * 0.04, tbl_top, H)

    # ---- 截面大样 + 墙边缘构件大样（plan 右侧） ----
    rep_beam = max(beams_r.values(), key=lambda m: m.get("As", 0)) if beams_r else None
    sec_x = x1 + off + span * 0.18
    cell = span / 7.0
    _draw_sections(msp, rows, rep_beam, sec_x, y1, cell, H)
    sec_bottom = y1 - (len(rows) + 1) * cell * 1.9 - cell
    if wrows:
        _draw_wall_edge(msp, wrows, sec_x, sec_bottom, cell, H)
        sec_bottom -= cell * 1.9

    # ---- 图名 + 图框 + 标题栏 ----
    n_floors = project.total_floors()
    sys_ = "Frame-Wall" if fl.walls else "Frame"
    _txt(msp, (x0 + x1) / 2, y1 + off + bub * 2.0,
         f"REINFORCEMENT PLAN (Std Floor)  {sys_}  {n_floors}F   unit: mm", H * 1.3, "TITLE", RGB_W)
    L = x0 - off - bub * 1.6
    R = sec_x + cell * 0.8
    T = y1 + off + bub * 3.4
    Bm = min(tables_bottom, sec_bottom) - bub * 0.6
    _frame_titleblock(msp, L, Bm, R, T, H,
                      title="结构配筋平面图（标准层）",
                      proj=f"{'框架-剪力墙' if fl.walls else '框架'}结构 {n_floors}层", dwg_no="结施-01")

    doc.saveas(dxf_path)

    cn = f"结构配筋平面图（标准层）　{'框架-剪力墙' if fl.walls else '框架'}　{n_floors}层"
    if png_path or pdf_path:
        try:
            _render(doc, msp, png_path, pdf_path, cn)
        except Exception:
            png_path = pdf_path = None
    return dxf_path, png_path, pdf_path


def export_slab_plan(project, result, dxf_path, png_path=None, pdf_path=None):
    """板配筋施工图：各板区格绘**板底钢筋**(贯通) + **支座负筋**(板面，伸入跨内≈Ln/4) + LB 表。"""
    fl = project.floor
    slabs = getattr(result, "slabs", []) if result else []
    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    for name, c in [("AXIS", C_AXIS), ("SLAB", 4), ("SBOT", 3), ("STOP", 1),
                    ("TEXT", 7), ("TABLE", 7), ("TITLE", 7)]:
        if name not in doc.layers:
            doc.layers.add(name, color=c)
    gx = sorted(project.grid.x) or sorted({round(c.x) for c in fl.columns})
    gy = sorted(project.grid.y) or sorted({round(c.y) for c in fl.columns})
    x0, x1 = (min(gx), max(gx)) if gx else (0, 0)
    y0, y1 = (min(gy), max(gy)) if gy else (0, 0)
    span = max(x1 - x0, y1 - y0, 1000)
    H = span / 80.0
    bub = span / 26.0
    off = bub * 2.2
    _axis_grid(msp, gx, gy, x0, x1, y0, y1, off, bub)

    for sd in slabs:
        xa = min(sd["x1"], sd["x2"]); ya = min(sd["y1"], sd["y2"])
        ws = abs(sd["x2"] - sd["x1"]); hs = abs(sd["y2"] - sd["y1"])
        msp.add_lwpolyline([(xa, ya), (xa + ws, ya), (xa + ws, ya + hs), (xa, ya + hs)],
                           close=True, dxfattribs={"layer": "SLAB"})
        # 板底钢筋：X 向(水平线)、Y 向(竖直线) 各画 2 根代表线
        for fy in (0.35, 0.65):
            msp.add_line((xa + ws * 0.06, ya + hs * fy), (xa + ws * 0.94, ya + hs * fy),
                         dxfattribs={"layer": "SBOT"})
        for fx in (0.35, 0.65):
            msp.add_line((xa + ws * fx, ya + hs * 0.06), (xa + ws * fx, ya + hs * 0.94),
                         dxfattribs={"layer": "SBOT"})
        _txt(msp, xa + ws / 2, ya + hs / 2 + H * 1.0, f"{sd['name']} h={sd['t']}", H, "SLAB", RGB_W)
        # 平法 B(板底贯通)
        _txt(msp, xa + ws / 2, ya + hs / 2 - H * 0.2,
             f"B:X{sd['bars_x']} Y{sd['bars_y']}", H * 0.72, "SBOT", (150, 240, 160))
        # 平法 T(支座板面负筋)
        _txt(msp, xa + ws / 2, ya + hs / 2 - H * 1.3,
             f"T:{sd.get('bars_x_top', sd['bars_x'])}", H * 0.72, "STOP", (255, 175, 95))
        # 支座负筋(板面)：四边各画一条伸入跨内 L/4 的线 + 端部下弯钩 + 标注
        qx, qy = ws * 0.25, hs * 0.25
        bxt = sd.get("bars_x_top", sd["bars_x"]); byt = sd.get("bars_y_top", sd["bars_y"])
        edges = [((xa, ya + hs * 0.5), (xa + qx, ya + hs * 0.5), byt),          # 左(Y向负筋?) 用 byt
                 ((xa + ws, ya + hs * 0.5), (xa + ws - qx, ya + hs * 0.5), byt),  # 右
                 ((xa + ws * 0.5, ya), (xa + ws * 0.5, ya + qy), bxt),            # 下
                 ((xa + ws * 0.5, ya + hs), (xa + ws * 0.5, ya + hs - qy), bxt)]  # 上
        for (p0, p1, bar) in edges:
            msp.add_line(p0, p1, dxfattribs={"layer": "STOP"})
            _txt(msp, (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + H * 0.5, bar, H * 0.6, "STOP", (255, 170, 90))

    # LB 板表
    if slabs:
        seen, srows = set(), []
        for sd in slabs:
            if sd["name"] not in seen:
                seen.add(sd["name"])
                srows.append((sd["name"], f"{int(sd['Lx']*1000)}x{int(sd['Ly']*1000)}", sd["t"],
                              sd["kind"], sd["bars_x"], sd["bars_y"],
                              sd.get("bars_x_top", "-"), sd["qty"]))
        scw = [span * f for f in (0.09, 0.16, 0.07, 0.11, 0.15, 0.15, 0.17, 0.10)]
        _table(msp, x0, y0 - off - bub * 3.2, scw, H, "SLAB SCHEDULE / 板表 (btm + top)",
               ["Mark", "LxxLy", "h", "Type", "X-btm", "Y-btm", "Top", "Qty"], srows)

    _txt(msp, (x0 + x1) / 2, y1 + off + bub * 2.2,
         "SLAB REINFORCEMENT PLAN  (B: bottom=green, T: support/top=orange)  unit: mm", H * 1.3, "TITLE", RGB_W)
    # 图框 + 标题栏
    tb_top = (y0 - off - bub * 3.2)
    _frame_titleblock(msp, x0 - off - bub * 1.6, min(tb_top - bub * 8, y0 - off - bub * 9),
                      x1 + off + bub * 1.6, y1 + off + bub * 3.4, H,
                      title="结构楼板配筋施工图", proj="标准层楼板", dwg_no="结施-02")
    doc.saveas(dxf_path)
    if png_path or pdf_path:
        try:
            _render(doc, msp, png_path, pdf_path, "结构楼板配筋施工图（标准层）")
        except Exception:
            png_path = pdf_path = None
    return dxf_path, png_path, pdf_path


def _draw_beams(msp, fl, beams_r, H):
    # 归并：水平梁按 y、竖直梁按 x 成连续梁
    runs = {}
    for bi, b in enumerate(fl.beams):
        if abs(b.y1 - b.y2) < 1:
            key = ("H", round(b.y1))
        elif abs(b.x1 - b.x2) < 1:
            key = ("V", round(b.x1))
        else:
            key = ("D", bi)
        runs.setdefault(key, []).append((bi, b))
    kl = 0
    for key, segs in sorted(runs.items()):
        kl += 1
        if key[0] == "H":
            segs.sort(key=lambda t: min(t[1].x1, t[1].x2))
        elif key[0] == "V":
            segs.sort(key=lambda t: min(t[1].y1, t[1].y2))
        # 集中标注（连续梁一次，平法）：KLn(跨数) b×h / 箍筋 / 上部通长筋 [/ G腰筋]
        bi0, b0 = segs[0]
        m0 = beams_r.get(str(bi0)) or {}
        sec = f"{int(b0.b)}x{int(b0.h)}"
        stir = m0.get("stirrup", "A8@100/200(2)")
        thru = m0.get("thru", "2D20")
        waist = m0.get("waist", "")
        px, py = _perp(b0)
        cx, cy = (b0.x1 + b0.x2) / 2, (b0.y1 + b0.y2) / 2
        line1 = f"KL{kl}({len(segs)}) {sec} {stir} {thru}"
        _txt(msp, cx + px * H * 3.2, cy + py * H * 3.2, line1, H * 0.9, "BEAM", RGB_G)
        if waist:                      # 腰筋另起一行(平法 G/N 行)
            _txt(msp, cx + px * H * 4.6, cy + py * H * 4.6, waist, H * 0.8, "BEAM", (150, 220, 170))
        # 逐跨：跨中下部筋 + 支座上部负筋
        for bi, b in segs:
            msp.add_line((b.x1, b.y1), (b.x2, b.y2), dxfattribs={"layer": "BEAM"})
            m = beams_r.get(str(bi))
            if not m:
                continue
            px, py = _perp(b)
            mx, my = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
            # 下部跨中（perp 负侧）
            _txt(msp, mx - px * H * 1.3, my - py * H * 1.3, m.get("bars_bot", m["bars"]),
                 H * 0.8, "BEAM", RGB_W)
            # 支座负筋（两端，perp 正侧）
            for f in (0.18, 0.82):
                sx, sy = b.x1 + (b.x2 - b.x1) * f, b.y1 + (b.y2 - b.y1) * f
                _txt(msp, sx + px * H * 1.3, sy + py * H * 1.3, m.get("bars_top", m["bars"]),
                     H * 0.75, "BEAM", RGB_Y)


def _parse_sec(sec):
    try:
        a, b = _san(sec).lower().split("x")
        return int(float(a)), int(float(b))
    except Exception:
        return 500, 500


def _ring_bars(msp, cx, cy, bw, hh, n_side, r):
    xs = [cx - bw / 2 + bw * i / max(n_side - 1, 1) for i in range(n_side)]
    ys = [cy - hh / 2 + hh * i / max(n_side - 1, 1) for i in range(n_side)]
    pts = set()
    for x in xs:
        pts.add((round(x, 1), round(cy - hh / 2, 1))); pts.add((round(x, 1), round(cy + hh / 2, 1)))
    for y in ys:
        pts.add((round(cx - bw / 2, 1), round(y, 1))); pts.add((round(cx + bw / 2, 1), round(y, 1)))
    for (x, y) in pts:
        c = msp.add_circle((x, y), r, dxfattribs={"layer": "COLUMN"})
        c.dxf.true_color = ezdxf.rgb2int(RGB_Y)


def _section_box(msp, ax, ay, b, h, cell, label, sub, kind="col", top="", bot=""):
    sc = cell / max(b, h)
    bw, hh = b * sc, h * sc
    cv = 25 * sc
    msp.add_lwpolyline([(ax - bw / 2, ay - hh / 2), (ax + bw / 2, ay - hh / 2),
                        (ax + bw / 2, ay + hh / 2), (ax - bw / 2, ay + hh / 2)],
                       close=True, dxfattribs={"layer": "COLUMN"})
    msp.add_lwpolyline([(ax - bw / 2 + cv, ay - hh / 2 + cv), (ax + bw / 2 - cv, ay - hh / 2 + cv),
                        (ax + bw / 2 - cv, ay + hh / 2 - cv), (ax - bw / 2 + cv, ay + hh / 2 - cv)],
                       close=True, dxfattribs={"layer": "BEAM"})
    r = max(cell / 40.0, 8)
    if kind == "col":
        n_side = 3 if b >= 600 else 2
        _ring_bars(msp, ax, ay, bw - 2 * cv, hh - 2 * cv, n_side, r)
    else:
        for nx, yy in ((3, ay + hh / 2 - cv * 1.6), (2, ay - hh / 2 + cv * 1.6)):
            xs = [ax - bw / 2 + cv + (bw - 2 * cv) * i / max(nx - 1, 1) for i in range(nx)]
            for x in xs:
                c = msp.add_circle((x, yy), r, dxfattribs={"layer": "COLUMN"})
                c.dxf.true_color = ezdxf.rgb2int(RGB_Y)
    Ht = cell / 9.0
    _txt(msp, ax, ay - hh / 2 - Ht * 1.6, label, Ht * 1.2, "TEXT", RGB_W)
    _txt(msp, ax, ay - hh / 2 - Ht * 3.2, sub, Ht * 0.95, "TEXT", RGB_G)


def _frame_titleblock(msp, L, B, R, T, H, title="结构施工图", proj="", dwg_no="结施-01"):
    """图框(粗边框) + 右下角标题栏(图名/工程/比例/日期/图号)。"""
    lw = max((R - L) * 0.0012, 6.0)
    msp.add_lwpolyline([(L, B), (R, B), (R, T), (L, T)], close=True,
                       dxfattribs={"layer": "FRAME", "const_width": lw})
    # 内边线(细)
    pad = (T - B) * 0.012
    msp.add_lwpolyline([(L + pad, B + pad), (R - pad, B + pad), (R - pad, T - pad), (L + pad, T - pad)],
                       close=True, dxfattribs={"layer": "FRAME"})
    # 标题栏(右下)
    tw = min((R - L) * 0.34, (R - L) - 2 * pad)
    rh = H * 2.6
    nrow = 5
    tx0, ty0 = R - pad - tw, B + pad
    for r in range(nrow + 1):
        msp.add_line((tx0, ty0 + r * rh), (R - pad, ty0 + r * rh), dxfattribs={"layer": "FRAME"})
    msp.add_line((tx0, ty0), (tx0, ty0 + nrow * rh), dxfattribs={"layer": "FRAME"})
    msp.add_line((tx0 + tw * 0.34, ty0), (tx0 + tw * 0.34, ty0 + nrow * rh), dxfattribs={"layer": "FRAME"})
    rowsTB = [("图号", dwg_no), ("日期", "—"), ("比例", "NTS"), ("图名", title), ("工程", proj)]
    for i, (k, v) in enumerate(rowsTB):
        yy = ty0 + (i + 0.5) * rh
        _txt(msp, tx0 + tw * 0.17, yy, k, H * 0.85, "FRAME", RGB_W)
        _txt(msp, tx0 + tw * 0.34 + (tw * 0.66) / 2, yy, v, H * 0.9, "FRAME", RGB_Y)


def _draw_wall_edge(msp, wrows, ax, ay, cell, H):
    """墙边缘构件(GBZ/YBZ)大样：取代表墙肢，画约束边缘构件截面 + 纵筋 + 箍筋示意。"""
    if not wrows:
        return
    name, sec, vd, hd, edge, mu, qty = wrows[0]
    bw, lw = _parse_sec(sec)
    lc = max(bw, 400)                      # 边缘构件长度(示意)
    _txt(msp, ax, ay + cell * 0.75, "EDGE MEMBER / 边缘构件(GBZ)", cell / 8.0, "TEXT", RGB_W)
    _section_box(msp, ax, ay, lc, bw, cell, f"GBZ ({name})", f"{edge}  A8@100", kind="col")


def _draw_sections(msp, rows, rep_beam, ax, ay_top, cell, H):
    _txt(msp, ax, ay_top + cell * 0.9, "SECTION DETAILS / 截面大样", cell / 7.0, "TEXT", RGB_W)
    step = cell * 1.9
    y = ay_top
    for (name, sec, bars, stir, mu, qty) in rows:
        b, h = _parse_sec(sec)
        _section_box(msp, ax, y, b, h, cell, f"{name} {sec}", f"{bars}  {stir}", kind="col")
        y -= step
    if rep_beam:
        b, h = _parse_sec(rep_beam["sec"])
        _section_box(msp, ax, y, b, h, cell, f"KL {rep_beam['sec']}",
                     f"T:{rep_beam.get('bars_top','')} B:{rep_beam.get('bars_bot','')} {rep_beam.get('stirrup','')}",
                     kind="beam")


def _draw_takeoff_table(msp, tk, x0, top, span, H):
    rows = [
        ("Concrete C40 Column", f"{tk['conc_col']:.1f} m3"),
        ("Concrete C40 Wall", f"{tk['conc_wall']:.1f} m3"),
        ("Concrete C30 Beam", f"{tk['conc_beam']:.1f} m3"),
        ("Concrete TOTAL", f"{tk['conc_total']:.1f} m3"),
        ("Steel longitudinal", f"{tk['steel_long_t']:.2f} t"),
        ("Steel stirrup (est.)", f"{tk['steel_stirrup_t']:.2f} t"),
        ("Steel TOTAL", f"{tk['steel_total_t']:.2f} t"),
        ("Steel intensity", f"{tk['steel_kg_m2']:.1f} kg/m2"),
        ("Concrete intensity", f"{tk['conc_m3_per_m2']:.3f} m3/m2"),
    ]
    cw = [span * 0.32, span * 0.22]
    total_w = sum(cw); rh = H * 2.2; n = len(rows) + 1
    for r in range(n + 1):
        yy = top - r * rh
        msp.add_line((x0, yy), (x0 + total_w, yy), dxfattribs={"layer": "TABLE"})
    xx = x0
    for w in cw + [0]:
        msp.add_line((xx, top), (xx, top - n * rh), dxfattribs={"layer": "TABLE"}); xx += w
    _txt(msp, x0 + total_w / 2, top + rh * 0.6, "MATERIAL TAKE-OFF / 材料统计", H * 1.1, "TABLE", RGB_W)
    _txt(msp, x0 + cw[0] / 2, top - 0.5 * rh, "Item", H * 0.85, "TABLE", RGB_Y)
    _txt(msp, x0 + cw[0] + cw[1] / 2, top - 0.5 * rh, "Quantity", H * 0.85, "TABLE", RGB_Y)
    for i, (a, b) in enumerate(rows):
        yy = top - (i + 1.5) * rh
        _txt(msp, x0 + cw[0] / 2, yy, a, H * 0.8, "TABLE", RGB_W)
        _txt(msp, x0 + cw[0] + cw[1] / 2, yy, b, H * 0.8, "TABLE", RGB_W)


def _draw_notes(msp, nt, x, top, H):
    _txt(msp, x, top + H * 1.4, "DESIGN NOTES / 设计说明", H * 1.1, "TEXT", RGB_W, align="MIDDLE_LEFT")
    lines = [
        f"1. Seismic grade 抗震等级: {nt.get('grade','-')}",
        f"2. Concrete 混凝土: Col/Wall {nt.get('conc_col','C40')}, Beam {nt.get('conc_beam','C30')}; "
        f"Rebar {nt.get('rebar','HRB400')}/HPB300",
        f"3. Cover 保护层(mm): beam {nt.get('cover_beam',25)}, col {nt.get('cover_col',30)}, wall {nt.get('cover_wall',15)}",
        f"4. Stirrup dense zone 箍筋加密区(mm): beam end {nt.get('beam_dense',500)}; "
        f"col end {nt.get('col_dense',500)}, col bottom {nt.get('col_dense_bottom',500)}",
        f"5. Clear col height 柱净高 Hn={nt.get('Hn',0)} mm",
        "6. Schematic design-level drawing; verify per code & licensed engineer.",
    ]
    for i, ln in enumerate(lines):
        _txt(msp, x, top - i * H * 1.8, ln, H * 0.8, "TEXT", RGB_G, align="MIDDLE_LEFT")


def _draw_col_table(msp, rows, x0, top, span, H):
    headers = ["Mark", "b x h", "Longit. Bars", "Stirrup", "AxialRatio", "Qty"]
    cw = [span * f for f in (0.10, 0.16, 0.26, 0.20, 0.16, 0.12)]
    rh = H * 2.4
    total_w = sum(cw)
    n = len(rows) + 1
    # 外框 + 行线
    for r in range(n + 1):
        yy = top - r * rh
        msp.add_line((x0, yy), (x0 + total_w, yy), dxfattribs={"layer": "TABLE"})
    xx = x0
    for w in cw + [0]:
        msp.add_line((xx, top), (xx, top - n * rh), dxfattribs={"layer": "TABLE"})
        xx += w
    _txt(msp, x0 + total_w / 2, top + rh * 0.6, "COLUMN SCHEDULE / 柱表", H * 1.1, "TABLE", RGB_W)

    def cell_row(r, vals, rgb):
        yy = top - (r + 0.5) * rh
        xx = x0
        for v, w in zip(vals, cw):
            _txt(msp, xx + w / 2, yy, v, H * 0.85, "TABLE", rgb)
            xx += w
    cell_row(0, headers, RGB_Y)
    for i, row in enumerate(rows):
        cell_row(i + 1, [str(v) for v in row], RGB_W)


def _axis_grid(msp, gx, gy, x0, x1, y0, y1, off, bub):
    for i, x in enumerate(gx):
        msp.add_line((x, y0 - off), (x, y1 + off), dxfattribs={"layer": "AXIS"})
        for yy in (y0 - off, y1 + off):
            msp.add_circle((x, yy), bub, dxfattribs={"layer": "AXIS"})
            _txt(msp, x, yy, str(i + 1), bub, "AXIS", (255, 120, 120))
    for k, y in enumerate(gy):
        msp.add_line((x0 - off, y), (x1 + off, y), dxfattribs={"layer": "AXIS"})
        for xx in (x0 - off, x1 + off):
            msp.add_circle((xx, y), bub, dxfattribs={"layer": "AXIS"})
            _txt(msp, xx, y, chr(ord("A") + k), bub, "AXIS", (255, 120, 120))


def _table(msp, x0, top, col_w, H, title, header, rows, hdr_rgb=RGB_Y):
    rh = H * 2.3
    total_w = sum(col_w)
    n = len(rows) + 1
    for r in range(n + 1):
        yy = top - r * rh
        msp.add_line((x0, yy), (x0 + total_w, yy), dxfattribs={"layer": "TABLE"})
    xx = x0
    for w in col_w + [0]:
        msp.add_line((xx, top), (xx, top - n * rh), dxfattribs={"layer": "TABLE"}); xx += w
    _txt(msp, x0 + total_w / 2, top + rh * 0.6, title, H * 1.1, "TABLE", RGB_W)

    def row_cells(r, vals, rgb):
        yy = top - (r + 0.5) * rh; xx = x0
        for v, w in zip(vals, col_w):
            _txt(msp, xx + w / 2, yy, str(v), H * 0.82, "TABLE", rgb); xx += w
    row_cells(0, header, hdr_rgb)
    for i, row in enumerate(rows):
        row_cells(i + 1, row, RGB_W)


def export_foundation(project, result, dxf_path, png_path=None, pdf_path=None, fak=200.0):
    from ..run.foundation import design_footings, design_strip_footings, recommend_foundation
    footings, rows = design_footings(project, result, fak)
    strips, srows = design_strip_footings(project, result, fak) if project.floor.walls else ([], [])
    rec = recommend_foundation(project, result, fak)

    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    for name, c in [("AXIS", C_AXIS), ("FOUND", 4), ("STRIP", 3), ("COLUMN", C_COL),
                    ("TABLE", 7), ("TEXT", 7), ("TITLE", 7)]:
        if name not in doc.layers:
            doc.layers.add(name, color=c)
    gx = sorted(project.grid.x) or sorted({round(c.x) for c in project.floor.columns})
    gy = sorted(project.grid.y) or sorted({round(c.y) for c in project.floor.columns})
    x0, x1 = (min(gx), max(gx)) if gx else (0, 0)
    y0, y1 = (min(gy), max(gy)) if gy else (0, 0)
    span = max(x1 - x0, y1 - y0, 1000)
    H = span / 80.0; bub = span / 26.0; off = bub * 2.2
    _axis_grid(msp, gx, gy, x0, x1, y0, y1, off, bub)

    for c in project.floor.columns:
        k = (str(round(c.x)), str(round(c.y)))
        f = footings.get(k)
        if not f:
            continue
        Bm = f["B"] * 1000.0
        msp.add_lwpolyline([(c.x - Bm / 2, c.y - Bm / 2), (c.x + Bm / 2, c.y - Bm / 2),
                            (c.x + Bm / 2, c.y + Bm / 2), (c.x - Bm / 2, c.y + Bm / 2)],
                           close=True, dxfattribs={"layer": "FOUND"})
        msp.add_lwpolyline([(c.x - c.b / 2, c.y - c.h / 2), (c.x + c.b / 2, c.y - c.h / 2),
                            (c.x + c.b / 2, c.y + c.h / 2), (c.x - c.b / 2, c.y + c.h / 2)],
                           close=True, dxfattribs={"layer": "COLUMN"})
        _txt(msp, c.x, c.y - Bm / 2 - H * 1.1, f["name"], H * 0.95, "FOUND", RGB_Y)

    # 墙下条形基础（沿墙线画底宽 B 的带状）
    for s in strips:
        L = ((s["x2"] - s["x1"]) ** 2 + (s["y2"] - s["y1"]) ** 2) ** 0.5 or 1.0
        ux, uy = (s["x2"] - s["x1"]) / L, (s["y2"] - s["y1"]) / L
        px, py = -uy, ux                    # 法向
        hw = s["B"] * 1000.0 / 2.0
        poly = [(s["x1"] + px * hw, s["y1"] + py * hw), (s["x2"] + px * hw, s["y2"] + py * hw),
                (s["x2"] - px * hw, s["y2"] - py * hw), (s["x1"] - px * hw, s["y1"] - py * hw)]
        msp.add_lwpolyline(poly, close=True, dxfattribs={"layer": "STRIP"})
        _txt(msp, (s["x1"] + s["x2"]) / 2, (s["y1"] + s["y2"]) / 2, s["name"], H * 0.9, "STRIP", RGB_G)

    # 基础表
    cw = [span * f for f in (0.10, 0.18, 0.10, 0.18, 0.14, 0.10)]
    cur = y0 - off - bub * 3.2
    _table(msp, x0, cur, cw, H, "FOOTING SCHEDULE / 独立基础表",
           ["Mark", "BxB(mm)", "h(mm)", "Rebar", "Nk(kN)", "Qty"], rows)
    cur = cur - (len(rows) + 2) * (H * 2.3) - H * 3.0
    # 条基表
    if srows:
        scw = [span * f for f in (0.10, 0.14, 0.12, 0.20, 0.18, 0.10)]
        _table(msp, x0, cur, scw, H, "STRIP FOOTING / 条形基础表 (TJ)",
               ["Mark", "B(mm)", "h(mm)", "Rebar", "q(kN/m)", "Qty"], srows)
        cur = cur - (len(srows) + 2) * (H * 2.3) - H * 3.0

    # 典型基础剖面大样（右侧）
    if rows:
        _footing_section(msp, rows[0], x1 + off + span * 0.18, y1, span / 6.0, H, fak)

    n_floors = project.total_floors()
    _txt(msp, (x0 + x1) / 2, y1 + off + bub * 2.2,
         f"FOUNDATION PLAN  fak={fak:.0f} kPa   unit: mm", H * 1.3, "TITLE", RGB_W)
    _txt(msp, x0, y1 + off + bub * 0.8,
         f"基础选型建议：{rec['kind']}（{rec['reason']}）", H * 0.9, "TEXT", RGB_G, align="MIDDLE_LEFT")
    if "FRAME" not in doc.layers:
        doc.layers.add("FRAME", color=7)
    _frame_titleblock(msp, x0 - off - bub * 1.6, cur - bub * 2, x1 + off + span * 0.40,
                      y1 + off + bub * 3.4, H, title="基础平面布置图",
                      proj=f"fak={fak:.0f}kPa {rec['kind']}", dwg_no="结施-03")
    doc.saveas(dxf_path)
    cn = f"基础平面布置图（柱下独立基础）　fak={fak:.0f} kPa"
    if png_path or pdf_path:
        try:
            _render(doc, msp, png_path, pdf_path, cn)
        except Exception:
            png_path = pdf_path = None
    return dxf_path, png_path, pdf_path


def _footing_section(msp, row, ax, ay, cell, H, fak):
    name, bxb, hh, bars, nk, qty = row
    B = float(bxb.split("x")[0]); h = float(hh)
    sc = cell / B
    bw = B * sc; hht = h * sc
    msp.add_lwpolyline([(ax - bw / 2, ay - hht), (ax + bw / 2, ay - hht),
                        (ax + bw / 2, ay), (ax - bw / 2, ay)],
                       close=True, dxfattribs={"layer": "FOUND"})
    cstub = 0.5 * cell
    msp.add_lwpolyline([(ax - cstub / 4, ay), (ax + cstub / 4, ay),
                        (ax + cstub / 4, ay + cstub), (ax - cstub / 4, ay + cstub)],
                       close=True, dxfattribs={"layer": "COLUMN"})
    # 底板钢筋（底部一排点）
    r = max(cell / 45.0, 6)
    yb = ay - hht + r * 2
    nx = 6
    for i in range(nx):
        x = ax - bw / 2 + bw * (i + 0.5) / nx
        cc = msp.add_circle((x, yb), r, dxfattribs={"layer": "COLUMN"}); cc.dxf.true_color = ezdxf.rgb2int(RGB_Y)
    _txt(msp, ax, ay - hht - H * 1.6, f"{name}  {bxb}x{hh}", H * 1.1, "TEXT", RGB_W)
    _txt(msp, ax, ay - hht - H * 3.2, f"Btm {bars}", H * 0.9, "TEXT", RGB_G)


def export_stair(stair, dxf_path, png_path=None, pdf_path=None):
    """stair: stairs.design_stair() 结果。出剖面 + 平面 + 说明。"""
    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    for name, c in [("STAIR", 3), ("REBAR", 2), ("DIM", 1), ("TEXT", 7), ("TITLE", 7)]:
        if name not in doc.layers:
            doc.layers.add(name, color=c)
    H = stair["floor_h"]
    g = stair["going"]; r = stair["riser"]; spf = stair["spf"]; t = stair["t"]
    land = max(stair["width"], 1300)
    Ht = H / 22.0

    # ---- 剖面 ----
    pts = [(0.0, 0.0)]
    x = 0.0; y = 0.0
    for _ in range(spf):                      # 第一跑踏步
        x += g; pts.append((x, y))
        y += r; pts.append((x, y))
    x_l1 = x
    x += land; pts.append((x, y))             # 休息平台
    for _ in range(spf):                      # 第二跑踏步
        x += g; pts.append((x, y))
        y += r; pts.append((x, y))
    msp.add_lwpolyline(pts, dxfattribs={"layer": "STAIR"})
    run = x
    # 梯板底(斜板)：两跑斜线下移 t（竖向近似）+ 平台板
    def soffit(x1, y1, x2, y2):
        msp.add_line((x1, y1 - t * 1.4), (x2, y2 - t * 1.4), dxfattribs={"layer": "STAIR"})
    soffit(0, 0, x_l1, spf * r)
    msp.add_line((x_l1, spf * r - t * 1.4), (x_l1 + land, spf * r - t * 1.4), dxfattribs={"layer": "STAIR"})
    soffit(x_l1 + land, spf * r, run, H)
    # 配筋(板底通长，黄)
    msp.add_line((0, -t * 0.7), (x_l1, spf * r - t * 0.7), dxfattribs={"layer": "REBAR"})
    msp.add_line((x_l1 + land, spf * r - t * 0.7), (run, H - t * 0.7), dxfattribs={"layer": "REBAR"})
    # 楼层标高线
    for yy, tag in [(0, "+0.000"), (spf * r, f"+{spf*r/1000:.3f}"), (H, f"+{H/1000:.3f}")]:
        msp.add_line((-land * 0.4, yy), (run + land * 0.2, yy), dxfattribs={"layer": "DIM"})
        _txt(msp, -land * 0.55, yy, tag, Ht * 0.9, "DIM", RGB_W, align="MIDDLE_RIGHT")
    _txt(msp, run / 2, -t * 3.5, "SECTION 1-1 / 楼梯剖面", Ht * 1.2, "TEXT", RGB_W)

    # ---- 平面(剖面下方) ----
    py = -H * 0.9
    fw = stair["width"]
    run1 = spf * g
    # 两跑梯段 + 中间梯井 + 休息平台
    gap = 200
    msp.add_lwpolyline([(0, py), (run1, py), (run1, py + fw), (0, py + fw)], close=True, dxfattribs={"layer": "STAIR"})
    msp.add_lwpolyline([(0, py + fw + gap), (run1, py + fw + gap), (run1, py + 2 * fw + gap),
                        (0, py + 2 * fw + gap)], close=True, dxfattribs={"layer": "STAIR"})
    # 踏步线
    for i in range(1, spf):
        xx = i * g
        msp.add_line((xx, py), (xx, py + fw), dxfattribs={"layer": "STAIR"})
        msp.add_line((xx, py + fw + gap), (xx, py + 2 * fw + gap), dxfattribs={"layer": "STAIR"})
    # 休息平台
    msp.add_lwpolyline([(run1, py), (run1 + land, py), (run1 + land, py + 2 * fw + gap),
                        (run1, py + 2 * fw + gap)], close=True, dxfattribs={"layer": "STAIR"})
    _txt(msp, run1 / 2, py - Ht * 1.6, "PLAN / 楼梯平面", Ht * 1.2, "TEXT", RGB_W)
    msp.add_text("UP", dxfattribs={"layer": "TEXT", "height": Ht}).set_placement(
        (run1 / 2, py + fw / 2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    # ---- 说明 ----
    notes = [
        f"TB1  slab t={t}mm   板式楼梯(双跑)",
        f"Steps 踏步: {stair['n']} x ({g} x {r}) mm   (per flight {spf})",
        f"Floor height 层高: {H} mm",
        f"Slab rebar 梯板受力筋: {stair['bars']} (btm, both flights)",
        "Distribution 分布筋: C8@200",
    ]
    nx = run + land * 0.5
    _txt(msp, nx, H, "STAIR NOTES / 楼梯说明", Ht * 1.1, "TEXT", RGB_W, align="MIDDLE_LEFT")
    for i, ln in enumerate(notes):
        _txt(msp, nx, H - (i + 1) * Ht * 1.7, ln, Ht * 0.85, "TEXT", RGB_G, align="MIDDLE_LEFT")

    _txt(msp, run / 2, H + Ht * 2.2, "STAIR DETAIL  AT-type slab stair   unit: mm", Ht * 1.2, "TITLE", RGB_W)
    doc.saveas(dxf_path)
    if png_path or pdf_path:
        try:
            _render(doc, msp, png_path, pdf_path, "楼梯详图（板式·双跑）")
        except Exception:
            png_path = pdf_path = None
    return dxf_path, png_path, pdf_path


def _render(doc, msp, png_path, pdf_path, cn_title=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    fig = plt.figure(figsize=(11.5, 13), facecolor="black")
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.93]); ax.set_axis_off(); ax.set_facecolor("black")
    try:
        from ezdxf.addons.drawing import config as _cfg
        conf = _cfg.Configuration(background_policy=_cfg.BackgroundPolicy.BLACK)
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=conf).draw_layout(msp, finalize=True)
    except Exception:
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    if cn_title:
        fig.suptitle(cn_title, fontsize=13, y=0.99, color="white")
    if png_path:
        fig.savefig(png_path, dpi=150, facecolor="black")
    if pdf_path:
        fig.savefig(pdf_path, facecolor="black")
    plt.close(fig)
