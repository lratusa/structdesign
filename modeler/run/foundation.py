"""独立基础(柱下扩展基础)设计：按柱底轴力 + 地基承载力定底面尺寸，按冲切/受弯定高与配筋。

简化方法（方案/初步设计）：
- 底面积 A = 1.05·Nk / fak（1.05 计基础及覆土自重）；方形 B 取 100mm 模数。
- 基础高 h 由(B-柱)/2 悬挑与最小值控制（近似），50mm 模数。
- 底板配筋：净反力悬挑弯矩 → 每米 As，@ 间距。
- 按 (B,h) 归并 JC1.. 。Nk≈柱底设计轴力/1.35（近似特征组合）。
"""
from __future__ import annotations
import math


def _round_up(v, step):
    return math.ceil(v / step) * step


def _base_axial(result):
    """各柱平面位置的柱底(最大)轴力 N(kN)。返回 {(kx,ky): N}。
    注意：键 = 构件 id 解析出的 round(x),round(y)，依赖 to_frame3d 的 TOL=1.0；
    若改 TOL 需同步此处与各 design_* 的 col_xy 键，否则 .get(k,0) 会静默给 0 轴力。"""
    out = {}
    for m in result.members:
        if m["kind"] != "柱":
            continue
        body = m["id"][1:].split("_")
        k = (body[0], body[1])
        out[k] = max(out.get(k, 0.0), m.get("N", 0.0))
    return out


