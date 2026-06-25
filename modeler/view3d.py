"""三维实体显示 + 状态云图（plotly 交互 HTML）。

把柱/梁/墙渲染为**实体盒**（非线框），支持三种模式：
- model：实体模型（按构件类型着色）；
- util ：构件**利用率**云图（柱/墙轴压比、梁配筋比；越红越接近/超限）——"应力/状态"代理；
- disp ：在重力+水平力下求解节点位移，画**变形体**并按位移大小着色。
输出自包含 HTML，浏览器交互旋转/缩放。
"""
from __future__ import annotations
import math

from .build.to_frame3d import build_with_meta
from structdesign.analysis.frame3d import solve, Load3D
from structdesign import loads_takedown as td

FACES = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def _prism(pa, pb, wdir, w, hdir, h):
    wx, wy, wz = wdir; hx, hy, hz = hdir
    pts = []
    for p in (pa, pb):
        for sw, sh in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts.append((p[0] + sw * w / 2 * wx + sh * h / 2 * hx,
                        p[1] + sw * w / 2 * wy + sh * h / 2 * hy,
                        p[2] + sw * w / 2 * wz + sh * h / 2 * hz))
    return pts


def _norm(dx, dy):
    L = math.hypot(dx, dy) or 1.0
    return dx / L, dy / L


def _member_prism(model, meta, mid, disp=None, scale=0.0):
    m = model.members[mid]
    ni, nj = model.nodes[m.ni], model.nodes[m.nj]
    pa = [ni.x, ni.y, ni.z]; pb = [nj.x, nj.y, nj.z]
    if disp is not None:
        ui = disp[m.ni]; uj = disp[m.nj]
        pa = [pa[k] + scale * ui[k] for k in range(3)]
        pb = [pb[k] + scale * uj[k] for k in range(3)]
    info = meta[mid]; kind = info["kind"]
    if kind == "柱":
        return _prism(pa, pb, (1, 0, 0), info["b"], (0, 1, 0), info["h"])
    if kind == "墙":
        wdx, wdy = info.get("wdir", (1, 0))
        return _prism(pa, pb, (wdx, wdy, 0), info["lw"], (-wdy, wdx, 0), info["bw"])
    # 梁：水平轴，截面 b(水平)×h(竖向)，盒下挂半高
    ax, ay = _norm(pb[0] - pa[0], pb[1] - pa[1])
    pa2 = [pa[0], pa[1], pa[2] - info["h"] / 2]
    pb2 = [pb[0], pb[1], pb[2] - info["h"] / 2]
    return _prism(pa2, pb2, (-ay, ax, 0), info["b"], (0, 0, 1), info["h"])


def _slab_box(x1, y1, x2, y2, z0, z1):
    xs = [min(x1, x2), max(x1, x2)]
    ys = [min(y1, y2), max(y1, y2)]
    return [(xs[0], ys[0], z0), (xs[1], ys[0], z0), (xs[1], ys[1], z0), (xs[0], ys[1], z0),
            (xs[0], ys[0], z1), (xs[1], ys[0], z1), (xs[1], ys[1], z1), (xs[0], ys[1], z1)]


def _rect_minus(rect, hole):
    """rect=(x0,y0,x1,y1) 挖去 hole → 至多4块边框子矩形(画框法)。无重叠返回原矩形。"""
    x0, y0, x1, y1 = rect
    hx0, hy0, hx1, hy1 = hole
    hx0 = max(x0, hx0); hy0 = max(y0, hy0); hx1 = min(x1, hx1); hy1 = min(y1, hy1)
    if hx0 >= hx1 or hy0 >= hy1:
        return [rect]
    out = []
    if hy0 > y0: out.append((x0, y0, x1, hy0))
    if hy1 < y1: out.append((x0, hy1, x1, y1))
    if hx0 > x0: out.append((x0, hy0, hx0, hy1))
    if hx1 < x1: out.append((hx1, hy0, x1, hy1))
    return out


def _slab_pieces(rect, holes):
    rects = [rect]
    for h in holes:
        nxt = []
        for r in rects:
            nxt += _rect_minus(r, h)
        rects = nxt
    return rects


