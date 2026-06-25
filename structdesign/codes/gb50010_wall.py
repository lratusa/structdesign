"""
GB 50010 / GB 50011 剪力墙墙肢 —— 轴压比、分布钢筋、边缘构件（简化但可追溯）。

方法论标注：
  - 轴压比 μN=N/(fc·A)：规范公式（GB 50011 6.4.2）。
  - 竖向/水平分布筋最小配筋率：构造规定（GB 50011 6.4.3）。
  - 边缘构件纵筋最小量：构造规定（GB 50011 6.4.5，本版取简化配筋率，标注为简化）。
"""
from __future__ import annotations
from dataclasses import dataclass

from .. import materials
from ..trace import Basis


# 剪力墙墙肢轴压比限值（GB 50011 表6.4.2，简化按抗震等级取常用值）
WALL_AXIAL_LIMIT = {
    "一级": 0.5,   # 一级(6/7/8度)
    "二级": 0.6,
    "三级": 0.6,
    "四级": 0.7,
    None: 1.0,     # 非抗震不由轴压比控制
}

# 分布钢筋最小配筋率（GB 50011 6.4.3）
def dist_min_ratio(seismic_grade):
    return 0.0025 if seismic_grade in ("一级", "二级", "三级") else 0.0020

# 边缘构件纵筋简化最小配筋率（GB 50011 6.4.5 简化）
BE_MIN_RHO = {"一级": 0.010, "二级": 0.008, "三级": 0.006, "四级": 0.005, None: 0.005}


def wall_axial_ratio(N_kn, bw, lw, concrete_grade):
    """墙肢轴压比 μN = N/(fc·bw·lw)。"""
    conc = materials.concrete(concrete_grade)
    A = bw * lw
    return N_kn * 1e3 / (conc.fc * A)


def wall_axial_limit(seismic_grade):
    return WALL_AXIAL_LIMIT.get(seismic_grade, 1.0)


def required_lw_for_axial(N_kn, bw, concrete_grade, seismic_grade):
    """满足轴压比所需的最小墙肢长度 lw = N/(limit·fc·bw)。"""
    conc = materials.concrete(concrete_grade)
    limit = wall_axial_limit(seismic_grade)
    if limit >= 1.0:
        return 0.0
    return N_kn * 1e3 / (limit * conc.fc * bw)


@dataclass
class WallReinf:
    lw: float
    bw: float
    mu_N: float
    axial_limit: float
    axial_ok: bool
    # 分布筋
    rho_dist_min: float
    vert_dist: str          # 竖向分布筋配置
    horiz_dist: str         # 水平分布筋配置
    # 边缘构件
    be_length: float
    be_As: float
    be_bars: str
    note: str = ""


def design_wall_reinforcement(N_kn, bw, lw, concrete_grade, rebar_grade,
                              seismic_grade) -> WallReinf:
    """给定（已满足轴压比的）墙肢，配置分布筋与边缘构件纵筋。"""
    from .. import rebar as rb
    conc = materials.concrete(concrete_grade)
    mu = wall_axial_ratio(N_kn, bw, lw, concrete_grade)
    limit = wall_axial_limit(seismic_grade)
    rho_min = dist_min_ratio(seismic_grade)

    # 竖向分布筋：双层，选直径与间距满足 ρ≥ρmin（每延米）
    # ρ = (层数·As1·(1000/s)) / (bw·1000) ≥ ρmin
    vert = _pick_dist(bw, rho_min)
    horiz = _pick_dist(bw, rho_min)

    # 边缘构件（构造边缘构件，简化）：lc=max(bw,400)，纵筋 ρ_be
    lc = max(bw, 400.0)
    rho_be = BE_MIN_RHO.get(seismic_grade, 0.005)
    be_As = rho_be * bw * lc
    be_bars = rb.select_bars(be_As, bw if bw > 250 else 250, diameters=[16, 18, 20, 22, 25])

    return WallReinf(
        lw=lw, bw=bw, mu_N=mu, axial_limit=limit, axial_ok=(mu <= limit + 1e-6),
        rho_dist_min=rho_min, vert_dist=vert, horiz_dist=horiz,
        be_length=lc, be_As=be_As, be_bars=be_bars.label(),
    )


def _pick_dist(bw, rho_min, layers=2):
    """选分布筋(双层) D@s 满足最小配筋率。返回如 'D10@200(双层)'。"""
    from .. import rebar as rb
    import math
    for d in (8, 10, 12):
        a1 = rb.area(d)
        for s in (200, 150, 100):
            rho = layers * a1 * (1000.0 / s) / (bw * 1000.0)
            if rho >= rho_min and d >= 8 and s <= 300:
                return f"D{d}@{s}(双层, ρ={rho*100:.2f}%)"
    return "D12@100(双层)"