def _bars_at(As_per_m, bw=1000):
    """每米 As → 选直径@间距字符串(简化)。"""
    for d in (12, 14, 16, 18, 20):
        a = math.pi * d * d / 4.0
        s = a / max(As_per_m, 1e-6) * 1000.0       # mm
        s = int(min(s, 200) // 10 * 10)
        if s >= 100:
            return f"C{d}@{s}"
    return "C20@100"


def design_footings(project, result, fak=200.0):
    """返回 (footings, groups)：
    footings: {(kx,ky): {name,B,h,bars,Nk,x,y}}；groups: [(name,B,h,bars,Nk_max,qty)]。
    """
    fak = float(fak or 200.0)
    Nmap = _base_axial(result)
    # 列出柱平面坐标
    col_xy = {(str(round(c.x)), str(round(c.y))): (c.x, c.y, max(c.b, c.h))
              for c in project.floor.columns}
    raw = {}
    for k, (x, y, csz) in col_xy.items():
        Nd = Nmap.get(k, 0.0)
        Nk = Nd / 1.35                              # 近似特征轴力 kN
        A = 1.05 * Nk / fak                         # m²
        B = max(_round_up(math.sqrt(max(A, 0.5)), 0.1), 1.2)   # m, ≥1.2
        col_m = csz / 1000.0
        a = (B - col_m) / 2.0                       # 悬挑 m
        h = max(0.40, _round_up(a * 0.5, 0.05))     # m（近似冲切/抗弯控高）
        h = min(h, 1.2)
        p_net = Nk / (B * B)                        # kPa 净反力
        M = p_net * a * a / 2.0                     # kN·m/m 悬挑弯矩
        h0 = h * 1000.0 - 50.0                      # mm
        As_per_m = M * 1e6 / (0.9 * h0 * 360.0)     # mm²/m
        As_per_m = max(As_per_m, 0.0015 * h * 1000.0 * 1000.0)  # 最小配筋率 0.15%
        bars = _bars_at(As_per_m)
        raw[k] = dict(B=round(B, 1), h=round(h, 2), bars=bars, Nk=round(Nk), x=x, y=y)

    # 归并 (B,h,bars) → JC#
    groups, order = {}, []
    for k, f in raw.items():
        gk = (f["B"], f["h"], f["bars"])
        if gk not in groups:
            groups[gk] = dict(name="", B=f["B"], h=f["h"], bars=f["bars"], Nk=f["Nk"], qty=0)
            order.append(gk)
        groups[gk]["qty"] += 1
        groups[gk]["Nk"] = max(groups[gk]["Nk"], f["Nk"])
    for i, gk in enumerate(order):
        groups[gk]["name"] = f"JC{i+1}"
    footings = {}
    for k, f in raw.items():
        gk = (f["B"], f["h"], f["bars"])
        footings[k] = dict(name=groups[gk]["name"], **f)
    rows = [(groups[gk]["name"], f"{groups[gk]['B']*1000:.0f}x{groups[gk]['B']*1000:.0f}",
             f"{groups[gk]['h']*1000:.0f}", groups[gk]["bars"],
             f"{groups[gk]['Nk']:.0f}", groups[gk]["qty"]) for gk in order]
    return footings, rows


def _wall_axial(result):
    """各墙(中点)轴力 N(kN)：{(kx,ky): N}。"""
    out = {}
    for m in result.members:
        if m["kind"] != "墙":
            continue
        body = m["id"][1:].split("_")
        k = (body[0], body[1])
        out[k] = max(out.get(k, 0.0), m.get("N", 0.0))
    return out


def design_strip_footings(project, result, fak=200.0):
    """墙下/柱列下**条形基础**(墙肢用)：按线荷载定底宽，悬挑定高与横向底筋。
    返回 (strips, rows)。strips: [{name,x1,y1,x2,y2,bw,B,h,bars,Nk_per_m}]。"""
    fak = float(fak or 200.0)
    Wmap = _wall_axial(result)
    raw = []
    for w in project.floor.walls:
        mx, my = (w.x1 + w.x2) / 2.0, (w.y1 + w.y2) / 2.0
        k = (str(round(mx)), str(round(my)))
        L = ((w.x2 - w.x1) ** 2 + (w.y2 - w.y1) ** 2) ** 0.5 / 1000.0   # m
        if L < 0.1:
            continue
        Nd = Wmap.get(k, 0.0)
        Nk_per_m = (Nd / 1.35) / L                                      # kN/m
        B = max(_round_up(1.05 * Nk_per_m / fak, 0.1), w.t / 1000.0 + 0.4, 0.8)   # m
        a = (B - w.t / 1000.0) / 2.0                                    # 悬挑 m
        h = min(max(0.30, _round_up(a * 0.5, 0.05)), 1.0)
        p_net = Nk_per_m / B                                            # kPa
        M = p_net * a * a / 2.0                                         # kN·m/m
        h0 = h * 1000.0 - 45.0
        As_per_m = max(M * 1e6 / (0.9 * h0 * 360.0), 0.0015 * h * 1e6)
        raw.append(dict(x1=w.x1, y1=w.y1, x2=w.x2, y2=w.y2, bw=w.t,
                        B=round(B, 1), h=round(h, 2), bars=_bars_at(As_per_m),
                        Nk_per_m=round(Nk_per_m)))
    groups, order = {}, []
    for f in raw:
        gk = (f["B"], f["h"], f["bars"])
        if gk not in groups:
            groups[gk] = dict(name="", B=f["B"], h=f["h"], bars=f["bars"], q=0, Nk=f["Nk_per_m"])
            order.append(gk)
        groups[gk]["q"] += 1
        groups[gk]["Nk"] = max(groups[gk]["Nk"], f["Nk_per_m"])
    for i, gk in enumerate(order):
        groups[gk]["name"] = f"TJ{i+1}"
    strips = []
    for f in raw:
        gk = (f["B"], f["h"], f["bars"])
        strips.append(dict(name=groups[gk]["name"], **f))
    rows = [(groups[gk]["name"], f"{groups[gk]['B']*1000:.0f}", f"{groups[gk]['h']*1000:.0f}",
             groups[gk]["bars"], f"{groups[gk]['Nk']:.0f}", groups[gk]["q"]) for gk in order]
    return strips, rows


def _plan_area(project):
    xs, ys = [], []
    for c in project.floor.columns:
        xs.append(c.x); ys.append(c.y)
    for w in project.floor.walls:
        xs += [w.x1, w.x2]; ys += [w.y1, w.y2]
    if not xs:
        return 0.0, 0.0, 0.0
    Lx = (max(xs) - min(xs)) / 1000.0; Ly = (max(ys) - min(ys)) / 1000.0
    return Lx, Ly, max(Lx * Ly, 1.0)


def design_raft(project, result, fak=200.0):
    """**筏板基础**：平均基底反力≤fak 校核 + 冲切定板厚 + 双向构造钢筋网。
    返回 dict(area, p_avg, ok, t, bars, Nk_total)。"""
    fak = float(fak or 200.0)
    Nmap = _base_axial(result)
    Wmap = _wall_axial(result)
    Nk_total = sum(v for v in Nmap.values()) / 1.35 + sum(v for v in Wmap.values()) / 1.35   # kN
    Lx, Ly, area = _plan_area(project)
    # 含边缘外挑 0.5m
    area_raft = (Lx + 1.0) * (Ly + 1.0) if Lx > 0 else area
    p_avg = Nk_total / max(area_raft, 1.0)                              # kPa
    ok = p_avg <= fak
    # 板厚：取最重柱冲切控制(近似)：h0 ≥ N/(0.7·ft·um)，ft≈1.43MPa(C30), um≈4(c+h0)
    Nmax = max(Nmap.values(), default=0.0) * 1e3                        # N(设计值)
    ft = 1.43; c = 600.0
    h0 = 300.0
    for _ in range(40):                                                 # 迭代解 h0
        um = 4.0 * (c + h0)
        cap = 0.7 * ft * um * h0
        if cap >= Nmax or h0 > 2500:
            break
        h0 += 25.0
    t = _round_up((h0 + 45.0) / 1000.0, 0.05)                          # m
    t = min(max(t, 0.30), 2.5)
    # 构造钢筋网(双层双向)：弯矩近似 p·l²/10
    span = max(_avg_span(project), 3.0)
    M = p_avg * span * span / 10.0
    As_per_m = max(M * 1e6 / (0.9 * (t * 1000 - 45) * 360.0), 0.0015 * t * 1e6)
    return dict(area=round(area_raft, 1), p_avg=round(p_avg, 1), fak=fak, ok=ok,
                t=round(t, 2), bars=_bars_at(As_per_m), Nk_total=round(Nk_total))


def _avg_span(project):
    gx = sorted(set(project.grid.x)); gy = sorted(set(project.grid.y))
    sp = []
    for g in (gx, gy):
        for a, b in zip(g, g[1:]):
            sp.append((b - a) / 1000.0)
    return sum(sp) / len(sp) if sp else 6.0


def design_piles(project, result, Ra=1200.0, d_pile=500):
    """**桩基础**(承台)MVP：按单桩竖向承载力特征值 Ra(kN，由地勘/试桩给定)定每柱桩数 +
    承台尺寸(桩中心距 3d、边距 1d)。不含桩身配筋/群桩效应/负摩阻——须地勘+专项。
    返回 (caps, rows)。caps: {(kx,ky):{name,n,cap,Nk,x,y}}。"""
    Ra = float(Ra or 1200.0)
    Nmap = _base_axial(result)
    col_xy = {(str(round(c.x)), str(round(c.y))): (c.x, c.y) for c in project.floor.columns}
    raw = {}
    for k, (x, y) in col_xy.items():
        Nk = Nmap.get(k, 0.0) / 1.35
        n = max(int(math.ceil(1.05 * Nk / Ra)), 1)
        # 承台边长：单桩按柱宽+边距；多桩按 桩距×(行数-1)+2边距，行列尽量方阵
        rows_n = int(math.ceil(n ** 0.5))
        sp = 3 * d_pile
        cap = max(rows_n - 1, 0) * sp + 2 * d_pile          # mm
        cap = _round_up(max(cap, 1.0 * d_pile + 800), 100)
        raw[k] = dict(n=n, cap=int(cap), Nk=round(Nk), x=x, y=y)
    groups, order = {}, []
    for k, f in raw.items():
        gk = (f["n"], f["cap"])
        if gk not in groups:
            groups[gk] = dict(name="", n=f["n"], cap=f["cap"], Nk=f["Nk"], q=0)
            order.append(gk)
        groups[gk]["q"] += 1
        groups[gk]["Nk"] = max(groups[gk]["Nk"], f["Nk"])
    for i, gk in enumerate(order):
        groups[gk]["name"] = f"CT{i+1}"
    caps = {}
    for k, f in raw.items():
        caps[k] = dict(name=groups[(f["n"], f["cap"])]["name"], **f)
    rows = [(groups[gk]["name"], groups[gk]["n"], f"{groups[gk]['cap']}",
             f"{int(Ra)}", f"{groups[gk]['Nk']:.0f}", groups[gk]["q"]) for gk in order]
    return caps, rows


def recommend_foundation(project, result, fak=200.0):
    """基础选型建议：按独基占地比 + 是否含墙，给出 独基/条基/筏板 建议。
    返回 dict(kind, ratio, reason)。"""
    footings, _ = design_footings(project, result, fak)
    _, _, area = _plan_area(project)
    foot_area = sum(f["B"] * f["B"] for f in footings.values())
    ratio = foot_area / max(area, 1.0)
    has_wall = bool(project.floor.walls)
    if ratio > 0.5:
        kind = "筏板基础"
        reason = f"独立基础占地比 {ratio*100:.0f}%>50%，宜改筏板。"
    elif has_wall:
        kind = "条形基础(墙下)+独立基础(柱下)"
        reason = f"含剪力墙，墙下宜条基；柱下独基占地比 {ratio*100:.0f}%。"
    else:
        kind = "柱下独立基础"
        reason = f"独立基础占地比 {ratio*100:.0f}%≤50%，独基经济。"
    return dict(kind=kind, ratio=round(ratio, 3), reason=reason)
