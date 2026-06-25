"""
GB 50010-2010(2015年版) 混凝土梁配筋内核。

实现（全部为规范公式，依据可追溯）：
  - 正截面受弯（矩形截面，单筋/双筋）           规范 6.2.10
  - 斜截面受剪（矩形截面，箍筋）                规范 6.3.1 / 6.3.4
  - 最小配筋率与构造                            规范 8.5.1 / 9.2.9
方法论：本构件类型规范均有闭式公式，故全部走“规范公式”，无需有限元。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

from .. import materials
from ..trace import TraceLog, Basis


# ----------------------------- 正截面受弯 -----------------------------
@dataclass
class FlexureResult:
    M: float                  # 弯矩设计值 (kN·m)
    As: float                 # 受拉钢筋计算面积 (mm²)
    As_comp: float = 0.0      # 受压钢筋计算面积 (mm²)
    xi: float = 0.0           # 相对受压区高度
    doubly: bool = False      # 是否双筋
    ok: bool = True
    message: str = ""
    log: TraceLog = field(default_factory=TraceLog)


def design_flexure(b, h, M_knm, concrete_grade, rebar_grade,
                   a_s=40.0, a_s_prime=40.0,
                   As_comp_known=0.0) -> FlexureResult:
    """矩形截面受弯配筋。M 单位 kN·m。返回受拉(及必要时受压)钢筋面积。"""
    log = TraceLog()
    conc = materials.concrete(concrete_grade)
    steel = materials.rebar(rebar_grade)
    M = M_knm * 1e6  # → N·mm
    h0 = h - a_s
    fc, ft = conc.fc, conc.ft
    a1 = conc.alpha1
    fy, fyc = steel.fy, steel.fyc
    xi_b = materials.ksi_b(rebar_grade)

    log.step(title="基本参数", clause="表4.1.4 / 表4.2.3 / 6.2.6",
             basis=Basis.CODE_FORMULA,
             substitution=(f"b={b} h={h} h0={h0:.0f}mm, {concrete_grade} fc={fc} ft={ft}, "
                           f"{rebar_grade} fy={fy}, α1={a1}, ξb={xi_b}"),
             result=f"M={M_knm} kN·m")

    res = FlexureResult(M=M_knm, As=0.0, log=log)

    # 计算系数 αs = M/(α1 fc b h0²)
    alpha_s = M / (a1 * fc * b * h0 ** 2)
    log.step(title="计算截面抵抗矩系数 αs", clause="6.2.10",
             expression="αs = M / (α1·fc·b·h0²)",
             substitution=f"αs = {M:.0f} / ({a1}×{fc}×{b}×{h0:.0f}²)",
             result=f"αs = {alpha_s:.4f}")

    if alpha_s >= 0.5:
        # 1-2αs<0，截面严重不足
        res.ok = False
        res.message = "αs≥0.5，截面受压区严重不足，需加大截面"
        log.step(title="判断", clause="6.2.10", note=res.message)
        return res

    xi = 1 - math.sqrt(1 - 2 * alpha_s)
    log.step(title="相对受压区高度 ξ", clause="6.2.10",
             expression="ξ = 1 - √(1 - 2αs)",
             substitution=f"ξ = 1 - √(1 - 2×{alpha_s:.4f})",
             result=f"ξ = {xi:.4f}（界限 ξb={xi_b}）")
    res.xi = xi

    if xi <= xi_b:
        # 单筋足够
        x = xi * h0
        As = a1 * fc * b * x / fy
        res.As = As
        res.doubly = False
        log.step(title="单筋判别", clause="6.2.10",
                 note=f"ξ={xi:.4f} ≤ ξb={xi_b}，按单筋矩形截面配筋")
        log.step(title="受拉钢筋面积 As", clause="6.2.10",
                 expression="As = α1·fc·b·x / fy,  x = ξ·h0",
                 substitution=f"As = {a1}×{fc}×{b}×{x:.1f} / {fy}",
                 result=f"As = {As:.1f} mm²")
    else:
        # 需双筋：取 x = ξb·h0
        res.doubly = True
        xb = xi_b * h0
        M_max = a1 * fc * b * xb * (h0 - 0.5 * xb)  # 单筋最大受弯承载力
        log.step(title="双筋判别", clause="6.2.14",
                 note=f"ξ={xi:.4f} > ξb={xi_b}，受压区不足，按双筋截面配置受压钢筋")
        log.step(title="单筋最大受弯承载力 Mu,max", clause="6.2.14",
                 expression="Mu,max = α1·fc·b·xb·(h0 - xb/2), xb=ξb·h0",
                 substitution=f"= {a1}×{fc}×{b}×{xb:.1f}×({h0:.0f}-{xb/2:.1f})",
                 result=f"Mu,max = {M_max/1e6:.1f} kN·m")
        # 受压钢筋
        As_prime = (M - M_max) / (fyc * (h0 - a_s_prime))
        log.step(title="受压钢筋面积 As'", clause="6.2.14",
                 expression="As' = (M - Mu,max) / (fy'·(h0 - a_s'))",
                 substitution=f"= ({M:.0f} - {M_max:.0f}) / ({fyc}×({h0:.0f}-{a_s_prime}))",
                 result=f"As' = {As_prime:.1f} mm²")
        # 受拉钢筋
        As = a1 * fc * b * xb / fy + As_prime * fyc / fy
        res.As = As
        res.As_comp = As_prime
        log.step(title="受拉钢筋面积 As", clause="6.2.14",
                 expression="As = α1·fc·b·xb/fy + As'·fy'/fy",
                 substitution=f"= {a1}×{fc}×{b}×{xb:.1f}/{fy} + {As_prime:.1f}×{fyc}/{fy}",
                 result=f"As = {As:.1f} mm²")
    return res


# --------------------------- 最小/最大配筋率 ---------------------------
def min_tension_area(b, h, concrete_grade, rebar_grade):
    """受拉钢筋最小配筋面积 (规范 8.5.1)：ρmin=max(0.20%, 0.45 ft/fy)，乘 b·h。"""
    conc = materials.concrete(concrete_grade)
    steel = materials.rebar(rebar_grade)
    rho_min = max(0.002, 0.45 * conc.ft / steel.fy)
    return rho_min * b * h, rho_min


def max_tension_check(As, b, h0, concrete_grade, rebar_grade):
    """适筋上限：ξ≤ξb 等价于 As ≤ α1 fc b ξb h0 / fy。返回(是否满足, As_max)。"""
    conc = materials.concrete(concrete_grade)
    steel = materials.rebar(rebar_grade)
    xi_b = materials.ksi_b(rebar_grade)
    As_max = conc.alpha1 * conc.fc * b * xi_b * h0 / steel.fy
    return As <= As_max * 1.0001, As_max


# ----------------------------- 斜截面受剪 -----------------------------
@dataclass
class ShearResult:
    V: float                 # 剪力设计值 (kN)
    Asv_s: float = 0.0       # 需要的箍筋面积/间距 (mm²/mm)
    only_constructional: bool = False
    section_ok: bool = True  # 剪压比(截面限制条件)
    ok: bool = True
    message: str = ""
    log: TraceLog = field(default_factory=TraceLog)


def design_shear(b, h, V_kn, concrete_grade, stirrup_grade,
                 a_s=40.0, uniform_load=True) -> ShearResult:
    """矩形截面受剪配筋（一般受弯构件，均布荷载为主）。V 单位 kN。"""
    log = TraceLog()
    conc = materials.concrete(concrete_grade)
    stir = materials.rebar(stirrup_grade)
    V = V_kn * 1e3  # → N
    h0 = h - a_s
    fc, ft = conc.fc, conc.ft
    beta_c = conc.beta_c
    fyv = stir.fyv()
    res = ShearResult(V=V_kn, log=log)

    log.step(title="基本参数", clause="表4.1.4 / 6.3.1",
             substitution=f"b={b} h0={h0:.0f}, {concrete_grade} fc={fc} ft={ft} βc={beta_c}, 箍筋 {stirrup_grade} fyv={fyv}",
             result=f"V={V_kn} kN")

    # 截面限制条件（剪压比，规范 6.3.1）
    hw = h0  # 矩形截面腹板高度近似取 h0
    ratio = hw / b
    if ratio <= 4:
        Vmax = 0.25 * beta_c * fc * b * h0
        rule = "hw/b≤4: V≤0.25βc·fc·b·h0"
    elif ratio >= 6:
        Vmax = 0.20 * beta_c * fc * b * h0
        rule = "hw/b≥6: V≤0.20βc·fc·b·h0"
    else:
        coef = 0.25 + (0.20 - 0.25) * (ratio - 4) / (6 - 4)
        Vmax = coef * beta_c * fc * b * h0
        rule = f"4<hw/b<6 内插: V≤{coef:.3f}βc·fc·b·h0"
    log.step(title="截面限制条件(剪压比)", clause="6.3.1",
             expression=rule,
             substitution=f"hw/b={ratio:.2f}, Vmax={Vmax/1e3:.1f} kN",
             result=("满足" if V <= Vmax else "不满足，需加大截面"))
    if V > Vmax:
        res.section_ok = False
        res.ok = False
        res.message = "剪压比超限，截面尺寸不足，需加大截面"
        return res

    # 混凝土受剪承载力 Vc = 0.7 ft b h0 （一般受弯构件，规范 6.3.4）
    Vc = 0.7 * ft * b * h0
    log.step(title="混凝土受剪承载力 Vc", clause="6.3.4",
             expression="Vc = 0.7·ft·b·h0",
             substitution=f"= 0.7×{ft}×{b}×{h0:.0f}",
             result=f"Vc = {Vc/1e3:.1f} kN")

    if V <= Vc:
        res.only_constructional = True
        res.Asv_s = 0.0
        log.step(title="判断", clause="6.3.4",
                 note=f"V={V_kn}kN ≤ Vc={Vc/1e3:.1f}kN，按构造配置箍筋")
    else:
        Asv_s = (V - Vc) / (fyv * h0)
        res.Asv_s = Asv_s
        log.step(title="箍筋需求 Asv/s", clause="6.3.4",
                 expression="V ≤ 0.7·ft·b·h0 + fyv·(Asv/s)·h0  ⇒  Asv/s = (V - Vc)/(fyv·h0)",
                 substitution=f"= ({V:.0f} - {Vc:.0f}) / ({fyv}×{h0:.0f})",
                 result=f"Asv/s = {Asv_s:.4f} mm²/mm")
    return res


def min_stirrup_ratio(concrete_grade, stirrup_grade):
    """箍筋最小配箍率 ρsv,min = 0.24 ft/fyv (规范 9.2.9)。"""
    conc = materials.concrete(concrete_grade)
    stir = materials.rebar(stirrup_grade)
    return 0.24 * conc.ft / stir.fyv()


def max_stirrup_spacing(h, V_exceeds_Vc):
    """箍筋最大间距 smax (规范表 9.2.9)，单位 mm。简化按梁高与是否V>Vc取值。"""
    if h <= 300:
        return 150 if V_exceeds_Vc else 200
    elif h <= 500:
        return 200 if V_exceeds_Vc else 300
    elif h <= 800:
        return 250 if V_exceeds_Vc else 350
    else:
        return 300 if V_exceeds_Vc else 400
