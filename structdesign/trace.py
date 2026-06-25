"""
追溯记录 — 实现“凡决策必留痕”。

每一步计算产生一条 TraceStep：用了哪条规范、什么方法、表达式、代入值与结果。
设计内核把这些步骤累积起来，计算书层据此渲染，使每个数字都可回链到依据。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Basis(str, Enum):
    """求解依据类型 —— 对应方法论优先级。"""
    CODE_FORMULA = "规范公式"      # 首选
    FEM = "有限元"                 # 规范无公式处
    ENGINEERING = "工程方法"        # 有依据的工程实用方法
    CONSTRUCTION = "构造规定"       # 构造措施类规范条款


@dataclass
class TraceStep:
    title: str                      # 这一步算什么
    clause: str                     # 规范条文号 / 方法出处
    basis: Basis = Basis.CODE_FORMULA
    expression: str = ""            # 公式（符号）
    substitution: str = ""          # 代入数值
    result: str = ""                # 结果（带单位）
    note: str = ""                  # 备注 / 结论

    def render(self) -> str:
        lines = [f"**{self.title}**　_[{self.basis.value} · {self.clause}]_"]
        if self.expression:
            lines.append(f"  公式: {self.expression}")
        if self.substitution:
            lines.append(f"  代入: {self.substitution}")
        if self.result:
            lines.append(f"  结果: {self.result}")
        if self.note:
            lines.append(f"  说明: {self.note}")
        return "\n".join(lines)


@dataclass
class TraceLog:
    steps: List[TraceStep] = field(default_factory=list)

    def add(self, step: TraceStep) -> TraceStep:
        self.steps.append(step)
        return step

    def step(self, **kwargs) -> TraceStep:
        return self.add(TraceStep(**kwargs))

    def render(self) -> str:
        return "\n\n".join(s.render() for s in self.steps)
