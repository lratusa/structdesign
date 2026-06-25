"""分析引擎统一接口。"""
from __future__ import annotations
from typing import Protocol, Dict, runtime_checkable

from ..frame_spec import FrameSpec, MemberForces


@runtime_checkable
class Analyzer(Protocol):
    """任何分析引擎都须实现：消费 FrameSpec，返回各构件统一内力。

    实现适配器时的职责：
      1. 把 FrameSpec(中立模型) 翻译成该引擎的模型(几何/截面/荷载/边界)；
      2. 触发分析；
      3. 提取构件内力并映射回 MemberForces(统一单位 N, N·mm, 压为正)。
    """
    name: str

    def analyze(self, spec: FrameSpec) -> Dict[str, MemberForces]:
        ...
