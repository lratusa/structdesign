"""
YJK 适配器（骨架）。

YJK(盈建科)对外提供数据接口：模型与计算结果存于其工程数据库/接口文件
(如 .yjk / 文本接口 / YJK-API)。本适配器演示两种典型路径：
  (A) 接口文件交换：读取 YJK 导出的内力结果文件 → 映射 MemberForces；
  (B) YJK-API：若环境提供 API，直接调用其分析并取内力。
现阶段以 (A) 文件交换为主（最稳、对环境依赖最小）。
"""
from __future__ import annotations
from typing import Dict, Optional
import os

from ..frame_spec import FrameSpec, MemberForces


class YjkAnalyzer:
    name = "YJK (数据接口)"

    def __init__(self, result_file: Optional[str] = None):
        self.result_file = result_file

    def export_model(self, spec: FrameSpec, path: str):
        """把 FrameSpec 写成 YJK 可导入的中间格式（占位：实际按 YJK 接口规范）。"""
        raise NotImplementedError(
            "需按 YJK 模型接口规范生成导入文件（构件/截面/荷载/边界）。")

    def analyze(self, spec: FrameSpec) -> Dict[str, MemberForces]:
        """路径(A)：解析 YJK 导出的内力结果文件。"""
        if not self.result_file or not os.path.exists(self.result_file):
            raise RuntimeError(
                "未提供 YJK 内力结果文件。请在 YJK 中完成分析并导出内力，"
                "或改用 InternalFrameAnalyzer。")
        return self._parse_result_file(self.result_file)

    def _parse_result_file(self, path: str) -> Dict[str, MemberForces]:
        """解析内力文件 → MemberForces。格式按实际 YJK 导出调整。

        约定示例(每行)：member_id, Mi, Mj, M_mid, Vi, Vj, N(压正)
        """
        out: Dict[str, MemberForces] = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                p = [x.strip() for x in line.split(",")]
                mid = p[0]
                vals = [float(x) for x in p[1:7]]
                out[mid] = MemberForces(Mi=vals[0], Mj=vals[1], M_mid=vals[2],
                                        Vi=vals[3], Vj=vals[4], N_axial=vals[5])
        return out
