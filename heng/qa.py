"""条文级规范问答（设计书 §4.3 第二级 RAG + §6.1 玻璃盒）。

在规则库(rule_id/title/条文原文/条号)上检索，返回答案**必附**条文号、原文、版本、是否强条。
硬约束：**无出处不作答**——检索不到适用条文时明确回答"未检索到适用条文"，禁止生成式补全条文内容。

本版为确定性关键词检索(可离线、可审计)；向量化/LLM 重排为后续增强，但"附出处"这一玻璃盒约束不变。
"""
from __future__ import annotations
import re
from .codes.registry import all_rules


_STOP = {"", "the", "a", "of", "in", "to", "is"}


def _terms(text: str):
    """中文用 2-gram(避免单字噪声) + 英文词 + 条号(如 5.5.1)。"""
    out = []
    for m in re.finditer(r"[A-Za-z]+|\d+(?:\.\d+)+|\d+|[一-鿿]+", text or ""):
        s = m.group()
        if re.fullmatch(r"[一-鿿]+", s):
            if len(s) == 1:
                out.append(s)
            else:
                out += [s[i:i + 2] for i in range(len(s) - 1)]   # bigrams
        else:
            out.append(s.lower())
    return [t for t in out if t not in _STOP]


def _score(q_terms, rule) -> float:
    hay = " ".join([rule.rule_id, rule.title, rule.provenance.get("text_zh", "")])
    hset = set(_terms(hay))
    clause = str(rule.provenance.get("clause", ""))
    s = 0.0
    for t in set(q_terms):
        if t in hset:
            s += 2.0
        if t == clause:            # 条号直接命中
            s += 6.0
    return s


def ask(question: str, jurisdiction: str = None, top: int = 3) -> dict:
    """返回 {answered, hits:[{rule_id,clause,version,mandatory,text,title,score}], note}。"""
    q = _terms(question)
    scored = []
    for r in all_rules():
        if jurisdiction and r.jurisdiction != jurisdiction:
            continue
        sc = _score(q, r)
        if sc > 0:
            scored.append((sc, r))
    scored.sort(key=lambda t: -t[0])
    hits = []
    for sc, r in scored[:top]:
        hits.append({
            "rule_id": r.rule_id, "clause": r.provenance.get("clause"),
            "version": r.rule_id.split(".")[1] if "." in r.rule_id else "",
            "mandatory": r.mandatory, "title": r.title,
            "text": r.provenance.get("text_zh", ""), "score": round(sc, 1),
        })
    if not hits:
        # 硬约束：无出处不作答
        return dict(answered=False, hits=[],
                    note="未检索到适用条文。请补充条件或换用关键词；本平台不生成无出处的条文内容。")
    return dict(answered=True, hits=hits,
                note="以下答案均附条文出处；最终判定以确定性规范引擎为准，工程师负责确认。")


def format_answer(res: dict) -> str:
    if not res["answered"]:
        return res["note"]
    L = []
    for h in res["hits"]:
        mand = "【强条】" if h["mandatory"] else ""
        L.append(f"{mand}{h['rule_id']}（{h['clause']}）{h['title']}\n    原文：{h['text']}")
    return "\n".join(L) + "\n\n" + res["note"]