def _slab_boxes(project):
    """各楼板薄盒（板顶在层标高，向下 t），并**挖去板洞/楼梯洞**。返回 [8-corner verts]。"""
    zs = project.elevations()
    boxes = []
    for fi, fl in enumerate(_level_floors(project)):
        j = fi + 1
        if j >= len(zs):
            break
        holes = [(min(o.x1, o.x2), min(o.y1, o.y2), max(o.x1, o.x2), max(o.y1, o.y2))
                 for o in list(getattr(fl, "openings", [])) + list(getattr(fl, "stairs_placed", []))]
        for sl in getattr(fl, "slabs", []):
            rect = (min(sl.x1, sl.x2), min(sl.y1, sl.y2), max(sl.x1, sl.x2), max(sl.y1, sl.y2))
            for (px0, py0, px1, py1) in _slab_pieces(rect, holes):
                if px1 - px0 > 1 and py1 - py0 > 1:
                    z1 = zs[j]; z0 = z1 - sl.t
                    boxes.append(_slab_box(px0, py0, px1, py1, z0, z1))
    return boxes


def _level_floors(project):
    try:
        return project.level_floors()
    except Exception:
        return [project.floor] * max(len(project.elevations()) - 1, 1)


def _stair_prisms(project):
    """楼梯：每层在楼梯布置处画一道斜跑板(从下层标高升到本层标高)。返回 [(verts8, color)]。"""
    zs = project.elevations()
    out = []
    for fi, fl in enumerate(_level_floors(project)):
        j = fi + 1
        if j >= len(zs):
            break
        z0, z1 = zs[j - 1], zs[j]
        for s in getattr(fl, "stairs_placed", []):
            x0, y0 = min(s.x1, s.x2), min(s.y1, s.y2)
            x1, y1 = max(s.x1, s.x2), max(s.y1, s.y2)
            along_x = (x1 - x0) >= (y1 - y0)
            t = 60.0   # 斜板厚(示意)
            if along_x:
                pa = [x0, (y0 + y1) / 2, z0]; pb = [x1, (y0 + y1) / 2, z1]
                verts = _prism(pa, pb, (0, 1, 0), (y1 - y0) * 0.9, (0, 0, 1), t)
            else:
                pa = [(x0 + x1) / 2, y0, z0]; pb = [(x0 + x1) / 2, y1, z1]
                verts = _prism(pa, pb, (1, 0, 0), (x1 - x0) * 0.9, (0, 0, 1), t)
            out.append((verts, "#e0a23a"))
    return out


def _basement_prisms(project):
    """地下室(视觉)：柱下延 + 周边外墙 + 各层底板，标高为负。返回 [(verts8, color)]。"""
    b = getattr(project, "basement", None)
    if not b or not getattr(b, "enabled", False) or b.n_levels < 1:
        return []
    h = b.height
    depth = b.n_levels * h
    out = []
    cols = project.floor.columns
    xs = [c.x for c in cols] or [0]; ys = [c.y for c in cols] or [0]
    x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    # 柱下延到基底
    for c in cols:
        verts = _prism([c.x, c.y, -depth], [c.x, c.y, 0.0], (1, 0, 0), c.b, (0, 1, 0), c.h)
        out.append((verts, "#7a6a55"))
    # 周边外墙(四边)，全地下高
    tw = b.wall_t
    for (ax, ay, bx, by) in [(x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)]:
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        # 外墙盒：沿墙线、厚 tw、全地下高
        wbx = _prism([(ax + bx) / 2, (ay + by) / 2, -depth], [(ax + bx) / 2, (ay + by) / 2, 0.0],
                     (ux, uy, 0), L, (-uy, ux, 0), tw)
        out.append((wbx, "#6f6f78"))
    # 各地下层底板(浅)
    for k in range(1, b.n_levels + 1):
        z = -k * h
        out.append((_slab_box(x0, y0, x1, y1, z - 120, z), "#b8a98f"))
    return out


