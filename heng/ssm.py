"""L1 单一结构语义模型(SSM) + Git 式版本化（设计书 §3.2）。

SSM 是平台"宪法"：构件/材料/荷载/组合/设计假定/规范上下文 以带类型对象存储；
分析网格、施工图、计算书都是 SSM 的**投影**。SSM 采用 Git 式版本化：
- commit：每次修改一个内容寻址快照；branch：方案比选；tag：送审版本(可签名)。
- diff：两版本自动生成**修改对照表**(审图/適合性判定回复的最耗时杂活)。
- 全量审计日志(满足终身责任追溯)。

内容寻址用快照 canonical-json 的哈希（确定性，不依赖时间戳）。
"""
from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(snapshot, parent, message, author) -> str:
    return "c" + hashlib.sha1(_canon([snapshot, parent, message, author]).encode("utf-8")).hexdigest()[:12]


@dataclass
class Commit:
    id: str
    parent: Optional[str]
    message: str
    author: str
    snapshot: dict
    tag: Optional[str] = None
    signature: Optional[str] = None


class SSMRepo:
    """SSM 版本库(内存)。快照=普通 dict(语义对象)。"""

    def __init__(self):
        self.commits: Dict[str, Commit] = {}
        self.branches: Dict[str, Optional[str]] = {"main": None}
        self.tags: Dict[str, str] = {}
        self.head = "main"
        self.audit: List[tuple] = []

    def commit(self, ssm: dict, message: str, author: str, branch: str = None) -> str:
        br = branch or self.head
        if br not in self.branches:
            self.branches[br] = None
        parent = self.branches[br]
        snap = copy.deepcopy(ssm)
        cid = _hash(snap, parent, message, author)
        self.commits[cid] = Commit(cid, parent, message, author, snap)
        self.branches[br] = cid
        self.audit.append(("commit", cid, br, author, message))
        return cid

    def branch(self, name: str, frm: str = None):
        self.branches[name] = self._resolve(frm) if frm else self.branches[self.head]
        self.audit.append(("branch", name, self.branches[name]))
        return name

    def tag(self, name: str, ref: str = None, signature: str = None) -> str:
        cid = self._resolve(ref) if ref else self.branches[self.head]
        self.commits[cid].tag = name
        self.commits[cid].signature = signature
        self.tags[name] = cid
        self.audit.append(("tag", name, cid, signature))
        return cid

    def checkout(self, ref: str) -> dict:
        return copy.deepcopy(self.commits[self._resolve(ref)].snapshot)

    def log(self, branch: str = None) -> List[Commit]:
        cid = self.branches.get(branch or self.head)
        out = []
        while cid:
            c = self.commits[cid]; out.append(c); cid = c.parent
        return out

    def diff(self, ref_a: str, ref_b: str) -> dict:
        """两版本的**修改对照表**：按语义对象逐个 added/removed/modified(字段级 old→new)。"""
        a = self.commits[self._resolve(ref_a)].snapshot
        b = self.commits[self._resolve(ref_b)].snapshot
        return _diff_ssm(a, b)

    def _resolve(self, ref: str) -> str:
        if ref in self.branches and self.branches[ref]:
            return self.branches[ref]
        if ref in self.tags:
            return self.tags[ref]
        return ref


def _diff_dict(a: dict, b: dict) -> dict:
    """两个 {id:obj} 集合的差异。"""
    out = {"added": [], "removed": [], "modified": []}
    for k in b:
        if k not in a:
            out["added"].append(k)
        elif a[k] != b[k]:
            fields = {}
            for f in set(list(a[k].keys()) + list(b[k].keys())):
                if a[k].get(f) != b[k].get(f):
                    fields[f] = [a[k].get(f), b[k].get(f)]
            out["modified"].append({"id": k, "fields": fields})
    for k in a:
        if k not in b:
            out["removed"].append(k)
    return out


def _diff_ssm(a: dict, b: dict) -> dict:
    return {sec: _diff_dict(a.get(sec, {}), b.get(sec, {}))
            for sec in ("members", "materials", "loads")}


# ---------------- Project → SSM 投影（现有模型是 SSM 的一个投影） ----------------

def ssm_from_project(project, jurisdiction: str = "CN") -> dict:
    """把 modeler.Project 投影为 SSM 语义快照(用于版本化/多国规范上下文)。"""
    fl = project.floor
    members = {}
    for i, c in enumerate(fl.columns):
        members[f"KZ{i}"] = {"type": "column", "b": c.b, "h": c.h,
                             "x": round(c.x), "y": round(c.y), "material": c.mat}
    for i, b in enumerate(fl.beams):
        members[f"KL{i}"] = {"type": "beam", "b": b.b, "h": b.h,
                             "x1": round(b.x1), "y1": round(b.y1),
                             "x2": round(b.x2), "y2": round(b.y2), "material": b.mat}
    for i, w in enumerate(fl.walls):
        members[f"Q{i}"] = {"type": "wall", "t": w.t,
                            "x1": round(w.x1), "y1": round(w.y1),
                            "x2": round(w.x2), "y2": round(w.y2), "material": w.mat}
    s = project.seismic
    return {
        "members": members,
        "materials": {"concrete": {"grade": "C40"}, "rebar": {"grade": "HRB400"}},
        "loads": {"slab_dead": {"kind": "dead", "value": fl.slab.dead},
                  "slab_live": {"kind": "live", "value": fl.slab.live}},
        "design_context": {"jurisdiction": jurisdiction,
                           "seismic": {"alpha_max": s.alpha_max, "Tg": s.Tg, "grade": s.grade},
                           "storeys": project.total_floors()},
        "meta": {"n_members": len(members)},
    }
