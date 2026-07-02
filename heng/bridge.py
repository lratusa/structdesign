"""规范引擎 ↔ 现有 analyze 的桥接。

把 structdesign 的 analyze 结果投影为规范引擎上下文(ctx)，用**数据驱动的规则**做整体指标校核，
产出**带条文溯源**的结果(玻璃盒)。目的：把硬编码的 checks_table 逐步路由到 Code-as-Data 规范引擎。
"""
from __future__ import annotations
from .codes.registry import scan


def _intensity(alpha_max: float) -> str:
    return {0.04: "6", 0.08: "7", 0.12: "7.5", 0.16: "8", 0.24: "8.5", 0.32: "9"}.get(
        round(float(alpha_max), 2), "8")


def context_from_result(result, project) -> dict:
    """analyze.Result + Project → 规范引擎整体指标上下文。"""
    walls = bool(getattr(project.floor, "walls", []))
    s = project.seismic
    return {
        "element": "structure",
        "system": "frame_wall" if walls else "frame",
        "intensity": _intensity(s.alpha_max),
        "grade": s.grade,
        "period_ratio": result.period_ratio,
        "disp_ratio": max(result.disp_ratio_x, result.disp_ratio_y),
        "shear_weight": result.shear_weight,
        "drift": result.drift_x,
    }


def heng_scan(result, project, jurisdiction: str = "CN") -> dict:
    """对 analyze 结果跑规范引擎整体校核，返回 scan 摘要(含逐条溯源结果)。"""
    ctx = context_from_result(result, project)
    # 'story' 层间位移角规则也用整体 ctx，但其 scope.element=story：补一个别名上下文
    ctx_story = dict(ctx); ctx_story["element"] = "story"
    s = scan(ctx, jurisdiction)
    # 单独并入 story 规则(层间位移角)
    from .codes.registry import get
    from .codes.rule import check
    drift_rule = get("CN.GB50011-2010(2016).5.5.1")
    dr = check(drift_rule, ctx_story)
    if dr.applicable and dr.ok is not None:
        s["results"].append(dr); s["total"] += 1
        s["passed"] += 1 if dr.ok else 0
        s["failed"] += 0 if dr.ok else 1
        if not dr.ok and dr.mandatory:
            s["mandatory_failed"] += 1; s["red_line"] = True
    return s
