"""
地下室专项（阶段5.5）—— 外墙水土压力受弯 + 抗浮校核。

定位说明：上部结构与地下室必须一体化。本模块处理地下室特有荷载与验算。
  - 外墙侧压力：静止土压力 K0·γs·z + 水压力 γw·z + 地面活载 K0·q。
  - 外墙按竖向单向板（上下支承于顶板/底板）受弯，取 1m 板带配筋（复用梁受弯内核）。
  - 抗浮：浮力 vs 结构自重+压重，安全系数 Kf。
方法标注：侧压力为土力学经典公式（工程方法/规范荷载）；受弯走规范公式；
弯矩采用简化支承模型（标注为工程方法）。
"""
from __future__ import annotations
from dataclasses import dataclass, field

from ..trace import TraceLog, Basis
from . import gb50010_beam as gb

# 三角形分布荷载简支梁最大弯矩系数 ≈ 1/(9√3)
TRI_COEF = 1.0 / (9.0 * (3.0 ** 0.5))   # ≈0.06415


@dataclass
class BasementWallResult:
    H: float
    M_design: float            # 设计弯矩 (kN·m/m)
    components: dict
    flexure: object            # FlexureResult (1m 板带)
    As_req: float
    log: TraceLog = field(default_factory=TraceLog)


def basement_wall_moment(H, soil_unit_weight=18.0, water_height=None,
                         surcharge=10.0, K0=0.5, gamma_w=10.0,
                         gG=1.3, gQ=1.5):
    """计算地下室外墙竖向板带设计弯矩 (kN·m/m)。

    H: 外墙计算跨度(支承间高度, m)；water_height: 水头高度(m)，默认=H(水位至地面)。
    简支板带，土压/水压为三角形，活载侧压为矩形。peak 叠加(略偏保守)。
    """
    if water_height is None:
        water_height = H
    # 底部峰值压力 (kN/m²)
    w_soil = K0 * soil_unit_weight * H
    w_water = gamma_w * water_height
    w_surch = K0 * surcharge
    # 各自简支跨中弯矩 (kN·m/m)，三角形用 TRI_COEF，矩形用 1/8
    M_soil = TRI_COEF * w_soil * H ** 2
    M_water = TRI_COEF * w_water * H ** 2
    M_surch = w_surch * H ** 2 / 8.0
    # 分项系数：土/水为永久作用 gG，活载侧压为可变 gQ
    M_design = gG * (M_soil + M_water) + gQ * M_surch
    comp = {
        "w_soil_kPa": w_soil, "w_water_kPa": w_water, "w_surch_kPa": w_surch,
        "M_soil": M_soil, "M_water": M_water, "M_surch": M_surch,
        "M_design": M_design,
    }
    return M_design, comp


def design_basement_wall(H, thickness, concrete_grade, rebar_grade,
                         soil_unit_weight=18.0, water_height=None,
                         surcharge=10.0, K0=0.5, a_s=40.0) -> BasementWallResult:
    log = TraceLog()
    M_design, comp = basement_wall_moment(H, soil_unit_weight, water_height,
                                          surcharge, K0)
    log.step(title="外墙侧压力(底部峰值)", clause="土力学/GB 50009", basis=Basis.ENGINEERING,
             expression="土 K0·γs·H; 水 γw·hw; 活载 K0·q",
             substitution=f"土={comp['w_soil_kPa']:.1f}, 水={comp['w_water_kPa']:.1f}, "
                          f"活载={comp['w_surch_kPa']:.1f} kPa",
             result=f"H={H} m")
    log.step(title="设计弯矩(1m板带,简支)", clause="结构力学简化模型", basis=Basis.ENGINEERING,
             expression="M=1.3(Msoil+Mwater)+1.5·Msurch; 三角形系数1/(9√3),矩形1/8",
             substitution=f"Msoil={comp['M_soil']:.1f}, Mwater={comp['M_water']:.1f}, "
                          f"Msurch={comp['M_surch']:.1f}",
             result=f"M_design={M_design:.1f} kN·m/m")
    # 1m 板带受弯配筋（复用梁受弯内核，b=1000）
    fl = gb.design_flexure(1000.0, thickness, M_design, concrete_grade,
                           rebar_grade, a_s=a_s)
    for s in fl.log.steps:
        log.add(s)
    As_min, _ = gb.min_tension_area(1000.0, thickness, concrete_grade, rebar_grade)
    As_req = max(fl.As, As_min)
    log.step(title="外墙竖向受力筋(每米)", clause="8.5.1", basis=Basis.CONSTRUCTION,
             substitution=f"As计算={fl.As:.0f}, As,min={As_min:.0f}",
             result=f"As={As_req:.0f} mm²/m")
    return BasementWallResult(H=H, M_design=M_design, components=comp,
                              flexure=fl, As_req=As_req, log=log)


@dataclass
class AntiFloatResult:
    buoyancy: float       # 浮力 (kN)
    weight: float         # 抗浮重 (kN)
    Kf: float             # 抗浮安全系数
    required: float       # 规范要求
    ok: bool
    ballast_need: float   # 不足时需增加的压重/锚杆抗力 (kN)
    log: TraceLog = field(default_factory=TraceLog)


def anti_float_check(water_head, area, total_weight_kn, gamma_w=10.0,
                     Kf_required=1.05) -> AntiFloatResult:
    """整体抗浮：Kf = G/Fw ≥ 1.05 (规范常用)。

    water_head: 抗浮设防水位至底板底的水头(m)；area: 底板投影面积(m²)；
    total_weight_kn: 结构自重+压重等抗浮有利荷载标准值(kN)。
    """
    log = TraceLog()
    Fw = gamma_w * water_head * area
    Kf = total_weight_kn / Fw if Fw > 0 else float("inf")
    ok = Kf >= Kf_required
    ballast = max(0.0, Kf_required * Fw - total_weight_kn)
    log.step(title="浮力 Fw", clause="抗浮设计", basis=Basis.ENGINEERING,
             expression="Fw = γw·hw·A",
             substitution=f"= {gamma_w}×{water_head}×{area}",
             result=f"Fw={Fw:.0f} kN")
    log.step(title="抗浮安全系数 Kf", clause="抗浮设计", basis=Basis.ENGINEERING,
             expression="Kf = G/Fw ≥ 1.05",
             substitution=f"= {total_weight_kn:.0f}/{Fw:.0f}",
             result=f"Kf={Kf:.3f} {'满足' if ok else '不满足→需压重/抗浮锚杆 '+format(ballast,'.0f')+' kN'}")
    return AntiFloatResult(buoyancy=Fw, weight=total_weight_kn, Kf=Kf,
                           required=Kf_required, ok=ok, ballast_need=ballast, log=log)
