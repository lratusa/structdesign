# -*- coding: utf-8 -*-
"""structdesign 建模器启动器。

用法：
    python launch_modeler.py            # 启动 GUI
    structdesign_modeler.exe --selftest # 打包后自检：跑一遍分析+出图+3D，结果写 ~/structdesign_work/_selftest/
本机开发用 python=3.9.7（含 PyQt5/numpy/matplotlib/ezdxf/plotly），不要用 python3。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtWidgets


def _selftest():
    """打包健康自检：核心链路(分析→配筋图→3D)能否在冻结环境跑通。结果写文件(无控制台也可查)。"""
    out = os.path.join(os.path.expanduser("~"), "structdesign_work", "_selftest")
    os.makedirs(out, exist_ok=True)
    try:
        from modeler.project import (Column, Beam, Grid, StandardFloor, SlabLoad, Storey,
                                     Seismic, Project)
        from modeler.run.analyze import analyze
        from modeler.io.dxf_export import export_plan
        from modeler import view3d
        from modeler.project import Wall, Slab
        B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
        cols = [Column(x, y, 600, 600) for x in xs for y in ys]
        beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 650) for y in ys for i in range(2)]
                 + [Beam(x, ys[k], x, ys[k + 1], 300, 650) for x in xs for k in range(2)])
        slabs = [Slab(xs[i], ys[k], xs[i + 1], ys[k + 1], 120) for i in range(2) for k in range(2)]
        p = Project(grid=Grid(xs, ys),
                    floor=StandardFloor(columns=cols, beams=beams, walls=[Wall(B, B, 2 * B, B, 300)],
                                        slabs=slabs, slab=SlabLoad(6, 2.5)),
                    storeys=[Storey(3600, 4)], seismic=Seismic(n_modes=6))
        r = analyze(p, out)
        # 出图(含新版图框/标题栏/平法通长筋腰筋/墙边缘大样/板B-T)
        export_plan(p, r, os.path.join(out, "plan.dxf"),
                    os.path.join(out, "plan.png"), os.path.join(out, "plan.pdf"))
        from modeler.io.dxf_export import export_slab_plan as _esp
        _esp(p, r, os.path.join(out, "slab.dxf"), os.path.join(out, "slab.png"))
        view3d.export_html(p, r, os.path.join(out, "v3d.html"), "util")
        view3d.export_png(p, r, os.path.join(out, "v3d.png"), "disp")
        # 新功能模块的冻结环境冒烟(确保 hiddenimport 齐全：钢结构/地区/识别/命令/基础/板施工图)
        from structdesign.codes import gb50017_steel as _st
        _st.check_steel_beam("HN400x200", 200, 80, 6000, grade="Q355")
        from modeler import regions as _rg
        _rg.apply_region(p, "beijing")
        from modeler import commands as _cmd
        _cmd.to_tool_schema()
        _cmd.run_nl(p, "标准层所有板 恒载5 活载2")        # AI 本地执行链
        from modeler.io import recognize as _rec  # noqa: F401
        from modeler.io.dxf_export import export_slab_plan  # noqa: F401
        from modeler.run.foundation import design_strip_footings, design_piles  # noqa: F401
        view3d.export_html(p, r, os.path.join(out, "v3d_load.html"), "load")   # 荷载3D
        view3d.export_mode_animation(p, r, os.path.join(out, "v3d_anim.html"), "扭转")  # 振型动画
        with open(os.path.join(out, "SELFTEST_OK.txt"), "w", encoding="utf-8") as f:
            f.write("ok\nT1=%.3f base=%.0fkN steel=%.1ft\n"
                    "modules: steel/region/cmd/recognize/foundation OK\n"
                    % (r.T1, r.base_x / 1e3, r.total_steel_t))
        return 0
    except Exception:
        import traceback
        with open(os.path.join(out, "SELFTEST_FAIL.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        return 2


def main():
    app = QtWidgets.QApplication(sys.argv)
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    # 全局字体加大、标题更醒目（用户反馈：字体偏小，尤其标题）
    f = app.font(); f.setPointSize(11); app.setFont(f)
    app.setStyleSheet(
        "QGroupBox{font-size:14px;font-weight:bold;margin-top:8px;}"
        "QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 4px;}"
        "QDockWidget{font-size:14px;}"
        "QDockWidget::title{font-size:15px;font-weight:bold;padding:6px;background:#eef2f7;}"
        "QPushButton{font-size:13px;padding:3px 6px;}"
        "QLabel,QComboBox,QLineEdit,QDoubleSpinBox,QSpinBox,QTableWidget{font-size:13px;}")
    from modeler.app import MainWindow
    w = MainWindow()
    w.resize(1360, 900)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
