"""
可插拔分析引擎层。

闭环通过 Analyzer 接口调用任一引擎，互不感知：
  - InternalFrameAnalyzer ：内置 2D 杆系有限元（默认，离线可用）
  - EtabsAnalyzer         ：ETABS OAPI 适配器（重要工程，需 Windows+ETABS）
  - YjkAnalyzer           ：YJK 数据接口适配器
所有引擎消费 FrameSpec，返回 Dict[member_id, MemberForces]。
"""
from .base import Analyzer
from .internal import InternalFrameAnalyzer

__all__ = ["Analyzer", "InternalFrameAnalyzer"]
