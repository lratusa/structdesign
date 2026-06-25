"""
建筑模型约束层 —— 把"建筑给结构的可行域"显式建模。

这是本软件区别于 PKPM/YJK 的关键输入：建筑模型里一段墙线上，有结构墙肢
和可让位的填充墙。结构墙肢可以在建筑允许范围内"生长"（加长/加厚）来解决
轴压比等问题。本模块定义这个可行域，并提供读取接口。

读取来源：
  - 现阶段：from_dict / from_json（建筑专业导出的轻量约束表）
  - 后续：IFC / Revit 适配器 → 转换为这里的 WallEnvelope（接口已预留）
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json


@dataclass
class WallEnvelope:
    """一段墙线上的建筑可行域（单位 mm）。

    结构墙肢长度 lw 允许在 [lw_min, lw_max] 内变化；lw_max 由"这段墙线总长
    减去必须保留的洞口/通道"决定，即填充墙可让位出来的最大长度。
    厚度 bw 可在 thickness_options 中选择（建筑常限定墙厚）。
    """
    wall_id: str
    axis: str = ""                 # 轴线标识，如 "1/A-C"
    lw_min: float = 200.0          # 墙肢最小长度
    lw_max: float = 2000.0         # 墙肢最大可生长长度（填充墙让位上限）
    thickness_options: List[float] = field(default_factory=lambda: [200.0])
    fixed_thickness: Optional[float] = None  # 若建筑锁定墙厚
    note: str = ""

    def thickness_choices(self) -> List[float]:
        if self.fixed_thickness is not None:
            return [self.fixed_thickness]
        return sorted(self.thickness_options)

    def clamp_length(self, lw: float) -> float:
        return max(self.lw_min, min(lw, self.lw_max))

    def feasible(self, lw: float, bw: float) -> bool:
        return self.lw_min <= lw <= self.lw_max + 1e-6 and bw in self.thickness_choices()


@dataclass
class ArchModel:
    """建筑模型约束集合。"""
    project: str = ""
    walls: Dict[str, WallEnvelope] = field(default_factory=dict)

    def add_wall(self, w: WallEnvelope) -> "ArchModel":
        self.walls[w.wall_id] = w
        return self

    def envelope(self, wall_id: str) -> WallEnvelope:
        if wall_id not in self.walls:
            raise KeyError(f"建筑模型中无墙 {wall_id}")
        return self.walls[wall_id]

    @staticmethod
    def from_dict(d: dict) -> "ArchModel":
        m = ArchModel(project=d.get("project", ""))
        for w in d.get("walls", []):
            m.add_wall(WallEnvelope(
                wall_id=w["wall_id"],
                axis=w.get("axis", ""),
                lw_min=float(w.get("lw_min", 200)),
                lw_max=float(w.get("lw_max", 2000)),
                thickness_options=[float(x) for x in w.get("thickness_options", [200])],
                fixed_thickness=(float(w["fixed_thickness"]) if w.get("fixed_thickness") is not None else None),
                note=w.get("note", ""),
            ))
        return m

    @staticmethod
    def from_json(path: str) -> "ArchModel":
        with open(path, "r", encoding="utf-8") as f:
            return ArchModel.from_dict(json.load(f))


# --- 适配器占位：未来从 BIM 读取并转换为 ArchModel ---
def from_ifc(path: str) -> ArchModel:
    raise NotImplementedError(
        "IFC 适配器待实现：解析 IfcWall/IfcWallStandardCase 几何与墙线，"
        "区分结构墙与填充墙，生成 WallEnvelope。当前请用 from_dict/from_json。")
