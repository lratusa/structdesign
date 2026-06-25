"""
三维位移指标 —— 位移比(扭转不规则) + 层间位移角。

位移比(GB 50011 3.4.3)：单向地震+偶然偏心下，楼层最大水平位移/平均位移；
  >1.2 扭转不规则，>1.5 不应采用。这里对每层节点位移做刚体(平动+扭转)拟合，
  由拟合得到楼层平动 U 与转角 θ → 边缘位移 = U + θ·(半跨) → 位移比。
层间位移角(GB 50011 5.5.1)：相邻层平动差/层高，框剪限 1/800。
"""
from __future__ import annotations
from typing import Dict
import numpy as np

from .frame3d import Frame3D, Load3D, solve


def apply_lateral_and_solve(model: Frame3D, direction: str, F: float):
    """对所有楼层节点施加单向水平力并求解，返回 U_dict。"""
    saved = list(model.loads)
    for nid, n in model.nodes.items():
        if n.z > 1e-6:
            model.add_load(Load3D(nid, fx=(F if direction == "x" else 0.0),
                                  fy=(F if direction == "y" else 0.0)))
    U, _ = solve(model)
    model.loads = saved
    return U


def _floor_rigid_fit(coords, disp, comp):
    """对一层节点位移做刚体拟合，返回 (U_trans, theta, ratio)。

    comp='x': u_i = UX - θ(y_i-yc);  comp='y': u_i = UY + θ(x_i-xc)
    """
    xs = np.array([c[0] for c in coords]); ys = np.array([c[1] for c in coords])
    xc, yc = xs.mean(), ys.mean()
    d = np.array(disp)
    if comp == "x":
        Amat = np.column_stack([np.ones_like(xs), -(ys - yc)])
        half = (ys.max() - ys.min()) / 2 or 1.0
    else:
        Amat = np.column_stack([np.ones_like(xs), (xs - xc)])
        half = (xs.max() - xs.min()) / 2 or 1.0
    sol, *_ = np.linalg.lstsq(Amat, d, rcond=None)
    U, theta = sol[0], sol[1]
    if abs(U) < 1e-12:
        return U, theta, 1.0
    dmax = abs(U) + abs(theta) * half
    ratio = dmax / abs(U)
    return U, theta, ratio


def displacement_ratio(model: Frame3D, direction: str = "x", F: float = 1e4) -> float:
    """各层位移比的最大值。"""
    U = apply_lateral_and_solve(model, direction, F)
    floors = sorted({round(n.z, 3) for n in model.nodes.values() if n.z > 1e-6})
    comp = 0 if direction == "x" else 1
    worst = 1.0
    for f in floors:
        ids = [nid for nid, n in model.nodes.items() if abs(n.z - f) < 1e-3]
        coords = [(model.nodes[i].x, model.nodes[i].y) for i in ids]
        disp = [U[i][comp] for i in ids]
        _, _, ratio = _floor_rigid_fit(coords, disp, direction)
        worst = max(worst, ratio)
    return worst


def story_profiles(model: Frame3D, direction: str, floor_forces: dict, story_h: float):
    """给定各层水平力 floor_forces={z: F}，返回沿高度剖面。

    返回 list[(z, V_story, U_floor, drift_ratio)]，自下而上：
      V_story = 该层及以上各层力之和；U_floor=楼层平动；drift=层间位移角。
    """
    saved = list(model.loads)
    floors = sorted(floor_forces.keys())
    for f in floors:
        ids = [nid for nid, n in model.nodes.items() if abs(n.z - f) < 1e-3]
        per = floor_forces[f] / len(ids)
        for nid in ids:
            model.add_load(Load3D(nid, fx=(per if direction == "x" else 0.0),
                                  fy=(per if direction == "y" else 0.0)))
    U, _ = solve(model)
    model.loads = saved
    comp = 0 if direction == "x" else 1
    Uf = {}
    for f in floors:
        ids = [nid for nid, n in model.nodes.items() if abs(n.z - f) < 1e-3]
        coords = [(model.nodes[i].x, model.nodes[i].y) for i in ids]
        disp = [U[i][comp] for i in ids]
        Uf[f], _, _ = _floor_rigid_fit(coords, disp, direction)
    out = []
    prevU = 0.0
    for i, f in enumerate(floors):
        V = sum(floor_forces[ff] for ff in floors[i:])     # 该层及以上
        drift = abs(Uf[f] - prevU) / story_h
        out.append((f, V, Uf[f], drift))
        prevU = Uf[f]
    return out


def story_drift_ratio(model: Frame3D, direction: str, story_h: float, F: float = 1e4):
    """最大层间位移角 = max(相邻层平动差)/层高。"""
    U = apply_lateral_and_solve(model, direction, F)
    floors = sorted({round(n.z, 3) for n in model.nodes.values() if n.z >= -1e-6})
    comp = 0 if direction == "x" else 1
    # 各层平动(刚体拟合的U)
    Ufloor = {}
    for f in floors:
        ids = [nid for nid, n in model.nodes.items() if abs(n.z - f) < 1e-3]
        if not ids:
            continue
        coords = [(model.nodes[i].x, model.nodes[i].y) for i in ids]
        disp = [U[i][comp] for i in ids]
        Uf, _, _ = _floor_rigid_fit(coords, disp, direction)
        Ufloor[f] = Uf
    keys = sorted(Ufloor)
    worst = 0.0
    for a, b in zip(keys[:-1], keys[1:]):
        worst = max(worst, abs(Ufloor[b] - Ufloor[a]) / story_h)
    return worst
