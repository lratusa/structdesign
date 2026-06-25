"""
钢筋归并 —— 把多构件的离散配筋合并成有限规格（经济 + 易施工）。

问题域④"算得过≠建得出"的一环：若每根构件规格都不同，无法施工也不经济。
归并原则：每个构件实配 As ≥ 其需求；在满足前提下尽量减少规格种类。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .. import rebar as rb


@dataclass
class GroupAssignment:
    member_to_label: Dict[str, str] = field(default_factory=dict)
    member_to_As: Dict[str, float] = field(default_factory=dict)
    kinds: List[str] = field(default_factory=list)
    total_steel_area: float = 0.0     # Σ 实配 As（不含长度，仅面积代表用量倾向）
    total_required: float = 0.0
    waste_ratio: float = 0.0


def group_rebar(req: Dict[str, float], b: float = 300.0,
                max_kinds: Optional[int] = None) -> GroupAssignment:
    """req: 构件名 → 需求 As(mm²)。max_kinds: 限制规格种类数(None=不限)。

    步骤：① 各构件独立选筋；② 若规格数超过 max_kinds，从最小规格起，
    把其成员升配到下一更大规格，直至规格数达标。每个构件始终 As≥需求。
    """
    # ① 各自选筋
    choice: Dict[str, rb.BarChoice] = {}
    for name, As in req.items():
        choice[name] = rb.select_bars(As, b)

    # 规格按实配面积排序
    def label_of(c): return c.label()

    # ② 归并
    if max_kinds is not None:
        # 当前不同规格集合（按 As 升序）
        def distinct_sorted():
            seen = {}
            for c in choice.values():
                seen[c.label()] = c.As
            return sorted(seen.items(), key=lambda kv: kv[1])  # [(label, As)]

        guard = 0
        while True:
            ds = distinct_sorted()
            if len(ds) <= max_kinds or len(ds) <= 1:
                break
            guard += 1
            if guard > 200:
                break
            smallest_label, smallest_As = ds[0]
            # 下一更大规格
            target_label, target_As = ds[1]
            # 找到该更大规格对应的 BarChoice（任取一个该 label 的构件）
            target_choice = next(c for c in choice.values() if c.label() == target_label)
            # 把所有最小规格成员升配到 target
            for name, c in list(choice.items()):
                if c.label() == smallest_label:
                    choice[name] = target_choice

    # 汇总
    ga = GroupAssignment()
    kinds = []
    for name in req:
        c = choice[name]
        ga.member_to_label[name] = c.label()
        ga.member_to_As[name] = c.As
        ga.total_steel_area += c.As
        ga.total_required += req[name]
        if c.label() not in kinds:
            kinds.append(c.label())
    ga.kinds = kinds
    ga.waste_ratio = (ga.total_steel_area - ga.total_required) / ga.total_required if ga.total_required else 0.0
    # 校验：每个构件 As≥需求
    for name, As in req.items():
        assert ga.member_to_As[name] >= As - 1e-6, (name, As, ga.member_to_As[name])
    return ga
