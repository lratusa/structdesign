"""离屏演示完整工作流：建模 → 自动迭代优化 → 优化后模型/配筋/计算书截图。
QT_QPA_PLATFORM=offscreen python modeler/_demo_shot.py
"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
from PyQt5 import QtWidgets, QtGui, QtCore
from modeler.app import MainWindow
from modeler.io.dxf_import import import_drawing
from modeler.project import Column, Beam, Grid, Storey
from modeler.run.optimize import optimize, DesignPrefs

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")


def make_sample_dxf(path):
    doc = ezdxf.new(); msp = doc.modelspace()
    O = [(-1000, -1000), (25000, -1000), (25000, 25000), (-1000, 25000)]
    for (x1, y1), (x2, y2) in zip(O, O[1:] + [O[0]]):
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "ARCH-OUTLINE"})
    for x in (8000, 16000):
        msp.add_line((x, -1000), (x, 25000), dxfattribs={"layer": "ARCH-PARTITION"})
    for y in (8000, 16000):
        msp.add_line((-1000, y), (25000, y), dxfattribs={"layer": "ARCH-PARTITION"})
    doc.saveas(path)


def render_model(canvas, path):
    scene = canvas.scene_
    rect = scene.itemsBoundingRect()
    img = QtGui.QImage(1100, 1100, QtGui.QImage.Format_ARGB32)
    img.fill(QtGui.QColor("#ffffff"))
    p = QtGui.QPainter(img); p.setRenderHint(QtGui.QPainter.Antialiasing)
    scene.render(p, QtCore.QRectF(20, 20, 1060, 1060), rect, QtCore.Qt.KeepAspectRatio)
    p.end(); img.save(path)


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    w = MainWindow(); w.resize(1320, 860)
    os.makedirs(WORK, exist_ok=True)

    dxf = os.path.join(WORK, "_sample_arch.dxf"); make_sample_dxf(dxf)
    w.drawing = import_drawing(dxf)

    # 起始：偏小 400 柱、300x550 梁，纯框架 3x3 @7500，6 层 → 需优化加大，再减小省料
    NX = NY = 3; B = 7500
    xs = [i * B for i in range(NX + 1)]; ys = [k * B for k in range(NY + 1)]
    w.project.grid = Grid(xs, ys)
    fl = w.project.floor
    fl.columns.clear(); fl.beams.clear(); fl.walls.clear()
    for x in xs:
        for y in ys:
            fl.columns.append(Column(x, y, 400, 400))
    for y in ys:
        for i in range(NX):
            fl.beams.append(Beam(xs[i], y, xs[i + 1], y, 300, 550))
    for x in xs:
        for k in range(NY):
            fl.beams.append(Beam(x, ys[k], x, ys[k + 1], 300, 550))
    w.project.storeys = [Storey(3600, 6)]
    w.project.floor.slab.dead = 6.0; w.project.floor.slab.live = 2.5
    w._refresh(); w.canvas.fit()
    render_model(w.canvas, os.path.join(WORK, "shot_model_before.png"))

    print(">> 自动迭代优化（均衡 / 全优化）…")
    res = optimize(w.project, DesignPrefs(objective="均衡", strategy="full"), WORK,
                   progress_cb=lambda r: print(
                       f"  第{r.it:2d}轮[{r.phase}] 柱{r.col} 梁{r.beam_h}"
                       + (f" 墙{r.wall_t}" if r.wall_t else "")
                       + f"  钢{r.steel_t}t  {'满足' if r.feasible else '不足%d'%r.n_bad}"))

    # 优化结果回填到窗口
    w.project = res.project; w.result = res.result
    w._refresh(); w.canvas.fit()
    render_model(w.canvas, os.path.join(WORK, "shot_model_after.png"))

    c0 = res.project.floor.columns[0]
    fr = res.result
    print("\n>> 优化完成：%d 轮，%s" % (res.iterations, "收敛✔" if res.converged else "已尽力"))
    print("   最终截面：柱 %dx%d  梁 %dx%d  墙 %d" % (
        c0.b, c0.h, res.project.floor.beams[0].b, res.project.floor.beams[0].h,
        res.project.floor.walls[0].t if res.project.floor.walls else 0))
    print("   Tx=%.2f Tt/T1=%.3f Vx=%.0fkN 位移角=1/%.0f 不足=%d 纵筋≈%.1ft" % (
        fr.Tx, fr.period_ratio, fr.base_x / 1e3, 1 / max(fr.drift_x, 1e-9), fr.n_bad, fr.total_steel_t))
    print("   计算书：", fr.calcbook_md)


if __name__ == "__main__":
    main()
