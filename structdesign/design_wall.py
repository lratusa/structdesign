"""
墙肢生长设计编排器 —— 本软件的核心差异化能力。

在建筑给定的可行域内，自动调整墙肢长度 lw（必要时换墙厚 bw）以满足轴压比，
再完成配筋。若在建筑允许的最大范围内仍无法满足 → 不报错，而是生成
"建筑需配合清单"（反向协商），呼应"无解→反馈建筑"的设计哲学。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
import math

from .arch import WallEnvelope
from .codes import gb50010_wall as gw
from .trace import TraceLog, Basis


@dataclass
class WallGrowthResult:
    wall_id: str
    bw: float
    lw_final: float
    lw_init: float
    feasible: bool                 # 是否在建筑可行域内找到可行墙肢
    mu_N: float = 0.0
    axial_limit: float = 0.0
    reinforcement: Optional[gw.WallReinf] = None
    arch_request: str = ""         # 无解时给建筑专业的配合需求
    trials: List[str] = field(default_factory=list)
    log: TraceLog = field(default_factory=TraceLog)


def design_wall_pier(wall_id: str, N_kn: float, M_knm: float, V_kn: float,
                     env: WallEnvelope, concrete_grade: str, rebar_grade: str,
                     seismic_grade: Optional[str],
                     lw_init: Optional[float] = None,
                     step: float = 50.0) -> WallGrowthResult:
    log = TraceLog()
    limit = gw.wall_axial_limit(seismic_grade)
    res = WallGrowthResult(wall_id=wall_id, bw=0.0, lw_final=0.0,
                           lw_init=lw_init or env.lw_min, feasible=False,
                           axial_limit=limit, log=log)

    log.step(title="建筑可行域", clause="建筑模型约束", basis=Basis.ENGINEERING,
             substitution=f"墙 {wall_id} ({env.axis}): lw∈[{env.lw_min},{env.lw_max}]mm, "
                          f"可选墙厚 {env.thickness_choices()}",
             result=f"轴压比限值={limit}（{seismic_grade or '非抗震'}）")

    # 逐墙厚（由薄到厚）尝试；每个墙厚内由短到长生长 lw
    best = None
    for bw in env.thickness_choices():
        lw_req = gw.required_lw_for_axial(N_kn, bw, concrete_grade, seismic_grade)
        # 生长起点
        lw_start = max(env.lw_min, lw_init or env.lw_min)
        lw = lw_start
        # 直接跳到需求值附近再细调（等价于逐步生长，但高效）
        if lw_req > lw:
            lw = math.ceil(lw_req / step) * step
        lw = env.clamp_length(lw)
        mu = gw.wall_axial_ratio(N_kn, bw, lw, concrete_grade)
        res.trials.append(f"bw={bw}: 需 lw≥{lw_req:.0f} → 试 lw={lw:.0f}, μN={mu:.3f}")
        log.step(title=f"墙肢生长尝试 (bw={bw:.0f})", clause="GB 50011 6.4.2",
                 basis=Basis.CODE_FORMULA,
                 expression="需 lw = N/(限值·fc·bw)",
                 substitution=f"需 lw≥{lw_req:.0f}mm, 取 lw={lw:.0f}mm",
                 result=f"μN={mu:.3f} {'≤' if mu<=limit+1e-6 else '>'} 限值{limit}")
        if mu <= limit + 1e-6 and env.feasible(lw, bw):
            best = (bw, lw, mu)
            break
        # 记录该墙厚下的最优（即便不满足）
        if best is None:
            best = (bw, lw, mu)

    bw, lw, mu = best
    res.bw, res.lw_final, res.mu_N = bw, lw, mu

    if mu <= limit + 1e-6:
        res.feasible = True
        reinf = gw.design_wall_reinforcement(N_kn, bw, lw, concrete_grade,
                                             rebar_grade, seismic_grade)
        res.reinforcement = reinf
        log.step(title="墙肢确定 + 配筋", clause="GB 50011 6.4.3/6.4.5",
                 basis=Basis.CONSTRUCTION,
                 substitution=f"bw×lw={bw:.0f}×{lw:.0f}mm",
                 result=f"竖向分布筋 {reinf.vert_dist}; 边缘构件 {reinf.be_bars}(lc={reinf.be_length:.0f})")
    else:
        # 无解 → 建筑配合反馈
        res.feasible = False
        # 计算满足所需的最小 lw（最薄可行墙厚下取最有利，即最厚墙）
        bw_thick = env.thickness_choices()[-1]
        lw_need = gw.required_lw_for_axial(N_kn, bw_thick, concrete_grade, seismic_grade)
        res.arch_request = (
            f"墙 {wall_id}({env.axis}) 轴压比无法在建筑可行域内满足："
            f"当前 μN={mu:.3f} > 限值{limit}。"
            f"建议之一：(a) 墙肢加长至 lw≥{lw_need:.0f}mm（现建筑上限 {env.lw_max:.0f}mm，"
            f"需填充墙让位 {max(0, lw_need-env.lw_max):.0f}mm）；"
            f"(b) 墙厚增至 >{bw_thick:.0f}mm；(c) 提高混凝土等级；(d) 此处增设结构墙分担轴力。")
        log.step(title="无解 → 建筑配合需求", clause="设计协商", basis=Basis.ENGINEERING,
                 result=res.arch_request)
    return res
