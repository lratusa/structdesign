"""内置 2D 杆系有限元适配器（默认引擎，离线可用）。"""
from __future__ import annotations
from typing import Dict

from ..frame_spec import FrameSpec, MemberForces, build_model
from ..analysis.frame2d import solve


class InternalFrameAnalyzer:
    name = "内置2D杆系有限元"

    def analyze(self, spec: FrameSpec) -> Dict[str, MemberForces]:
        raw = solve(build_model(spec))
        out: Dict[str, MemberForces] = {}
        for mid, r in raw.items():
            out[mid] = MemberForces(Mi=r.Mi, Mj=r.Mj, M_mid=r.M_mid,
                                    Vi=r.Vi, Vj=r.Vj, N_axial=r.N_axial)
        return out
