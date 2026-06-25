"""
GB 50010 正常使用极限状态 —— 受弯构件裂缝宽度与挠度。

  - 最大裂缝宽度 ωmax (规范 7.1.2)：规范公式。
  - 挠度 (规范 7.2.2 / 7.2.5)：刚度 B 法，含长期效应 θ；本版用矩形截面简化。
内力用准永久组合 Mq。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

from .. import materials
from ..trace import TraceLog, Basis

# 混凝土抗拉强度标准值 ftk (规范表4.1.3)
_FTK = {"C20": 1.54, "C25": 1.78, "C30": 2.01, "C35": 2.20,
        "C40": 2.39, "C45": 2.51, "C50": 2.64, "C55": 2.74, "C60": 2.85}
# 混凝土弹性模量已在 materials.Concrete.Ec

# 相对粘结特性系数 ν：带肋 1.0，光面 0.7
def _nu(rebar_grade):
    return 0.7 if rebar_grade.upper().startswith("HPB") else 1.0


@dataclass
class CrackResult:
    wmax: float
    sigma_sq: float
    psi: float
    rho_te: float
    limit: float
    ok: bool
    log: TraceLog = field(default_factory=TraceLog)


def crack_width(b, h, As, Mq_knm, concrete_grade, rebar_grade,
                d_bar, c=25.0, a_s=40.0, alpha_cr=1.9, w_limit=0.3) -> CrackResult:
    """受弯构件最大裂缝宽度 (规范 7.1.2)。Mq 为准永久组合弯矩。"""
    log = TraceLog()
    ftk = _FTK[concrete_grade.upper()]
    steel = materials.rebar(rebar_grade)
    Es = steel.Es
    h0 = h - a_s
    Mq = Mq_knm * 1e6

    Ate = 0.5 * b * h
    rho_te = max(As / Ate, 0.01)
    sigma_sq = Mq / (0.87 * h0 * As)
    psi = 1.1 - 0.65 * ftk / (rho_te * sigma_sq)
    psi = min(max(psi, 0.2), 1.0)
    nu = _nu(rebar_grade)
    deq = d_bar / nu  # 单一直径等效

    wmax = alpha_cr * psi * (sigma_sq / Es) * (1.9 * c + 0.08 * deq / rho_te)

    log.step(title="有效配筋率 ρte", clause="7.1.2",
             expression="ρte = As/(0.5·b·h) ≥ 0.01",
             substitution=f"= {As:.0f}/{Ate:.0f}", result=f"ρte={rho_te:.4f}")
    log.step(title="钢筋应力 σsq", clause="7.1.4",
             expression="σsq = Mq/(0.87·h0·As)",
             substitution=f"= {Mq:.0f}/(0.87×{h0:.0f}×{As:.0f})",
             result=f"σsq={sigma_sq:.1f} N/mm²")
    log.step(title="裂缝间钢筋应变不均匀系数 ψ", clause="7.1.2",
             expression="ψ = 1.1 - 0.65·ftk/(ρte·σsq), 0.2≤ψ≤1.0",
             substitution=f"ftk={ftk}", result=f"ψ={psi:.4f}")
    log.step(title="最大裂缝宽度 ωmax", clause="7.1.2",
             expression="ωmax = αcr·ψ·(σsq/Es)·(1.9c + 0.08·deq/ρte)",
             substitution=f"αcr={alpha_cr}, c={c}, deq={deq:.1f}",
             result=f"ωmax={wmax:.3f} mm（限值 {w_limit}）")

    return CrackResult(wmax=wmax, sigma_sq=sigma_sq, psi=psi, rho_te=rho_te,
                       limit=w_limit, ok=(wmax <= w_limit + 1e-9), log=log)


@dataclass
class DeflectionResult:
    f: float          # 挠度 (mm)
    limit: float      # 挠度限值 (mm)
    ok: bool
    Bs: float
    B: float
    log: TraceLog = field(default_factory=TraceLog)


def deflection(b, h, As, Mq_knm, l0, concrete_grade, rebar_grade,
               a_s=40.0, theta=2.0, span_ratio=200.0, load_pattern=5/48) -> DeflectionResult:
    """受弯构件挠度（矩形截面简化 B 法）。

    Bs 短期刚度(规范7.2.3简化), B=Bs/θ 长期刚度(7.2.5)。
    f = load_pattern·Mq·l0²/B（默认均布简支 5/48）。挠度限值 l0/span_ratio。
    """
    log = TraceLog()
    conc = materials.concrete(concrete_grade)
    steel = materials.rebar(rebar_grade)
    Ec, Es = conc.Ec, steel.Es
    h0 = h - a_s
    Mq = Mq_knm * 1e6
    alphaE = Es / Ec
    rho = As / (b * h0)

    # 规范7.2.3 受弯构件短期刚度简化式
    ftk = _FTK[concrete_grade.upper()]
    Ate = 0.5 * b * h
    rho_te = max(As / Ate, 0.01)
    sigma_sq = Mq / (0.87 * h0 * As)
    psi = min(max(1.1 - 0.65 * ftk / (rho_te * sigma_sq), 0.2), 1.0)
    gamma_f = 0.0  # 矩形截面无受拉翼缘
    Bs = (Es * As * h0 ** 2) / (1.15 * psi + 0.2 + 6 * alphaE * rho / (1 + 3.5 * gamma_f))
    B = Bs / theta
    f = load_pattern * Mq * l0 ** 2 / B
    f_limit = l0 / span_ratio

    log.step(title="短期刚度 Bs", clause="7.2.3", basis=Basis.CODE_FORMULA,
             expression="Bs = Es·As·h0² / (1.15ψ + 0.2 + 6αE·ρ/(1+3.5γf'))",
             substitution=f"αE={alphaE:.2f}, ρ={rho:.4f}, ψ={psi:.3f}",
             result=f"Bs={Bs:.3e} N·mm²")
    log.step(title="长期刚度 B", clause="7.2.5", basis=Basis.CODE_FORMULA,
             expression="B = Bs/θ", substitution=f"θ={theta}",
             result=f"B={B:.3e} N·mm²")
    log.step(title="挠度 f", clause="7.2.2", basis=Basis.CODE_FORMULA,
             expression="f = s·Mq·l0²/B",
             substitution=f"s={load_pattern:.4f}, l0={l0}",
             result=f"f={f:.2f} mm（限值 l0/{span_ratio:.0f}={f_limit:.1f}）")
    return DeflectionResult(f=f, limit=f_limit, ok=(f <= f_limit), Bs=Bs, B=B, log=log)
