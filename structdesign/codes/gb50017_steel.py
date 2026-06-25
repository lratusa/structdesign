"""钢结构构件验算（GB 50017-2017）—— 工字/H 形截面 梁/柱/压弯。

截面特性由板件几何计算(A,Ix,Iy,Wx,Wy,ix,iy)，与型钢表相差仅圆角(<2%)、偏安全。
验算：
- 钢梁：抗弯强度 σ=Mx/(γx·Wnx)≤f；抗剪 τ=V·Sx/(Ix·tw)≤fv；整体稳定 Mx/(φb·Wx)≤f；挠度。
- 钢柱(轴压)：强度 N/An≤f；整体稳定 N/(φ·A)≤f(φ 按 b 类截面附录D)；长细比 λ≤[λ]。
- 压弯：强度 + 平面内/平面外稳定(8.2)。
依据 GB 50017 表4.4.1(f,fv)、附录C(φb)、附录D(φ)、第6/8章。
"""
from __future__ import annotations
from dataclasses import dataclass
import math

E_STEEL = 206000.0     # MPa


@dataclass
class SteelSection:
    name: str
    h: float; b: float; tw: float; tf: float    # mm（高/翼缘宽/腹板厚/翼缘厚）

    @property
    def A(self):                                  # mm²
        return 2 * self.b * self.tf + (self.h - 2 * self.tf) * self.tw

    @property
    def Ix(self):                                 # mm⁴（绕强轴）
        return self.b * self.h ** 3 / 12.0 - (self.b - self.tw) * (self.h - 2 * self.tf) ** 3 / 12.0

    @property
    def Iy(self):                                 # mm⁴（绕弱轴）
        return 2 * (self.tf * self.b ** 3 / 12.0) + (self.h - 2 * self.tf) * self.tw ** 3 / 12.0

    @property
    def Wx(self):
        return self.Ix / (self.h / 2.0)

    @property
    def Wy(self):
        return self.Iy / (self.b / 2.0)

    @property
    def ix(self):
        return math.sqrt(self.Ix / self.A)

    @property
    def iy(self):
        return math.sqrt(self.Iy / self.A)

    @property
    def Sx(self):
        """半截面对中性轴的面积矩(mm³)，用于腹板抗剪。"""
        hw = self.h - 2 * self.tf
        return self.b * self.tf * (self.h - self.tf) / 2.0 + self.tw * hw / 2.0 * hw / 4.0


# 常用热轧 H 型钢(GB/T 11263)，尺寸 h×b×tw×tf
SECTIONS = {
    "HW200x200": SteelSection("HW200x200", 200, 200, 8, 12),
    "HW250x250": SteelSection("HW250x250", 250, 250, 9, 14),
    "HW300x300": SteelSection("HW300x300", 300, 300, 10, 15),
    "HW400x400": SteelSection("HW400x400", 400, 400, 13, 21),
    "HM300x200": SteelSection("HM300x200", 294, 200, 8, 12),
    "HM400x300": SteelSection("HM400x300", 390, 300, 10, 16),
    "HM500x300": SteelSection("HM500x300", 488, 300, 11, 18),
    "HN400x200": SteelSection("HN400x200", 400, 200, 8, 13),
    "HN500x200": SteelSection("HN500x200", 500, 200, 10, 16),
    "HN600x200": SteelSection("HN600x200", 600, 200, 11, 17),
}


def steel_f(grade="Q355", t=16.0):
    """抗弯/抗拉/抗压强度设计值 f (MPa)，GB 50017 表4.4.1，按板厚 t。"""
    tbl = {
        "Q235": [(16, 215), (40, 205), (100, 200)],
        "Q355": [(16, 305), (40, 295), (63, 290), (100, 285)],
        "Q390": [(16, 345), (40, 330), (63, 310), (100, 295)],
        "Q420": [(16, 375), (40, 355), (63, 320), (100, 305)],
    }.get(grade, [(16, 305), (40, 295), (100, 285)])
    for tmax, f in tbl:
        if t <= tmax:
            return f
    return tbl[-1][1]


def steel_fv(grade="Q355", t=16.0):
    """抗剪强度设计值 fv (MPa)。"""
    tbl = {"Q235": [(16, 125), (40, 120), (100, 115)],
           "Q355": [(16, 175), (40, 170), (63, 165), (100, 160)],
           "Q390": [(16, 200), (40, 190), (100, 180)],
           "Q420": [(16, 215), (40, 205), (100, 195)]}.get(grade, [(16, 175), (100, 165)])
    for tmax, fv in tbl:
        if t <= tmax:
            return fv
    return tbl[-1][1]


def _fy(grade):
    return {"Q235": 235, "Q355": 355, "Q390": 390, "Q420": 420}.get(grade, 355)


