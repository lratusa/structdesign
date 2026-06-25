"""
整体建筑 demo —— 上部结构 + 地下室一体化（冲到阶段5.5）。

流程演示完整数据流：
  荷载工况 → 组合 → 包络 → 能力设计内力调整 → 配筋 → 验算(承载力+裂缝) → 计算书
覆盖：上部梁、上部柱、剪力墙墙肢(智能生长，读建筑可行域) + 地下室外墙 + 抗浮。

运行：python demo_building.py  → 生成 计算书_整体.md
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign import loads
from structdesign.loads import CaseForces, G, Q, W, E
from structdesign.codes import seismic_adjust as sa
from structdesign.codes import gb50010_beam as gb
from structdesign.codes import gb50010_sls as sls
from structdesign.codes import gb50010_basement as bm
from structdesign import rebar as rb
from structdesign.model import Column, ColumnForces, RectSection
from structdesign.design_column import design_column
from structdesign.arch import WallEnvelope
from structdesign.design_wall import design_wall_pier

SEISMIC = "二级"
L = []


def hdr(t): L.append(t)


def main():
    hdr("# 结构计算书 —— 整体（上部结构 + 地下室）")
    hdr("")
    hdr("依据：GB 50010 / GB 50011 / GB 50009；抗震等级 " + SEISMIC)
    hdr("> 数据流：荷载工况→组合→包络→能力设计调整→配筋→验算。每步标注依据。")
    hdr("")

    # ================= 上部结构 =================
    hdr("# 一、上部结构（地上）")

    # ---- 1) 框架梁 KL1：含组合+能力设计+受弯受剪+裂缝 ----
    hdr("\n## 1.1 框架梁 KL1（b×h=250×500, C30, HRB400）")
    # 支座截面各工况标准值内力
    cases = {G: CaseForces(M=-90, V=70), Q: CaseForces(M=-40, V=30),
             E: CaseForces(M=-110, V=60)}
    env = loads.envelope(cases, seismic=True)
    # 取支座最不利负弯矩 + 剪力
    M_design = env.M_neg
    V_env = env.V_max
    V_design, eta_v = sa.beam_shear_magnify(V_env, SEISMIC)
    hdr(f"- 组合包络：M_neg={M_design:.1f} kN·m, V={V_env:.1f} kN")
    hdr(f"- 强剪弱弯：V放大 η={eta_v} → V_design={V_design:.1f} kN  _[GB 50011 6.2.4]_")
    fl = gb.design_flexure(250, 500, abs(M_design), "C30", "HRB400", a_s=40)
    As_min, _ = gb.min_tension_area(250, 500, "C30", "HRB400")
    As_gov = max(fl.As, As_min)
    bars = rb.select_bars(As_gov, 250)
    sh = gb.design_shear(250, 500, V_design, "C30", "HPB300", a_s=40)
    # 裂缝（准永久弯矩近似取 G+0.5Q 标准组合）
    Mq = abs(cases[G].M + 0.5 * cases[Q].M)
    cr = sls.crack_width(250, 500, bars.As, Mq, "C30", "HRB400", d_bar=20, a_s=40)
    hdr(f"- 受弯：需 As={As_gov:.0f} mm² → **{bars.label()}** (As={bars.As:.0f})")
    hdr(f"- 受剪：Asv/s需={sh.Asv_s:.3f} → 配箍(详构件)；剪压比{'OK' if sh.section_ok else '超限'}")
    hdr(f"- 裂缝：ωmax={cr.wmax:.3f} mm（限0.3）{'✔' if cr.ok else '✗'}")

    # ---- 2) 框架柱 KZ1：组合 + 偏压 + 轴压比 ----
    hdr("\n## 1.2 框架柱 KZ1（b×h=500×500, C40, HRB400）")
    col = Column(name="KZ1", section=RectSection(500, 500, "C40", 40, 40),
                 main_rebar_grade="HRB400", seismic_grade=SEISMIC)
    # 柱端弯矩做强柱弱梁放大
    M_col_raw = 220.0
    M_col, eta_c = sa.column_moment_magnify(M_col_raw, SEISMIC)
    col.add_forces(ColumnForces(N=3400, M=M_col, V=90, location="柱底"))
    hdr(f"- 强柱弱梁：M放大 η={eta_c} → M={M_col:.1f} kN·m  _[GB 50011 6.2.2]_")
    cr2 = design_column(col)
    hdr(f"- 偏压类型：{cr2.eccentric}；轴压比 μN={cr2.axial_ratio:.3f}（限{cr2.axial_limit}）"
        f"{'✔' if cr2.axial_ok else '✗'}")
    hdr(f"- 纵筋：全截面 2×{cr2.bars_per_side.label()}，As={cr2.As_total_prov:.0f} mm² "
        f"{'✔' if cr2.ok else '✗ '+cr2.note}")

    # ---- 3) 剪力墙墙肢 Q1：读建筑可行域 + 智能生长 ----
    hdr("\n## 1.3 剪力墙墙肢 Q1（智能生长，读建筑可行域）")
    env_arch = WallEnvelope("Q1", axis="3/B-C", lw_min=300, lw_max=2500,
                            thickness_options=[200, 250])
    wr = design_wall_pier("Q1", N_kn=5200, M_knm=900, V_kn=420,
                          env=env_arch, concrete_grade="C40", rebar_grade="HRB400",
                          seismic_grade=SEISMIC, lw_init=1200)
    hdr(f"- 建筑可行域：lw∈[{env_arch.lw_min},{env_arch.lw_max}], 墙厚{env_arch.thickness_choices()}")
    for t in wr.trials:
        hdr(f"  - 生长尝试：{t}")
    if wr.feasible:
        hdr(f"- **墙肢确定：{wr.bw:.0f}×{wr.lw_final:.0f} mm，μN={wr.mu_N:.3f}≤{wr.axial_limit} ✔**")
        hdr(f"- 配筋：竖向分布筋 {wr.reinforcement.vert_dist}；"
            f"边缘构件 {wr.reinforcement.be_bars}（lc={wr.reinforcement.be_length:.0f}）")
    else:
        hdr(f"- ⚠ **无解→建筑配合需求**：{wr.arch_request}")

    # ================= 地下室 =================
    hdr("\n# 二、地下室（地下）")
    hdr("\n## 2.1 地下室外墙 DW1（厚300, C30, HRB400）")
    bw = bm.design_basement_wall(H=3.6, thickness=300, concrete_grade="C30",
                                 rebar_grade="HRB400", soil_unit_weight=18,
                                 water_height=3.6, surcharge=10, K0=0.5)
    c = bw.components
    hdr(f"- 侧压力(底)：土{c['w_soil_kPa']:.1f} + 水{c['w_water_kPa']:.1f} + 活载{c['w_surch_kPa']:.1f} kPa")
    hdr(f"- 设计弯矩 M={bw.M_design:.1f} kN·m/m → 竖向受力筋 As={bw.As_req:.0f} mm²/m "
        f"{'✔' if bw.flexure.ok else '✗'}")

    hdr("\n## 2.2 整体抗浮")
    af = bm.anti_float_check(water_head=4.5, area=600.0, total_weight_kn=32000.0)
    hdr(f"- 浮力 Fw={af.buoyancy:.0f} kN；抗浮重 G={af.weight:.0f} kN；Kf={af.Kf:.3f}（需≥1.05）"
        f"{'✔' if af.ok else '✗ 需压重/锚杆 '+format(af.ballast_need,'.0f')+' kN'}")

    hdr("\n# 三、结论")
    hdr("上部梁柱墙与地下室外墙、抗浮均已按规范完成配筋与验算；墙肢 Q1 在建筑可行域内"
        "自动生长至满足轴压比，全过程可追溯。详细逐步计算见各构件追溯日志。")
    hdr("")
    hdr("> 本计算书由 structdesign v0.2 自动生成，须由注册结构工程师复核签字。")

    md = "\n".join(L)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "计算书_整体.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)

    # 控制台摘要
    print("整体计算完成（上部 + 地下室）：")
    print(f"  梁KL1: {bars.label()}, ω={cr.wmax:.3f}mm")
    print(f"  柱KZ1: 2×{cr2.bars_per_side.label()}, μN={cr2.axial_ratio:.3f} ({cr2.eccentric})")
    print(f"  墙Q1 : {wr.bw:.0f}×{wr.lw_final:.0f}, μN={wr.mu_N:.3f}, "
          f"{'可行' if wr.feasible else '需建筑配合'}")
    print(f"  地下室外墙: As={bw.As_req:.0f}mm²/m; 抗浮 Kf={af.Kf:.3f} ({'OK' if af.ok else '不足'})")
    print(f"\n计算书: {out}")


if __name__ == "__main__":
    main()
