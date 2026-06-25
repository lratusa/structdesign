"""
一键总流程 demo —— 读参数 → 导荷 → 分析配筋(含P-Δ/自动生长) → 钢筋表 → 出图 → 计算书。

跑两个：① 常规 4跨6层；② 用户的 2000㎡/层 × 20 层（方案级）。
运行：python demo_project.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.design_project import ProjectParams, design_project

HERE = os.path.dirname(os.path.abspath(__file__))


def run(title, p, sub):
    out = os.path.join(HERE, sub)
    r = design_project(p, out)
    print("=" * 64)
    print(title)
    print("=" * 64)
    print("  " + r.summary)
    print(f"  楼板线荷载 w={r.w_gravity:.1f} kN/m；输出目录 {sub}/")
    for k, v in r.files.items():
        print(f"    - {k}: {os.path.basename(v)}")
    return r


def main():
    run("① 常规办公楼 4跨×6层 8m柱网 7度",
        ProjectParams(n_bays=4, n_stories=6, bay_w=8000, story_h=3600,
                      floor_area=2000, dead_kpa=5, live_kpa=2,
                      alpha_max=0.08, Tg=0.40, seismic_grade="三级",
                      col0=(600, 600), beam0=(300, 700)),
        "项目_常规6层")

    run("② 2000㎡/层 × 20 层（方案级；2D框架近似，最终需三维复核）",
        ProjectParams(n_bays=6, n_stories=20, bay_w=8000, story_h=3600,
                      floor_area=2000, dead_kpa=6, live_kpa=2.5,
                      alpha_max=0.16, Tg=0.45, seismic_grade="二级",
                      col0=(700, 700), beam0=(350, 750)),
        "项目_20层")

    print("\n注：20层4万㎡为真实三维结构，含核心筒/扭转/超限等，"
          "本结果为方案级估算（柱墙量级、含钢量、整体稳定），施工图须三维软件+注册工程师。")


if __name__ == "__main__":
    main()
