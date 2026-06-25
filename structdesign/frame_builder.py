"""
规则框架生成器 —— 把"多层多跨"参数化生成 FrameSpec，喂给闭环。

内置有限元本就支持任意 2D 框架；本模块只是方便地生成规则框架（含重力均布 +
逐层水平力），证明闭环在整榀框架上可用、可收敛。
"""
from __future__ import annotations
from typing import Callable

from .analysis.frame2d import NodalLoad
from .frame_spec import SecBox, FrameSpec


def build_regular_frame(n_bays: int, n_stories: int,
                        bay_w: float, story_h: float,
                        col_sec: Callable[[], SecBox],
                        beam_sec: Callable[[], SecBox],
                        w_gravity: float,
                        lateral_per_floor: float,
                        wall_axes=None,
                        wall_sec: Callable[[], SecBox] = None) -> FrameSpec:
    """生成 n_bays 跨 × n_stories 层 的平面框架（可含剪力墙）。

    col_sec/beam_sec：返回**新** SecBox 的工厂（闭环会就地改 h，须各构件独立实例）。
    w_gravity：梁上重力均布 (N/mm)；lateral_per_floor：每层水平力 (N)。
    wall_axes：作为剪力墙的柱列索引集合（这些竖向构件用 wall_sec，等效宽柱模型，
              通过各层楼面梁与框架协同工作）；wall_sec：墙截面工厂(kind='wall')。
    节点编号 N{i}_{j}：i=0..n_bays 柱列，j=0..n_stories 层(0=基础)。
    """
    wall_axes = set(wall_axes or [])
    nodes = {}
    for i in range(n_bays + 1):
        for j in range(n_stories + 1):
            nid = f"N{i}_{j}"
            restraint = (True, True, True) if j == 0 else (False, False, False)
            nodes[nid] = (i * bay_w, j * story_h, restraint)

    members = {}
    # 柱/墙：每列每层
    for i in range(n_bays + 1):
        is_wall = i in wall_axes and wall_sec is not None
        for j in range(n_stories):
            mid = f"Z{i}_{j+1}"   # 第 j+1 层柱(墙)
            members[mid] = (f"N{i}_{j}", f"N{i}_{j+1}",
                            wall_sec() if is_wall else col_sec(), 0.0)
    # 梁：每层每跨
    for j in range(1, n_stories + 1):
        for i in range(n_bays):
            mid = f"L{i}_{j}"
            members[mid] = (f"N{i}_{j}", f"N{i+1}_{j}", beam_sec(), w_gravity)

    # 荷载：每层最左节点施加水平力（简化的层剪力输入）
    loads = []
    for j in range(1, n_stories + 1):
        loads.append(NodalLoad(f"N0_{j}", Fx=lateral_per_floor))

    return FrameSpec(nodes=nodes, members=members, loads=loads)
