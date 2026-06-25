"""地下室 + 错层(短柱) 专项。

地下室：外墙水土压力受弯配筋（复用 structdesign.codes.gb50010_basement）+ 整体抗浮校核。
  上部结构嵌固于地下室顶板(标高±0.000)，地下室外墙/底板按本模块专项设计。
错层：错层的主要危害是**短柱**(净高/截面 < 4 → 剪跨比小、易脆性剪切破坏)。
  本模块对全楼柱做短柱判别(错层、夹层、不等高均会产生)，提示全高加密箍筋 + 抗剪验算。

诚实边界：地下室外墙按**贯通全高的简化支承板带**(多层时忽略中间楼板约束→偏保守)；
抗浮重力取上部+地下室估算；真正错层须按各区不同标高建模(本版未做几何错层，仅短柱排查)。
"""
from __future__ import annotations
import math
from structdesign.codes.gb50010_basement import design_basement_wall, anti_float_check


def _plan_area(project):
    xs, ys = [], []
    for c in project.floor.columns:
        xs.append(c.x); ys.append(c.y)
    for w in project.floor.walls:
        xs += [w.x1, w.x2]; ys += [w.y1, w.y2]
    if not xs:
        return 1.0
    return max((max(xs) - min(xs)) / 1000.0 * (max(ys) - min(ys)) / 1000.0, 1.0)


def design_basement(project, takeoff=None):
    """返回 dict(wall=..., antifloat=...) 或 None(未启用)。takeoff: analyze 的材料统计 dict。"""
    b = getattr(project, "basement", None)
    if not b or not b.enabled or b.n_levels < 1:
        return None
    H = b.n_levels * b.height / 1000.0                       # 总深(m)，作外墙计算跨度(保守)
    water_height = max(H - b.water_depth, 0.0)               # 水头(m)
    wall = design_basement_wall(H, b.wall_t, "C30", "HRB400",
                                soil_unit_weight=b.soil_gamma,
                                water_height=water_height, surcharge=b.surcharge, K0=b.K0)
    # 抗浮：水头取至底板底；抗浮重力取上部结构重力代表值 + 地下室自重估算
    area = _plan_area(project)
    w_super = (takeoff or {}).get("conc_total", 0.0) * 25.0    # 上部混凝土自重估算
    w_base = area * (b.n_levels * (b.height / 1000.0) * 25.0 * 0.15 + 0.5 * 25.0)  # 墙板自重粗估
    weight = max(w_super + w_base, area * b.n_levels * 12.0)   # 兜底: 每层12kPa
    af = anti_float_check(water_height, area, weight)
    return dict(
        H=H, water_height=water_height, wall_t=b.wall_t,
        M_design=wall.M_design, As_req=wall.As_req,
        components=wall.components,
        anti_float_Kf=af.Kf, anti_float_ok=af.ok, ballast_need=af.ballast_need,
        area=area, weight=round(weight))


def short_columns(project, storey_h, beam_h=600.0, ratio_limit=4.0):
    """短柱排查：净高 Hn = 层高 - 梁高；柱净高/截面高 < ratio_limit → 短柱。
    返回 dict(n_short, total, items[]) —— items: [(sec, Hn, ratio)]。"""
    Hn = max(storey_h - beam_h, storey_h * 0.5)
    items, n_short = [], 0
    secs = {}
    for c in project.floor.columns:
        h = max(c.b, c.h)
        r = Hn / h
        key = (int(c.b), int(c.h))
        if key not in secs:
            secs[key] = r
            if r < ratio_limit:
                n_short += 1
                items.append((f"{int(c.b)}x{int(c.h)}", round(Hn), round(r, 2)))
    return dict(n_short=n_short, total=len(secs), Hn=round(Hn), items=items)
