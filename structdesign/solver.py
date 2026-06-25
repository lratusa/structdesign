"""
闭环调度器骨架（L6）—— 把"分析→配筋→验算→调整"串成自动循环。

设计要点（对应问题域地图 §0 双层迭代）：
  - 内层（截面固定）：内力不变，配筋确定性收敛 —— 已由各 design_* 内核实现。
  - 外层（截面变化）：改截面→需重新分析→内力重分布。这一步需要一个分析引擎。
    本软件不自研全局 FEM：通过 Analyzer 接口对接外部引擎(ETABS/YJK/...)。
    此处给出接口与一个 TrivialAnalyzer(固定内力)，使固定截面闭环可端到端运行；
    截面生长的外层重分析留待接入真实 Analyzer（适配器）。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, Dict, Callable, Any, List


class Analyzer(Protocol):
    """分析引擎接口。真实实现由适配器提供（ETABS OAPI / YJK 等）。"""
    def analyze(self, model: Any) -> Dict[str, Any]:
        """对给定模型(含截面)做分析，返回各构件内力。"""
        ...


@dataclass
class TrivialAnalyzer:
    """占位分析器：内力与截面无关（固定内力）。仅用于固定截面闭环演示。"""
    forces: Dict[str, Any] = field(default_factory=dict)

    def analyze(self, model: Any) -> Dict[str, Any]:
        return self.forces


@dataclass
class IterationReport:
    converged: bool
    iterations: int
    history: List[str] = field(default_factory=list)


def closed_loop(model: Any, analyzer: Analyzer,
                design_fn: Callable[[Any, Dict[str, Any]], Dict[str, Any]],
                adjust_fn: Callable[[Any, Dict[str, Any]], bool],
                max_iter: int = 20, damping: float = 0.5) -> IterationReport:
    """通用闭环：分析→配筋/验算→（不满足则）调整截面→重分析。

    design_fn(model, forces) -> 设计结果(含 ok 标志与超限信息)
    adjust_fn(model, design_result) -> 是否对模型做了截面调整(True=改了,需重算)
    返回是否收敛。外层是否真正"重分布"取决于 analyzer 是否对截面敏感。
    """
    rep = IterationReport(converged=False, iterations=0)
    for it in range(1, max_iter + 1):
        rep.iterations = it
        forces = analyzer.analyze(model)
        result = design_fn(model, forces)
        ok = result.get("ok", True)
        if ok:
            rep.converged = True
            rep.history.append(f"第{it}轮：全部满足，收敛")
            break
        changed = adjust_fn(model, result)
        rep.history.append(f"第{it}轮：存在超限 → {'调整截面后重算' if changed else '无可调整空间，停止'}")
        if not changed:
            break
    return rep
