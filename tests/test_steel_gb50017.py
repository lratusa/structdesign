"""钢结构 GB 50017 验算 —— 解析/手算校核。

手算依据：
- 工字形截面特性由板件几何积分：A=2·b·tf+(h-2tf)·tw；Ix=b·h³/12-(b-tw)(h-2tf)³/12；
  Wx=Ix/(h/2)；ix=√(Ix/A)。HW200×200×8×12：A≈6208mm²、Ix≈4.61e7mm⁴、Wx≈4.61e5mm³。
- 抗弯强度 σ=M/(γx·Wx)，γx=1.05；M 使 σ=f 时利用率≈1。
- 轴压稳定 φ：λ=0→φ=1；λ=100,Q355→φ≈0.42(附录D, b类)；N_cap=φ·A·f。
- 强度设计值 f：Q355 t≤16→305，16<t≤40→295；Q235 t≤16→215。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from structdesign.codes import gb50017_steel as st


def test_section_properties():
    s = st.SECTIONS["HW200x200"]
    assert abs(s.A - 6208) < 5, s.A
    assert abs(s.Ix - 4.61e7) / 4.61e7 < 0.02, s.Ix
    assert abs(s.Wx - s.Ix / (s.h / 2)) < 1e-6
    assert abs(s.ix - (s.Ix / s.A) ** 0.5) < 1e-6
    # 与型钢表(含圆角)相差<3%
    assert abs(s.A - 6353) / 6353 < 0.03


def test_design_strength_by_thickness():
    assert st.steel_f("Q355", 12) == 305
    assert st.steel_f("Q355", 20) == 295
    assert st.steel_f("Q235", 12) == 215
    assert st.steel_fv("Q355", 10) == 175


def test_phi_axial_monotonic():
    assert abs(st.phi_axial(0, "Q355") - 1.0) < 1e-9
    assert abs(st.phi_axial(100, "Q355") - 0.42) < 0.03
    prev = 1.01
    for lam in (0, 20, 50, 100, 150, 200):
        v = st.phi_axial(lam, "Q355")
        assert v <= prev + 1e-9 and v > 0, (lam, v)
        prev = v


def test_beam_strength_utilization():
    s = st.SECTIONS["HN500x200"]
    f = st.steel_f("Q355", s.tf)
    # 取使抗弯强度利用率≈1 的弯矩
    M_cap = f * 1.05 * s.Wx / 1e6      # kN·m
    chk = st.check_steel_beam(s, M=M_cap, V=50, L=6000, l1=0.0, grade="Q355")
    assert abs(chk.items["抗弯强度σ"][2] - 1.0) < 0.02, chk.items["抗弯强度σ"]
    # 半载 → 强度利用率≈0.5
    chk2 = st.check_steel_beam(s, M=M_cap * 0.5, V=50, L=6000, l1=0.0, grade="Q355")
    assert abs(chk2.items["抗弯强度σ"][2] - 0.5) < 0.02


def test_beam_lateral_support_helps():
    # 侧向支承短(l1小) → 整体稳定利用率低于侧向支承长(l1大)
    s = "HN600x200"
    braced = st.check_steel_beam(s, M=200, V=80, L=8000, l1=1500, grade="Q355")
    unbraced = st.check_steel_beam(s, M=200, V=80, L=8000, l1=8000, grade="Q355")
    assert braced.items["整体稳定"][2] <= unbraced.items["整体稳定"][2]


def test_column_axial_capacity():
    s = st.SECTIONS["HW300x300"]
    f = st.steel_f("Q355", s.tf)
    # 纯轴压(Mx=0)，取 l0 使 λ≈100
    l0 = int(100 * s.ix)
    phi = st.phi_axial(l0 / s.ix, "Q355")
    N_cap = phi * s.A * f / 1e3        # kN
    chk = st.check_steel_column(s, N=N_cap, Mx=0.0, l0x=l0, l0y=l0, grade="Q355")
    assert abs(chk.items["平面内稳定"][2] - 1.0) < 0.03, chk.items["平面内稳定"]


def test_column_slenderness_flag():
    s = st.SECTIONS["HN400x200"]      # iy 较小，易超长细比
    chk = st.check_steel_column(s, N=100, Mx=10, l0x=12000, l0y=12000, grade="Q355")
    assert chk.items["长细比λ"][3] is False     # 超 150
    assert chk.ok is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
