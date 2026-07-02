"""计算书「规范校核」章节 —— 每个判定带条文锚点(rule_id + 原文)（设计书 §8⑦ 依据链）。

把规范引擎的整体指标 + 构件级校核渲染为可追加进计算书的 markdown。这是玻璃盒
"点击任何数字→依据链"的文本载体：每一条判定都标注 rule_id、条文号、条文原文、中间量。
"""
from __future__ import annotations
from .bridge import heng_scan, member_scan
from .review import mandatory_selfcheck


def _v(ok):
    return "✔ 满足" if ok else "✗ **不满足**"


def compliance_section(result, project, jurisdiction: str = "CN") -> str:
    s = heng_scan(result, project, jurisdiction)
    ms = member_scan(result, project, jurisdiction)
    mand = mandatory_selfcheck(result, project, jurisdiction)
    L = []
    L.append("## 规范校核（「衡」规范引擎 · Code-as-Data · 逐条溯源）\n")
    L.append(f"辖区 **{jurisdiction}**；共扫描适用条文 {s['total']} 条，"
             f"通过 {s['passed']}，不满足 {s['failed']}"
             + ("，**含强条不满足（红线）**" if s["red_line"] else "，强条全部满足") + "。\n")

    # 整体指标
    L.append("### 整体指标\n")
    L.append("| 指标 | 判定 | 依据(rule_id / 条文) | 条文原文 |")
    L.append("|------|------|----------------------|----------|")
    for r in s["results"]:
        mand_tag = "【强条】" if r.mandatory else ""
        txt = (r.provenance.get("text_zh", "") or "")[:40]
        L.append(f"| {mand_tag}{r.title} | {_v(r.ok)} | `{r.rule_id}`（{r.provenance.get('clause','')}） | {txt}… |")
    L.append("")

    # 构件级
    L.append("### 构件级配筋校核\n")
    L.append(f"共校核构件 {len(ms['members'])} 个，构件级条文判定 {ms['n_checks']} 次，"
             f"不满足构件 {len(ms['failed'])} 个。")
    if ms["failed"]:
        L.append("\n不满足构件（可溯源到具体条文，并标注控制条文）：\n")
        L.append("| 构件 | 截面 | 违反条文 | 控制条文(哪条卡住它) |")
        L.append("|------|------|----------|----------------------|")
        for m in ms["failed"][:20]:
            bad = [f"`{x.rule_id}`（{x.provenance.get('clause','')}）" for x in m["results"] if not x.ok]
            g = m.get("governing")
            gov = (f"{g['title']}（{g['clause']}，利用率 {g['criticality']*100:.0f}%）"
                   if g else "—")
            L.append(f"| {m['id']} | {m.get('sec','')} | {'；'.join(bad)} | {gov} |")
    L.append("")

    # 强条自查
    L.append("### 强制性条文自查（强条零容忍）\n")
    L.append("| 条文 | 内容 | 判定 |")
    L.append("|------|------|------|")
    for row in mand["rows"]:
        L.append(f"| {row['clause']} | {row['title']} | {_v(row['verdict'])} |")
    if mand["red_line"]:
        L.append("\n> ⚠ 存在强制性条文不满足（红线），**不得送审**。")
    L.append("")
    L.append("*本章由规范引擎自动生成，每条判定可溯源至条文原文与计算中间量；"
             "最终设计责任由注册结构工程师承担。*")
    return "\n".join(L)
