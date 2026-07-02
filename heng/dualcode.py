"""双规范并行对照报告（设计书 §4.4，跨国项目"杀手锏"）。

同一 SSM 上下文，两套规范上下文并行校核，按概念(concept)配对，输出逐条对照：
各自 rule_id / 判定 / 控制限值 / 差异说明。**映射仅用于解释差异，不换算结果**——
每套结论由各自规范独立算出。
"""
from __future__ import annotations
from .codes.registry import rules_for
from .codes.rule import check
from .codes.jurisdiction import resolve


def _limit(values: dict):
    """从中间量里挑出"限值"(名以 _min/_max/_lim 结尾)。"""
    for k, v in values.items():
        if k.endswith(("_min", "_max", "_lim")) and isinstance(v, (int, float)):
            return k, v
    return None, None


def _side(res):
    if res is None or not res.applicable:
        return None
    lk, lv = _limit(res.values)
    return {"rule_id": res.rule_id, "clause": res.provenance.get("clause"),
            "verdict": res.ok, "limit_name": lk, "limit": lv,
            "mandatory": res.mandatory}


def dual_code_report(ctx: dict, jur_a: str = "CN", jur_b: str = "EU", na_b: str = None) -> dict:
    """返回 {jur_a, jur_b, rows:[{concept, a:{...}, b:{...}, note}]}。"""
    ctx_a, ctx_b = dict(ctx), dict(ctx)
    if jur_a == "EU":
        ctx_a.update(resolve("EU", na=na_b).ndp)
    if jur_b == "EU":
        ctx_b.update(resolve("EU", na=na_b).ndp)
    by_a = {r.concept: check(r, ctx_a) for r in rules_for(jur_a) if r.concept}
    by_b = {r.concept: check(r, ctx_b) for r in rules_for(jur_b) if r.concept}
    rows = []
    for c in sorted(set(by_a) | set(by_b)):
        a, b = _side(by_a.get(c)), _side(by_b.get(c))
        if a is None and b is None:      # 两侧均不适用(如梁上下文里的柱规则)→跳过
            continue
        note = ""
        if a and b and a["limit"] is not None and b["limit"] is not None:
            if abs(a["limit"] - b["limit"]) < 1e-9:
                note = "两规范限值一致"
            else:
                gov = jur_a if a["limit"] > b["limit"] else jur_b     # 限值越严越控制(以下限类为例)
                note = f"限值不同（{jur_a}={a['limit']:.4g} vs {jur_b}={b['limit']:.4g}），{gov} 更严控制"
        elif a and not b:
            note = f"仅 {jur_a} 有对应条文"
        elif b and not a:
            note = f"仅 {jur_b} 有对应条文"
        rows.append({"concept": c, "a": a, "b": b, "note": note})
    return {"jur_a": jur_a, "jur_b": jur_b, "rows": rows}


def render_markdown(rep: dict) -> str:
    L = [f"# 双规范并行对照表　{rep['jur_a']} vs {rep['jur_b']}\n",
         f"| 校核概念 | {rep['jur_a']} 条文 | {rep['jur_a']} 判定/限值 | "
         f"{rep['jur_b']} 条文 | {rep['jur_b']} 判定/限值 | 差异说明 |",
         "|---|---|---|---|---|---|"]
    def cell(s):
        if not s:
            return "—", "—"
        v = "✔" if s["verdict"] else "✗"
        lim = f"{s['limit_name']}={s['limit']:.4g}" if s["limit"] is not None else "-"
        return s["clause"], f"{v} {lim}"
    for r in rep["rows"]:
        ac, av = cell(r["a"]); bc, bv = cell(r["b"])
        L.append(f"| {r['concept']} | {ac} | {av} | {bc} | {bv} | {r['note']} |")
    L.append("\n> 每套结论由各自规范独立算出；映射仅用于解释差异，不做换算。")
    return "\n".join(L)