def _util_map(result):
    """构件 util 0..~1.2：柱/墙轴压比/0.9；梁 As/(0.025 b h0)；不足→≥1。"""
    out = {}
    for m in (result.members if result else []):
        if m["kind"] in ("柱", "墙"):
            u = m.get("mu", 0) / 0.9
        else:
            try:
                b, h = [float(v) for v in m["sec"].split("×")]
            except Exception:
                b, h = 300, 600
            u = m.get("As", 0) / max(0.025 * b * (h - 40), 1)
        if not m.get("ok", True):
            u = max(u, 1.05)
        out[m["id"]] = u
    return out


def _disp_solve(project, model):
    s = project.floor.slab
    q = td.slab_q(s.dead, s.live)
    xs = [n.x for n in model.nodes.values()]; ys = [n.y for n in model.nodes.values()]
    area = max((max(xs) - min(xs)) / 1000.0, 1) * max((max(ys) - min(ys)) / 1000.0, 1)
    plan = {(round(n.x), round(n.y)) for n in model.nodes.values() if n.z > 1e-6}
    n_per = max(len(plan), 1)
    Htot = max((n.z for n in model.nodes.values()), default=1.0) or 1.0
    w_node = q * area * 1000.0 / n_per
    for n in model.nodes.values():
        if n.z > 1e-6:
            model.add_load(Load3D(n.id, fz=-w_node, fx=0.15 * w_node * (n.z / Htot)))
    raw, _ = solve(model)
    # 刚性楼盖侧移：每标高取节点侧移均值，整层同移（消除等效宽柱局部朝向伪影）
    from collections import defaultdict
    lv = defaultdict(list)
    for nid, n in model.nodes.items():
        lv[round(n.z, 1)].append(nid)
    levelU = {}
    for z, nids in lv.items():
        levelU[z] = (sum(raw[i][0] for i in nids) / len(nids),
                     sum(raw[i][1] for i in nids) / len(nids))
    disp = {}
    for nid, n in model.nodes.items():
        mx, my = levelU[round(n.z, 1)]
        disp[nid] = (mx, my, 0.0)
    return disp


def build_figure(project, result=None, mode="model"):
    model, meta = build_with_meta(project)
    disp = None; scale = 0.0
    if mode == "disp":
        disp = _disp_solve(project, model)
        span = max(max((n.x for n in model.nodes.values()), default=1),
                   max((n.z for n in model.nodes.values()), default=1)) or 1.0
        umax = max((math.sqrt(sum(disp[nid][k] ** 2 for k in range(3)))
                    for nid in disp), default=1.0) or 1.0
        scale = 0.08 * span / umax
    util = _util_map(result) if mode == "util" else {}

    X, Y, Z, I, J, K, inten = [], [], [], [], [], [], []
    base = 0
    KCOL = {"柱": "#d83a3a", "梁": "#1a9e5a", "墙": "#1f6feb"}
    facecolors = []
    for mid in model.members:
        verts = _member_prism(model, meta, mid, disp, scale)
        for (vx, vy, vz) in verts:
            X.append(vx); Y.append(vy); Z.append(vz)
        if mode == "util":
            val = util.get(mid, 0.0)
            inten += [val] * 8
        elif mode == "disp":
            m = model.members[mid]
            du = max(math.sqrt(sum(disp[m.ni][k] ** 2 for k in range(3))),
                     math.sqrt(sum(disp[m.nj][k] ** 2 for k in range(3))))
            inten += [du] * 8
        else:
            facecolors += [KCOL.get(meta[mid]["kind"], "#888888")] * 12
        for (a, b, c) in FACES:
            I.append(base + a); J.append(base + b); K.append(base + c)
        base += 8

    # 楼板 + 楼梯 + 地下室（model / load 模式显示）
    if mode in ("model", "load"):
        extras = [(v, "#c9d4e0") for v in _slab_boxes(project)]
        extras += _stair_prisms(project)
        extras += _basement_prisms(project)
        for verts, col in extras:
            for (vx, vy, vz) in verts:
                X.append(vx); Y.append(vy); Z.append(vz)
            facecolors += [col] * 12
            for (a, b, c) in FACES:
                I.append(base + a); J.append(base + b); K.append(base + c)
            base += 8

    import plotly.graph_objects as go
    op = 0.45 if mode == "load" else 1.0      # 荷载模式：模型半透明以便看荷载箭头
    kw = dict(x=X, y=Y, z=Z, i=I, j=J, k=K, flatshading=True, opacity=op)
    if mode in ("util", "disp"):
        kw.update(intensity=inten, colorscale=("Turbo" if mode == "disp" else "Jet"),
                  showscale=True,
                  colorbar=dict(title=("位移|U|" if mode == "disp" else "利用率")))
    else:
        kw.update(facecolor=facecolors)
    mesh = go.Mesh3d(**kw)
    title = {"model": "三维实体模型", "util": "构件利用率云图（轴压比/配筋比）",
             "disp": "变形体（重力+水平力，位移云图，已放大）",
             "load": "荷载分布（重力 ↓ 蓝 · 风荷载 → 橙）"}[mode]
    data = [mesh]
    if mode == "load":
        data += _load_cone_traces(project, result)
    fig = go.Figure(data=data)
    fig.update_layout(title=title, scene=dict(aspectmode="data",
                      xaxis_title="X", yaxis_title="Y", zaxis_title="Z(mm)"),
                      margin=dict(l=0, r=0, t=40, b=0))
    return fig


