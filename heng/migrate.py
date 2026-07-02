"""模型迁移器 + 迁移诊断报告（设计书 §9 第一步：替换落地路径）。

把外部结构模型(PKPM/YJK/ETABS/STAAD/IFC…导出的通用结构对象)导入为 SSM，并生成
**迁移诊断报告**：哪些对象完整映射、哪些语义有损、哪些需人工补充。
不承诺 100% 无损，承诺 100% 透明。

本版实现通用中间格式(dict)导入器 + 诊断框架；各商业格式的原生解析器为 Phase 2。
"""
from __future__ import annotations

# 外部构件类型 → SSM 语义类型 的映射（可扩展）
_TYPE_MAP = {
    "column": "column", "col": "column", "COLUMN": "column", "柱": "column",
    "beam": "beam", "girder": "beam", "梁": "beam",
    "wall": "wall", "shearwall": "wall", "墙": "wall",
    "slab": "slab", "floor": "slab", "板": "slab",
    "brace": "brace", "支撑": "brace",           # 已知但当前 SSM 未建模 → 语义有损
}
# 迁移时可能丢失的语义(记入诊断)
_LOSSY_TYPES = {"brace", "damper", "isolator", "link", "tendon"}


def import_model(external: dict, source: str = "generic") -> tuple:
    """external: {members:[{id,type,...}], materials:{...}, loads:{...}} → (ssm, report)。"""
    members = {}
    mapped, lossy, manual = [], [], []
    for m in external.get("members", []):
        et = str(m.get("type", "")).strip()
        st = _TYPE_MAP.get(et) or (et if et in _LOSSY_TYPES else None)   # 已知但未完整建模→识别为有损
        mid = m.get("id") or f"M{len(members)}"
        if st is None:
            manual.append({"id": mid, "type": et, "reason": "未识别的构件类型，需人工确认"})
            continue
        if et in _LOSSY_TYPES:
            lossy.append({"id": mid, "type": et, "mapped_to": st,
                          "reason": f"{st} 语义在当前 SSM 未完整建模，几何保留、属性有损"})
        obj = {"type": st}
        for k in ("b", "h", "t", "x", "y", "x1", "y1", "x2", "y2", "material"):
            if k in m:
                obj[k] = m[k]
        # 记录未迁移字段(有损)
        extra = [k for k in m if k not in ("id", "type", "b", "h", "t",
                                           "x", "y", "x1", "y1", "x2", "y2", "material")]
        if extra:
            lossy.append({"id": mid, "type": et, "mapped_to": st,
                          "reason": f"字段未映射: {', '.join(extra)}"})
        members[mid] = obj
        mapped.append(mid)
    ssm = {
        "members": members,
        "materials": external.get("materials", {}),
        "loads": external.get("loads", {}),
        "design_context": {"jurisdiction": external.get("jurisdiction", "CN"),
                           "imported_from": source},
        "meta": {"n_members": len(members), "source": source},
    }
    total = len(external.get("members", []))
    report = {
        "source": source, "total": total,
        "mapped": mapped, "lossy": lossy, "manual": manual,
        "coverage": round(len(mapped) / total, 3) if total else 1.0,
        "clean": (not lossy and not manual),
    }
    return ssm, report


def render_report(report: dict) -> str:
    L = [f"# 迁移诊断报告　源：{report['source']}\n",
         f"- 构件总数 {report['total']}，完整映射 {len(report['mapped'])}，"
         f"语义有损 {len(report['lossy'])}，需人工补充 {len(report['manual'])}",
         f"- 映射覆盖率 **{report['coverage']*100:.1f}%**"
         + ("（100% 无损）" if report["clean"] else "（存在有损/待补，见下）"), ""]
    if report["lossy"]:
        L.append("## 语义有损（几何保留，属性需复核）")
        for x in report["lossy"]:
            L.append(f"- `{x['id']}`（{x['type']}→{x['mapped_to']}）：{x['reason']}")
        L.append("")
    if report["manual"]:
        L.append("## 需人工补充（未识别）")
        for x in report["manual"]:
            L.append(f"- `{x['id']}`（{x['type']}）：{x['reason']}")
        L.append("")
    L.append("> 迁移不承诺 100% 无损，承诺 100% 透明。有损/待补项须工程师逐项确认后方可用于计算。")
    return "\n".join(L)
