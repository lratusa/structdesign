"""规范知识图谱：条文引用关系 → 展开完整依据链（设计书 §4.3 第二级）。

"知识图谱维护条文间的引用关系(50010 引用 50009 的组合、示方書引用 JIS 材料标准)，
用于展开完整的依据链。" 本模块把这一关系做成可查询、可回归的有向图：

  给一条规则 → 递归展开它所依据/引用的上游条文，得到**完整依据链**(玻璃盒可溯源到根)。

引用节点分两类：注册表内的可执行规则(rule_id 可 check)、以及外部规范/条文(荷载组合、材料标准等叶节点)。
"""
from __future__ import annotations
from .codes.registry import REGISTRY

# rule_id / 条文节点 → [{"ref": 上游节点, "relation": 关系}]
# relation：依据(计算前提)、引用(直接调用其条款)、组合(荷载/工况组合来源)
REFERENCES = {
    "CN.GB50011-2010(2016).5.2.5": [       # 剪重比
        {"ref": "CN.GB50011-2010(2016).地震作用", "relation": "依据"},
        {"ref": "GB 50009-2012 §3(荷载组合)", "relation": "组合"},
    ],
    "CN.GB50011-2010(2016).5.5.1": [       # 层间位移角
        {"ref": "CN.GB50011-2010(2016).地震作用", "relation": "依据"},
    ],
    "CN.GB50011-2010(2016).地震作用": [     # 中间节点：地震作用计算(反应谱)
        {"ref": "GB 50011-2010 §5.1(地震影响系数)", "relation": "引用"},
        {"ref": "GB 50009-2012 §3(荷载组合)", "relation": "组合"},
    ],
    "CN.GB50010-2010(2015).8.5.1": [       # 最小配筋率
        {"ref": "GB 50010-2010 §4.1(混凝土材料 ft)", "relation": "引用"},
        {"ref": "GB 50010-2010 §4.2(钢筋材料 fy)", "relation": "引用"},
    ],
    "CN.GB50010-2010(2015).6.3.1": [       # 剪压比
        {"ref": "GB 50010-2010 §4.1(混凝土 fc)", "relation": "引用"},
    ],
    "US.ASCE7-22.12.12.1": [               # 容许层间位移角
        {"ref": "ASCE 7-22 §12.8(等效侧力法)", "relation": "依据"},
    ],
    "EU.EN1998-1.4.4.3.2": [               # 损伤极限位移
        {"ref": "EN 1990 §6.4(极限状态)", "relation": "依据"},
    ],
}


def is_executable(node: str) -> bool:
    """该节点是否为注册表内可执行规则(可 check)。"""
    return node in REGISTRY


def dependency_chain(rule_id: str, _seen=None) -> dict:
    """递归展开依据链，返回树 {node, executable, children:[{relation, ...}]}。防环。"""
    _seen = _seen or set()
    node = {"node": rule_id, "executable": is_executable(rule_id), "children": []}
    if rule_id in _seen:
        node["cycle"] = True
        return node
    _seen = _seen | {rule_id}
    for ref in REFERENCES.get(rule_id, []):
        child = dependency_chain(ref["ref"], _seen)
        child["relation"] = ref["relation"]
        node["children"].append(child)
    return node


def flatten(chain: dict) -> list:
    """依据链展平为节点列表(去重、深度优先)。"""
    out, seen = [], set()
    def _walk(n):
        if n["node"] not in seen:
            seen.add(n["node"]); out.append(n["node"])
        for c in n["children"]:
            _walk(c)
    _walk(chain)
    return out


def validate() -> dict:
    """图完整性：引用到的注册表 rule_id 必须真实存在(无悬空)；报告叶/中间节点数。"""
    dangling, internal_refs, external = [], 0, 0
    for src, refs in REFERENCES.items():
        for r in refs:
            t = r["ref"]
            if t in REGISTRY:                       # 注册表内可执行规则
                internal_refs += 1
            elif t.startswith(("CN.", "EU.", "JP.", "US.")) and t not in REFERENCES:
                dangling.append(t)                  # 形似 rule_id 但既非注册表规则也非中间节点 → 悬空
            else:
                external += 1                       # 外部规范/条文叶节点(如 GB 50009 §3)
    return {"dangling": dangling, "internal_refs": internal_refs,
            "external_leaves": external, "ok": not dangling}


def render_markdown(rule_id: str) -> str:
    chain = dependency_chain(rule_id)
    L = [f"# 依据链　{rule_id}\n"]
    def _walk(n, depth):
        tag = ("⚙可执行" if n["executable"]
               else "↗派生依据" if n["children"] else "📎外部条文")
        rel = f"（{n.get('relation')}）" if n.get("relation") else ""
        L.append("　" * depth + f"- {n['node']} {rel}[{tag}]" + ("　⟲环" if n.get("cycle") else ""))
        for c in n["children"]:
            _walk(c, depth + 1)
    _walk(chain, 0)
    L.append("\n*依据链由规范知识图谱展开，玻璃盒可溯源至根条文；外部规范为叶节点(引用而不换算)。*")
    return "\n".join(L)