def _load_cone_traces(project, result):
    """荷载可视化：重力(向下蓝锥) + 风荷载(水平橙锥)。返回 plotly 轨迹列表。"""
    import plotly.graph_objects as go
    zs = project.elevations()
    cols = project.floor.columns
    xs = [c.x for c in cols] or [0]; ys = [c.y for c in cols] or [0]
    x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    sp = max(x1 - x0, y1 - y0, 1000)
    traces = []
    # 重力：每层 3×3 网格向下锥
    gx, gy, gz, gu, gv, gw = [], [], [], [], [], []
    for j in range(1, len(zs)):
        for fx in (0.2, 0.5, 0.8):
            for fy in (0.2, 0.5, 0.8):
                gx.append(x0 + fx * (x1 - x0)); gy.append(y0 + fy * (y1 - y0)); gz.append(zs[j])
                gu.append(0); gv.append(0); gw.append(-1)
    if gx:
        traces.append(go.Cone(x=gx, y=gy, z=gz, u=gu, v=gv, w=gw, sizemode="absolute",
                              sizeref=sp * 0.18, anchor="tip", colorscale=[[0, "#1f6feb"], [1, "#1f6feb"]],
                              showscale=False, name="重力"))
    # 风荷载：迎风面(y0 边)每层水平锥(+X)，大小按楼层风力
    try:
        from .run.wind import wind_story_forces
        wf, info = wind_story_forces(project, "x")
    except Exception:
        wf, info = {}, {}
    if wf:
        fmax = max(wf.values()) or 1.0
        wx, wy, wz, wu, wv, ww = [], [], [], [], [], []
        for z_mm, F in wf.items():
            wx.append(x0 - sp * 0.05); wy.append((y0 + y1) / 2); wz.append(z_mm)
            wu.append(F / fmax); wv.append(0); ww.append(0)
        traces.append(go.Cone(x=wx, y=wy, z=wz, u=wu, v=wv, w=ww, sizemode="absolute",
                              sizeref=sp * 0.16, anchor="tail",
                              colorscale=[[0, "#e0772a"], [1, "#e0772a"]], showscale=False, name="风荷载"))
    return traces


def export_html(project, result, path, mode="model"):
    fig = build_figure(project, result, mode)
    # 内嵌 plotly.js（离线自包含，便于分发给试用人员）
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


def _mode_nodal_disp(model, modal, j):
    """第 j 阶振型(缩减空间列)→ 各节点位移 {nid:(ux,uy,0)}（刚性楼盖关系展开）。"""
    import numpy as np
    nodes = model.nodes
    floors = modal.floors
    fn = modal.floor_nodes
    cen = {f: (sum(nodes[k].x for k in fn[f]) / len(fn[f]),
               sum(nodes[k].y for k in fn[f]) / len(fn[f])) for f in floors}
    phi = modal.modes_dyn[:, j]
    dr = modal.dyn_red
    floorUF = {}
    for f in floors:
        floorUF[f] = (phi[dr[("UX", f)]], phi[dr[("UY", f)]], phi[dr[("RZ", f)]])
    disp = {}
    for nid, n in nodes.items():
        f = round(n.z, 3)
        if f not in floorUF:
            disp[nid] = (0.0, 0.0, 0.0); continue
        UX, UY, RZ = floorUF[f]; xc, yc = cen[f]
        disp[nid] = (UX - (n.y - yc) * RZ, UY + (n.x - xc) * RZ, 0.0)
    return disp


