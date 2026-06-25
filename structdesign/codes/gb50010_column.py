"""
GB 50010-2010(2015年版) 矩形截面柱配筋内核 —— 对称配筋偏心受压。

实现（规范公式）：
  - 附加偏心距 ea、初始偏心距 ei                  规范 6.2.5
  - 大偏心 / 小偏心受压判别与对称配筋             规范 6.2.17
  - 轴压比校核                                    GB 50011 6.3.6
  - 柱全部纵筋最小配筋率                          规范 8.5.1 / GB 50011 6.3.7
方法论：均为规范闭式公式（小偏心用规范近似公式），全部走"规范公式"。
说明：本版按短柱处理（弯矩增大系数 η=1），长柱二阶效应留待后续接入。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

from .. import materials
from ..trace import TraceLog, Basis


@dataclass
class ColumnResult:
    N: float                  # 轴力设计值 (kN, 压为正)
    M: float                  # 弯矩设计值 (kN·m)
    As_each: float = 0.0      # 单侧纵筋面积 (mm²) (对称配筋)
    As_total: float = 0.0     # 全部纵筋面积 (mm²)
    eccentric: str = ""       # "大偏心"/"小偏心"
    ok: bool = True
    message: str = ""
    log: TraceLog = field(default_factory=TraceLog)


def design_column_symmetric(b, h, N_kn, M_knm, concrete_grade, rebar_grade,
                            a_s=40.0) -> ColumnResult:
    """矩形截面对称配筋偏心受压。N 压为正(kN)，M(kN·m)。返回单侧纵筋面积。"""
    log = TraceLog()
    conc = materials.concrete(concrete_grade)
    steel = materials.rebar(rebar_grade)
    N = N_kn * 1e3
    M = M_knm * 1e6
    h0 = h - a_s
    a_s_prime = a_s
    fc = conc.fc
    a1 = conc.alpha1
    fy, fyc = steel.fy, steel.fyc
    xi_b = materials.ksi_b(rebar_grade)
    res = ColumnResult(N=N_kn, M=M_knm, log=log)

    # 偏心距
    e0 = M / N
    ea = max(20.0, h / 30.0)
    ei = e0 + ea
    e = ei + h / 2.0 - a_s  # 轴力到受拉(远)钢筋合力点距离
    log.step(title="偏心距", clause="6.2.5",
             expression="e0=M/N; ea=max(20, h/30); ei=e0+ea; e=ei+h/2-a_s",
             substitution=f"e0={e0:.1f}, ea={ea:.1f}, ei={ei:.1f}, e={e:.1f} mm",
             result=f"e={e:.1f} mm")

    # 受压区高度初判 x = N/(α1 fc b)
    x = N / (a1 * fc * b)
    xi = x / h0
    log.step(title="受压区高度判别", clause="6.2.17",
             expression="x = N/(α1·fc·b)",
             substitution=f"x={x:.1f} mm, ξ=x/h0={xi:.3f}（界限 ξb={xi_b}）",
             result=("大偏心受压 (ξ≤ξb)" if xi <= xi_b else "小偏心受压 (ξ>ξb)"))

    if xi <= xi_b:
        # 大偏心受压：对称配筋
        res.eccentric = "大偏心"
        if x < 2 * a_s_prime:
            # 受压钢筋不屈服，取对受压钢筋合力点取矩
            As = N * (e - h0 + a_s_prime) / (fy * (h0 - a_s_prime))
            As = max(As, 0.0)
            log.step(title="大偏心(x<2a_s')修正", clause="6.2.17",
                     note="受压区过小，受压钢筋未屈服，对As'合力点取矩")
        else:
            As = (N * e - a1 * fc * b * x * (h0 - x / 2.0)) / (fyc * (h0 - a_s_prime))
            As = max(As, 0.0)
        log.step(title="单侧纵筋 As=As'", clause="6.2.17",
                 expression="As' = (N·e - α1·fc·b·x·(h0-x/2)) / (fy'·(h0-a_s'))",
                 substitution=f"= ({N:.0f}×{e:.1f} - {a1}×{fc}×{b}×{x:.1f}×({h0:.0f}-{x/2:.1f})) / ({fyc}×({h0:.0f}-{a_s_prime:.0f}))",
                 result=f"As=As'={As:.1f} mm²")
        res.As_each = As
    else:
        # 小偏心受压：规范近似公式重解 ξ
        res.eccentric = "小偏心"
        denom = (N * e - 0.43 * a1 * fc * b * h0 ** 2) / ((xi_b - 0.8) * (h0 - a_s_prime)) + a1 * fc * b * h0
        xi_new = (N - xi_b * a1 * fc * b * h0) / denom + xi_b
        log.step(title="小偏心重解相对受压区高度 ξ", clause="6.2.17 (附录F近似式)",
                 expression="ξ = (N - ξb·α1·fc·b·h0)/D + ξb, D=(N·e-0.43α1fc·b·h0²)/((ξb-β1)(h0-a_s'))+α1fc·b·h0",
                 substitution=f"ξ={xi_new:.3f}",
                 result=f"ξ={xi_new:.3f}")
        xi_use = min(xi_new, 1.0)
        As = (N * e - a1 * fc * b * h0 ** 2 * xi_use * (1 - 0.5 * xi_use)) / (fyc * (h0 - a_s_prime))
        As = max(As, 0.0)
        log.step(title="单侧纵筋 As=As'", clause="6.2.17",
                 expression="As' = (N·e - α1·fc·b·h0²·ξ·(1-0.5ξ)) / (fy'·(h0-a_s'))",
                 substitution=f"ξ={xi_use:.3f}",
                 result=f"As=As'={As:.1f} mm²")
        res.As_each = As

    res.As_total = 2 * res.As_each
    return res


# ----------------------------- 轴压比 -----------------------------
# 框架柱轴压比限值 (GB 50011 表6.3.6，框架结构)
AXIAL_RATIO_LIMIT = {
    "一级": 0.65,
    "二级": 0.75,
    "三级": 0.85,
    "四级": 0.90,
    None: 1.0,   # 非抗震不控制（仍受承载力控制）
}


def axial_compression_ratio(N_kn, b, h, concrete_grade, seismic_grade=None):
    """轴压比 μN = N/(fc·A)。返回 (μN, 限值, 是否满足)。"""
    conc = materials.concrete(concrete_grade)
    N = N_kn * 1e3
    A = b * h
    mu = N / (conc.fc * A)
    limit = AXIAL_RATIO_LIMIT.get(seismic_grade, 1.0)
    return mu, limit, (mu <= limit + 1e-6)


# 柱全部纵筋最小配筋率 (GB 50011 表6.3.7-1，框架中柱/边柱，HRB400)，简化取值
COLUMN_MIN_RHO = {
    "一级": 0.009,
    "二级": 0.007,
    "三级": 0.006,
    "四级": 0.005,
    None: 0.005,   # 非抗震 (规范8.5.1 全部纵筋 0.5%~0.6%)
}


def column_min_reinforcement(b, h, seismic_grade=None):
    """柱全部纵筋最小面积。返回 (As_min_total, ρmin)。"""
    rho = COLUMN_MIN_RHO.get(seismic_grade, 0.005)
    return rho * b * h, rho


@dataclass
class BiaxialResult:
    N: float
    Mx: float
    My: float
    As_total: float
    As_x: float        # 抵抗 Mx 所需(对应 h 向)
    As_y: float        # 抵抗 My 所需(对应 b 向)
    As0: float         # 纯轴力基线
    rho: float


def design_column_biaxial(b, h, N_kn, Mx_knm, My_knm, concrete_grade, rebar_grade,
                          a_s=40.0) -> BiaxialResult:
    """矩形柱双向偏心受压配筋（叠加法）。

    Mx 绕 x 轴(截面高 h 方向受弯)，My 绕 y 轴(截面宽 b 方向)。
    As = As0 + (As_x-As0) + (As_y-As0) = As_x + As_y - As0
    其中 As0=纯轴力基线。当 My=0 时退化为单偏压 As_x（可验证）。
    """
    rx = design_column_symmetric(b, h, N_kn, abs(Mx_knm), concrete_grade, rebar_grade, a_s)
    ry = design_column_symmetric(h, b, N_kn, abs(My_knm), concrete_grade, rebar_grade, a_s)
    r0 = design_column_symmetric(b, h, N_kn, 0.0, concrete_grade, rebar_grade, a_s)
    As_x, As_y, As0 = rx.As_total, ry.As_total, r0.As_total
    As = max(As_x + As_y - As0, As0, 0.0)
    return BiaxialResult(N=N_kn, Mx=Mx_knm, My=My_knm, As_total=As,
                         As_x=As_x, As_y=As_y, As0=As0, rho=As / (b * h))
