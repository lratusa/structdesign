"""
三维一键总流程 demo —— 一行参数 → 三维分析 → 配筋 → 三维计算书。

运行：python demo_project_3d.py → 生成 项目_三维/三维计算书.md, 三维模型.svg
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.design_project_3d import design_project_3d

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    out = design_project_3d(
        nx=3, ny=3, nz=12, bx=8000, by=8000, hz=3600,
        out_dir=os.path.join(HERE, "项目_三维"),
        col_bh=(750, 750), beam_bh=(350, 750),
        wall_cols={(1, 1), (1, 2), (2, 1), (2, 2)}, wall_bh=(400, 4000),
        dead_kpa=6.0, live_kpa=2.5, alpha_max=0.16, Tg=0.45, seismic_grade="二级",
        n_modes=12)

    print("=" * 64)
    print("三维一键总流程：3×3跨×12层 框架-核心")
    print("=" * 64)
    print(f"  Tx={out.Tx:.2f} Ty={out.Ty:.2f} Tt={out.Tt:.2f}s")
    print(f"  基底剪力 Vx={out.base_x/1e3:.0f} Vy={out.base_y/1e3:.0f}kN 剪重比={out.shear_weight*100:.2f}%")
    print("  规范指标：")
    for name, (val, ok) in out.checks.items():
        vs = f"{val:.3f}" if val < 10 else f"1/{1/val:.0f}"
        print(f"    {name:18s} = {vs:10s} {'✔' if ok else '✗'}")
    print(f"  竖向构件 {out.n_members} 个，不足 {out.n_bad} 个；纵筋约 {out.total_steel_t:.1f} t")
    print(f"\n  生成：{os.path.relpath(out.files['三维计算书_md'], HERE)}, 三维模型.svg")
    print("\n这是三维分析端到端到配筋：周期比/位移比/双向地震/双偏压配筋 一次出齐。")


if __name__ == "__main__":
    main()