def _pick_mode_column(modal, which):
    """选振型列号 j。which: '扭转'/'X'/'Y' 或 int 阶号。返回 (j, 描述)。"""
    import numpy as np
    floors = modal.floors; dr = modal.dyn_red
    allx = []  # 各列分类
    R = 1.0
    cols = modal.modes_dyn.shape[1]
    info = []
    for j in range(cols):
        phi = modal.modes_dyn[:, j]
        sx = sum(abs(phi[dr[("UX", f)]]) for f in floors)
        sy = sum(abs(phi[dr[("UY", f)]]) for f in floors)
        st = sum(abs(phi[dr[("RZ", f)]]) for f in floors)
        T = modal.periods_all[j]
        kind = "扭转" if st * 1.0 > (sx ** 2 + sy ** 2) ** 0.5 else ("X" if sx >= sy else "Y")
        info.append((j, kind, T))
    if isinstance(which, int):
        return which, f"第{which+1}阶"
    # 取该类别中周期最长者
    cand = [t for t in info if t[1] == which]
    if not cand:
        cand = info
    cand.sort(key=lambda t: -t[2])
    j = cand[0][0]
    return j, f"{which}向振型 T={cand[0][2]:.2f}s"


def export_mode_animation(project, result, path, which="扭转", n_frames=24):
    """振型 3D 动画(plotly)：把指定振型(默认第一扭转)随时间摆动，播放看平动/**扭转旋转**。
    which: '扭转'/'X'/'Y' 或 阶号 int。输出自包含 HTML（带播放按钮）。"""
    import numpy as np
    import plotly.graph_objects as go
    from structdesign.analysis.modal3d import rigid_diaphragm_modal
    from structdesign.frame3d_builder import floor_masses
    model, meta = build_with_meta(project)
    fm = floor_masses(model, 1.0)
    modal = rigid_diaphragm_modal(model, fm)
    j, desc = _pick_mode_column(modal, which)
    disp = _mode_nodal_disp(model, modal, j)
    span = max((n.x for n in model.nodes.values()), default=1) or 1.0
    umax = max((math.hypot(disp[i][0], disp[i][1]) for i in disp), default=1.0) or 1.0
    amp = 0.10 * max(span, max((n.z for n in model.nodes.values()), default=1)) / umax

    KCOL = {"柱": "#d83a3a", "梁": "#1a9e5a", "墙": "#1f6feb"}

    def frame_mesh(scale):
        X, Y, Z, I, J, K, fcs = [], [], [], [], [], [], []
        base = 0
        for mid in model.members:
            verts = _member_prism(model, meta, mid, disp, scale)
            for (vx, vy, vz) in verts:
                X.append(vx); Y.append(vy); Z.append(vz)
            fcs += [KCOL.get(meta[mid]["kind"], "#888")] * 12
            for (a, b, c) in FACES:
                I.append(base + a); J.append(base + b); K.append(base + c)
            base += 8
        return go.Mesh3d(x=X, y=Y, z=Z, i=I, j=J, k=K, facecolor=fcs, flatshading=True)

    phases = [amp * math.sin(2 * math.pi * k / n_frames) for k in range(n_frames)]
    frames = [go.Frame(data=[frame_mesh(s)], name=str(k)) for k, s in enumerate(phases)]
    fig = go.Figure(data=[frame_mesh(phases[0])], frames=frames)
    fig.update_layout(
        title=f"振型动画：{desc}（{'楼层绕竖轴扭转' if which=='扭转' else '楼层平动'}，已放大）",
        scene=dict(aspectmode="data", xaxis_title="X", yaxis_title="Y", zaxis_title="Z(mm)"),
        margin=dict(l=0, r=0, t=46, b=0),
        updatemenus=[dict(type="buttons", showactive=False, y=1, x=0.0, xanchor="left",
                          buttons=[dict(label="▶ 播放", method="animate",
                                        args=[None, dict(frame=dict(duration=60, redraw=True),
                                                         fromcurrent=True, mode="immediate")]),
                                   dict(label="⏸ 暂停", method="animate",
                                        args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                           mode="immediate")])])])
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# 6 个四边形面(供 matplotlib Poly3DCollection)
_QUADS = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def export_png(project, result, path, mode="model"):
    """matplotlib 三维实体 PNG（离线，不需浏览器/kaleido），供嵌入计算书或快速预览。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    model, meta = build_with_meta(project)
    disp = None; scale = 0.0
    if mode == "disp":
        disp = _disp_solve(project, model)
        span = max(max((n.x for n in model.nodes.values()), default=1),
                   max((n.z for n in model.nodes.values()), default=1)) or 1.0
        umax = max((math.sqrt(sum(disp[nid][k] ** 2 for k in range(3))) for nid in disp), default=1.0) or 1.0
        scale = 0.08 * span / umax
    util = _util_map(result) if mode == "util" else {}

    polys, vals, fcs = [], [], []
    KCOL = {"柱": "#d83a3a", "梁": "#1a9e5a", "墙": "#1f6feb"}
    for mid in model.members:
        v = _member_prism(model, meta, mid, disp, scale)
        for q in _QUADS:
            polys.append([v[i] for i in q])
        if mode == "util":
            vals += [util.get(mid, 0.0)] * 6
        elif mode == "disp":
            m = model.members[mid]
            du = max(math.sqrt(sum(disp[m.ni][k] ** 2 for k in range(3))),
                     math.sqrt(sum(disp[m.nj][k] ** 2 for k in range(3))))
            vals += [du] * 6
        else:
            fcs += [KCOL.get(meta[mid]["kind"], "#888888")] * 6

    if mode in ("model", "load"):
        extras = [(v, "#c9d4e0") for v in _slab_boxes(project)]
        extras += _stair_prisms(project)
        extras += _basement_prisms(project)
        for verts, col in extras:
            for q in _QUADS:
                polys.append([verts[i] for i in q])
            fcs += [col] * 6

    fig = plt.figure(figsize=(9, 8)); ax = fig.add_subplot(111, projection="3d")
    if mode in ("util", "disp"):
        norm = mcolors.Normalize(min(vals or [0]), max(vals or [1]) or 1)
        cmap = cm.get_cmap("jet" if mode == "util" else "turbo")
        pc = Poly3DCollection(polys, facecolors=[cmap(norm(x)) for x in vals],
                              edgecolors=(0, 0, 0, 0.25), linewidths=0.15)
        ax.add_collection3d(pc)
        sm = cm.ScalarMappable(norm=norm, cmap=cmap); sm.set_array([])
        fig.colorbar(sm, ax=ax, shrink=0.6, label=("Utilization" if mode == "util" else "|U|"))
    else:
        pc = Poly3DCollection(polys, facecolors=fcs, edgecolors=(0, 0, 0, 0.35), linewidths=0.2)
        ax.add_collection3d(pc)

    xs = [n.x for n in model.nodes.values()]; ys = [n.y for n in model.nodes.values()]
    zs = [n.z for n in model.nodes.values()]
    ax.set_xlim(min(xs), max(xs)); ax.set_ylim(min(ys), max(ys)); ax.set_zlim(min(zs), max(zs))
    try:
        ax.set_box_aspect((max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(zs) - min(zs) + 1))
    except Exception:
        pass
    ax.view_init(elev=18, azim=-58)
    ax.set_title({"model": "3D Solid Model (slab holes / stairs / basement)",
                  "load": "Load Distribution", "util": "Member Utilization",
                  "disp": "Deformed Shape (|U|, scaled)"}.get(mode, "3D Model"),
                 fontsize=17, fontweight="bold")
    fig.savefig(path, dpi=140); plt.close(fig)
    return path
