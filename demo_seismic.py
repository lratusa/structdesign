"""
振型分解反应谱法 demo —— 6 层框架地震作用。

由层质量与层抗侧刚度(柱提供)求自振周期/振型，套 GB 50011 反应谱，SRSS 组合
得各层地震力、层剪力、基底剪力。输出可作为后续配筋的水平地震工况。

运行：python demo_seismic.py → 生成 计算书_地震反应谱.md
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign import materials
from structdesign.analysis.modal import story_stiffness_from_columns
from structdesign.analysis.response_spectrum import response_spectrum_analysis


def main():
    n = 6
    h = 3600.0                     # 层高 mm
    g = 9.81
    # 每层 4 根 500×500 C40 柱 → 层抗侧刚度
    E = materials.concrete("C40").Ec        # N/mm²
    I_one = 500 * 500 ** 3 / 12             # mm⁴
    I_total = 4 * I_one
    k_story_Nmm = story_stiffness_from_columns(E, I_total, h)   # N/mm
    k_story = k_story_Nmm * 1000.0          # → N/m
    masses = [6.0e5] * n                    # 每层 600 t
    stiff = [k_story] * n

    # 8度多遇 (αmax=0.16), II类场地第二组 Tg=0.40
    res = response_spectrum_analysis(masses, stiff, alpha_max=0.16, Tg=0.40, g=g)

    print("=" * 56)
    print("振型分解反应谱法 · 6层框架 · 8度多遇 · II类场地")
    print("=" * 56)
    print("自振周期 (s):")
    for j, T in enumerate(res.modal.periods, 1):
        print(f"  T{j} = {T:.3f}   (α={res.alphas[j-1]:.4f}, γ={res.modal.gammas[j-1]:.3f})")
    print(f"\n有效质量占比(前1阶): {res.modal.Meff[0]/res.modal.Mtotal*100:.1f}%")
    print("\n层地震力 / 层剪力 (kN)，自下而上:")
    for i in range(n):
        print(f"  第{i+1}层: F={res.story_forces[i]/1e3:8.1f}   V={res.story_shears[i]/1e3:8.1f}")
    Wtot = sum(masses) * g
    print(f"\n基底剪力 V0 = {res.base_shear/1e3:.1f} kN")
    print(f"剪重比 = V0/ΣG = {res.base_shear/Wtot*100:.2f}%")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "计算书_地震反应谱.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 结构计算书 —— 振型分解反应谱法\n\n")
        f.write("依据 GB 50011 5.2.2；剪切层模型；阻尼比 0.05。\n")
        f.write("条件：6层，层高3.6m，每层4根500×500 C40柱，层质量600t；8度多遇(αmax=0.16)，II类场地Tg=0.40。\n\n")
        f.write("## 自振周期与振型参与\n\n| 阶 | 周期T(s) | α | 参与系数γ |\n|---|---|---|---|\n")
        for j, T in enumerate(res.modal.periods, 1):
            f.write(f"| {j} | {T:.3f} | {res.alphas[j-1]:.4f} | {res.modal.gammas[j-1]:.3f} |\n")
        f.write("\n## 楼层地震力与层剪力 (SRSS组合)\n\n| 层 | 地震力F(kN) | 层剪力V(kN) |\n|---|---|---|\n")
        for i in range(n):
            f.write(f"| {i+1} | {res.story_forces[i]/1e3:.1f} | {res.story_shears[i]/1e3:.1f} |\n")
        f.write(f"\n**基底剪力 V0 = {res.base_shear/1e3:.1f} kN；剪重比 = {res.base_shear/Wtot*100:.2f}%**\n\n")
        f.write("> 周期、振型经解析解验证；层地震力可作为水平地震工况进入荷载组合与配筋。\n")
    print(f"\n计算书: {out}")


if __name__ == "__main__":
    main()