def phi_axial(lam, grade="Q355", cls="b"):
    """轴心受压稳定系数 φ（GB 50017 附录D，默认 b 类截面）。lam=长细比。"""
    fy = _fy(grade)
    lam_n = lam / math.pi * math.sqrt(fy / E_STEEL)
    a = {"a": (0.41, 0.986, 0.152), "b": (0.65, 0.965, 0.300), "c": (0.73, 0.906, 0.595)}[cls]
    a1, a2, a3 = a
    if lam_n <= 0.215:
        return 1.0 - a1 * lam_n ** 2
    t = a2 + a3 * lam_n + lam_n ** 2
    return (t - math.sqrt(max(t ** 2 - 4 * lam_n ** 2, 0.0))) / (2 * lam_n ** 2)


def phi_b_beam(sec: SteelSection, l1, grade="Q355", beta_b=1.0):
    """梁整体稳定系数 φb（GB 50017 附录C.0.1，双轴对称工字形绕强轴）。
    l1=受压翼缘侧向支承点间距(mm)；返回 φb(已按 C.0.1-7 修正，≤1.0)。"""
    fy = _fy(grade)
    if l1 <= 1e-6:                # 受压翼缘连续侧向支承 → 不发生整体失稳
        return 1.0
    lam_y = l1 / sec.iy
    phib = (beta_b * 4320.0 / lam_y ** 2 * (sec.A * sec.h / sec.Wx)
            * (math.sqrt(1.0 + (lam_y * sec.tf / (4.4 * sec.h)) ** 2)) * (235.0 / fy))
    if phib > 0.6:
        phib = 1.07 - 0.282 / phib
    return min(phib, 1.0)


@dataclass
class SteelCheck:
    section: str
    items: dict          # {名称: (值, 限值, 利用率, ok)}
    util: float          # 控制利用率
    ok: bool


def check_steel_beam(sec_name, M, V, L, grade="Q355", l1=None, defl_limit=250.0, gamma_x=1.05):
    """钢梁验算。M(kN·m)、V(kN)、L 跨度(mm)、l1 受压翼缘侧向支承间距(mm，默认=L)。"""
    sec = SECTIONS[sec_name] if isinstance(sec_name, str) else sec_name
    f = steel_f(grade, sec.tf); fv = steel_fv(grade, sec.tw)
    l1 = l1 if l1 is not None else L
    items = {}
    # 抗弯强度
    sigma = M * 1e6 / (gamma_x * sec.Wx)
    items["抗弯强度σ"] = (round(sigma, 1), f, round(sigma / f, 2), sigma <= f)
    # 抗剪
    tau = V * 1e3 * sec.Sx / (sec.Ix * sec.tw)
    items["抗剪τ"] = (round(tau, 1), fv, round(tau / fv, 2), tau <= fv)
    # 整体稳定
    phib = phi_b_beam(sec, l1, grade)
    sig_b = M * 1e6 / (phib * sec.Wx)
    items["整体稳定"] = (round(sig_b, 1), f, round(sig_b / f, 2), sig_b <= f)
    # 挠度(按均布近似 5wL⁴/384EI, w 由 M=wL²/8 反推)
    w = 8.0 * M * 1e6 / (L ** 2)                          # N/mm
    defl = 5.0 * w * L ** 4 / (384.0 * E_STEEL * sec.Ix)  # mm
    lim = L / defl_limit
    items["挠度"] = (round(defl, 1), round(lim, 1), round(defl / lim, 2), defl <= lim)
    util = max(v[2] for v in items.values())
    return SteelCheck(sec.name, items, util, all(v[3] for v in items.values()))


def check_steel_column(sec_name, N, Mx, l0x, l0y, grade="Q355", beta_mx=1.0, lam_limit=150.0):
    """钢柱(压弯)验算。N(kN 压)、Mx(kN·m)、l0x/l0y 计算长度(mm)。"""
    sec = SECTIONS[sec_name] if isinstance(sec_name, str) else sec_name
    f = steel_f(grade, max(sec.tf, sec.tw))
    lam_x = l0x / sec.ix; lam_y = l0y / sec.iy
    phix = phi_axial(lam_x, grade); phiy = phi_axial(lam_y, grade)
    phib = phi_b_beam(sec, l0y, grade)
    items = {}
    # 长细比
    lam = max(lam_x, lam_y)
    items["长细比λ"] = (round(lam, 1), lam_limit, round(lam / lam_limit, 2), lam <= lam_limit)
    # 强度
    sig = N * 1e3 / sec.A + Mx * 1e6 / (1.05 * sec.Wx)
    items["强度"] = (round(sig, 1), f, round(sig / f, 2), sig <= f)
    # 平面内稳定
    NEx = math.pi ** 2 * E_STEEL * sec.A / (1.1 * lam_x ** 2)    # N
    s_in = N * 1e3 / (phix * sec.A) + beta_mx * Mx * 1e6 / (1.05 * sec.Wx * (1 - 0.8 * N * 1e3 / NEx))
    items["平面内稳定"] = (round(s_in, 1), f, round(s_in / f, 2), s_in <= f)
    # 平面外稳定
    s_out = N * 1e3 / (phiy * sec.A) + beta_mx * Mx * 1e6 / (phib * sec.Wx)
    items["平面外稳定"] = (round(s_out, 1), f, round(s_out / f, 2), s_out <= f)
    util = max(v[2] for v in items.values())
    return SteelCheck(sec.name, items, util, all(v[3] for v in items.values()))
