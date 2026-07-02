"""规范引擎 ↔ 现有 analyze 的桥接。

把 structdesign 的 analyze 结果投影为规范引擎上下文(ctx)，用**数据驱动的规则**做整体指标校核，
产出**带条文溯源**的结果(玻璃盒)。目的：把硬编码的 checks_table 逐步路由到 Code-as-Data 规范引擎。
"""
from __future__ import annotations
from .codes.registry import scan, rules_for
from .codes.rule import check


def _sec(sec: str):
    """'300×700'/'300x700' → (300, 700)。"""
    try:
        a, b = str(sec).replace("×", "x").split("x")
        return float(a), float(b)
    except Exception:
        return 0.0, 0.0


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


# ---------------- 构件级校核（把配筋校核纳入规范引擎，逐构件带条文出处） ----------------

def member_context(m: dict, project) -> dict:
    """analyze 的一个 member(柱/墙/梁) → 构件级规范上下文。"""
    s = project.seismic
    ctx = {"material": "reinforced_concrete", "grade": s.grade,
           "intensity": _intensity(s.alpha_max)}
    kind = m.get("kind")
    if kind == "柱":
        ctx.update(element="column", rho=m.get("rho", 0.0), mu=m.get("mu", 0.0))
    elif kind == "墙":
        ctx.update(element="wall", mu=m.get("mu", 0.0))
    elif kind == "梁":
        b, h = _sec(m.get("sec", "0x0"))
        As = max(m.get("As_top", 0.0), m.get("As_bot", 0.0), m.get("As", 0.0))
        rho = As / (b * h) if b * h > 0 else 0.0
        ctx.update(element="beam", rho=rho, ft=1.43, fy=360.0)   # 混凝土C30/HRB400 代表值
    return ctx


def member_check(m: dict, project, jurisdiction: str = "CN") -> dict:
    """对一个构件跑所有适用的构件级规则(数据缺失的规则自动跳过)，返回带溯源的逐条结果。"""
    ctx = member_context(m, project)
    el = ctx.get("element")
    out = []
    for r in rules_for(jurisdiction):
        if el not in (r.scope.get("element") or []):
            continue
        res = check(r, ctx)
        if res.applicable and not res.error and res.ok is not None:
            out.append(res)
    # 控制条文标注(§6.2)：哪条规范最卡这个构件
    from .governing import governing_clause
    gov = governing_clause(ctx, jurisdiction)["governing"]
    return dict(id=m.get("id"), kind=m.get("kind"), sec=m.get("sec"),
                results=out, ok=all(x.ok for x in out) if out else True,
                n_rules=len(out), governing=gov)


def member_scan(result, project, jurisdiction: str = "CN") -> dict:
    """全构件级校核：逐构件跑规范引擎。返回 {members:[...], failed:[...], n_checks}。"""
    per = [member_check(m, project, jurisdiction) for m in result.members]
    failed = [x for x in per if not x["ok"]]
    return dict(members=per, failed=failed,
                n_checks=sum(x["n_rules"] for x in per),
                all_ok=not failed)
