"""审查包 + 强条自查表（设计书 §8⑧ 送审 / §10 合规 / §15 强条漏检数=0）。

面向审查机构的证据链输出：把 SSM 送审快照(签名tag) + 生效规范集 + 全量条文扫描 +
**强制性条文自查表**(带条文溯源) 打包。强条不满足=红线。这是把"送审通过率"做成产品指标的抓手。
"""
from __future__ import annotations
from .bridge import heng_scan
from .codes.jurisdiction import resolve
from .ssm import ssm_from_project, SSMRepo


def mandatory_selfcheck(result, project, jurisdiction: str = "CN") -> dict:
    """强条自查表：逐条强制性条文的判定 + 溯源。all_pass/red_line。"""
    s = heng_scan(result, project, jurisdiction)
    rows = []
    for r in s["results"]:
        if r.mandatory:
            rows.append({
                "rule_id": r.rule_id, "clause": r.provenance.get("clause"),
                "title": r.title, "verdict": bool(r.ok),
                "text": r.provenance.get("text_zh", ""),
                "values": r.values,
            })
    return dict(rows=rows,
                all_pass=all(x["verdict"] for x in rows) if rows else True,
                red_line=s["red_line"], scan=s)


def review_package(result, project, jurisdiction: str = "CN", author: str = "") -> dict:
    """审查包：SSM 签名快照 + 规范集 + 扫描摘要 + 强条自查表。"""
    cs = resolve(jurisdiction, "building", "design")
    ssm = ssm_from_project(project, jurisdiction)
    repo = SSMRepo()
    cid = repo.commit(ssm, "送审快照", author or "unsigned")
    tag = repo.tag("送审", cid, signature=author or None)
    mand = mandatory_selfcheck(result, project, jurisdiction)
    return dict(
        jurisdiction=cs.jurisdiction, codes=cs.codes, review_process=cs.review_process,
        ssm_commit=tag, signed=bool(author), author=author,
        n_members=ssm["meta"]["n_members"],
        mandatory=mand, red_line=mand["red_line"],
        pass_for_submission=mand["all_pass"],       # 强条全过才可进送审包
    )


def render_markdown(pkg: dict) -> str:
    L = []
    L.append("# 送审审查包 · 强条自查表\n")
    L.append(f"- 辖区：**{pkg['jurisdiction']}**　审查流程：{pkg['review_process']}")
    L.append(f"- SSM 送审快照：`{pkg['ssm_commit']}`　签名：{pkg['author'] or '（未签名，不得进入送审包）'}")
    L.append(f"- 适用规范：{ '；'.join(pkg['codes']) }")
    L.append("")
    L.append("## 强制性条文自查（强条零容忍）\n")
    L.append("| 条文 | 内容 | 判定 |")
    L.append("|------|------|------|")
    for r in pkg["mandatory"]["rows"]:
        v = "✔ 满足" if r["verdict"] else "✗ **不满足(红线)**"
        L.append(f"| {r['clause']} | {r['title']} | {v} |")
    L.append("")
    if pkg["red_line"]:
        L.append("> ⚠ **存在强制性条文不满足（红线），不得送审。** 请修改后重出审查包。")
    elif pkg["pass_for_submission"]:
        L.append("> ✔ 强制性条文全部满足。" + ("已签名，可进入送审包。" if pkg["signed"]
                 else "尚未由注册工程师签名——AI 起草，待工程师确认后方可送审。"))
    L.append("")
    L.append("*本自查表由「衡」规范引擎(Code-as-Data)自动生成，每一判定可点击溯源至条文原文；"
             "最终设计责任由注册结构工程师承担。*")
    return "\n".join(L)
