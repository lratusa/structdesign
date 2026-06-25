"""
钢筋表 / 材料表 —— 统计规格、根数、长度、重量与总用钢。

钢筋理论重量: m = ρ·A = 7850 · (π/4·d²)·1e-9 ·1e3 = 0.006165·d² (kg/m)。
（校验: D20→2.466, D25→3.853, D8→0.395，与规范钢筋理论重量表一致。）
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import math


def bar_mass_per_m(d: float) -> float:
    """单位长度理论重量 kg/m。m=ρ·A=7850·(π/4·d²·1e-6) = 0.0061654·d²。"""
    return 7850.0 * (math.pi / 4.0 * d * d * 1e-6)


def _mass(d):
    return bar_mass_per_m(d)


@dataclass
class ScheduleRow:
    mark: str          # 钢筋编号/构件
    grade: str         # 牌号
    d: float           # 直径
    count: int         # 根数
    length_mm: float   # 单根长度
    @property
    def total_length_m(self):
        return self.count * self.length_mm / 1000.0
    @property
    def mass_kg(self):
        return self.total_length_m * _mass(self.d)


@dataclass
class Schedule:
    rows: List[ScheduleRow] = field(default_factory=list)

    def add(self, mark, grade, d, count, length_mm):
        self.rows.append(ScheduleRow(mark, grade, d, count, length_mm))

    @property
    def total_mass_kg(self):
        return sum(r.mass_kg for r in self.rows)

    def mass_by_diameter(self) -> Dict[float, float]:
        out: Dict[float, float] = {}
        for r in self.rows:
            out[r.d] = out.get(r.d, 0.0) + r.mass_kg
        return out

    def render_markdown(self) -> str:
        L = ["| 编号 | 牌号 | 直径 | 根数 | 单长(mm) | 总长(m) | 重量(kg) |",
             "|---|---|---|---|---|---|---|"]
        for r in self.rows:
            L.append(f"| {r.mark} | {r.grade} | D{int(r.d)} | {r.count} | "
                     f"{r.length_mm:.0f} | {r.total_length_m:.1f} | {r.mass_kg:.1f} |")
        L.append(f"| **合计** | | | | | | **{self.total_mass_kg:.1f}** |")
        return "\n".join(L)
