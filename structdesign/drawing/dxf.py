"""
最小 DXF (R12 ASCII) 写出器 —— 零依赖，输出 AutoCAD/看图软件可打开的 .dxf。

支持 LINE / TEXT / CIRCLE 实体与图层。坐标单位 mm，y 轴向上(DXF 约定)。
足以承载平法配筋图；如需更复杂实体可后续接 ezdxf。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


def _pair(code, value):
    return f"{code}\n{value}\n"


@dataclass
class DXFDoc:
    entities: List[str] = field(default_factory=list)

    def add_line(self, x1, y1, x2, y2, layer="0"):
        e = "0\nLINE\n" + _pair(8, layer)
        e += _pair(10, f"{x1:.3f}") + _pair(20, f"{y1:.3f}") + _pair(30, "0.0")
        e += _pair(11, f"{x2:.3f}") + _pair(21, f"{y2:.3f}") + _pair(31, "0.0")
        self.entities.append(e)

    def add_text(self, x, y, text, height=2.5, layer="TEXT"):
        e = "0\nTEXT\n" + _pair(8, layer)
        e += _pair(10, f"{x:.3f}") + _pair(20, f"{y:.3f}") + _pair(30, "0.0")
        e += _pair(40, f"{height:.3f}") + _pair(1, text)
        self.entities.append(e)

    def add_circle(self, cx, cy, r, layer="0"):
        e = "0\nCIRCLE\n" + _pair(8, layer)
        e += _pair(10, f"{cx:.3f}") + _pair(20, f"{cy:.3f}") + _pair(30, "0.0")
        e += _pair(40, f"{r:.3f}")
        self.entities.append(e)

    def add_rect(self, x, y, w, h, layer="0"):
        self.add_line(x, y, x + w, y, layer)
        self.add_line(x + w, y, x + w, y + h, layer)
        self.add_line(x + w, y + h, x, y + h, layer)
        self.add_line(x, y + h, x, y, layer)

    def dumps(self) -> str:
        s = "0\nSECTION\n2\nHEADER\n0\nENDSEC\n"
        s += "0\nSECTION\n2\nENTITIES\n"
        s += "".join(self.entities)
        s += "0\nENDSEC\n0\nEOF\n"
        return s

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.dumps())
        return path
