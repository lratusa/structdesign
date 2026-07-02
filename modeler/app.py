"""structdesign 建模器主窗口（PyQt5）。

导入 DWG/DXF 底图 → 画轴网/柱/梁/墙(或一键生成规则轴网) → 设楼层表/地震参数 → 计算 → 结果 + 计算书。
"""
from __future__ import annotations
import os
import sys
from PyQt5 import QtWidgets, QtGui, QtCore

import copy
from .canvas import Canvas
from .project import (Column, Beam, Wall, Slab, Opening, WallOpening, StairPlacement, Joint,
                      SlabLoad, Storey, StandardFloor, Seismic, Wind, Thermal, Basement, Grid, Project)
from . import edit
from .io.dxf_import import import_drawing
from .io.recognize import recognize
from .io.dxf_export import export_plan, export_foundation, export_stair, export_slab_plan
from .run.analyze import analyze, ModelUnstableError
from .run.optimize import optimize, DesignPrefs
from .run.stairs import design_stair
from .run.checks import continuity_check, auto_transfer
from . import view3d

HERE = os.path.dirname(os.path.abspath(__file__))
# 打包(frozen)后程序目录可能只读 → 输出写到用户可写目录
if getattr(sys, "frozen", False):
    OUT_DIR = os.path.join(os.path.expanduser("~"), "structdesign_work")
else:
    OUT_DIR = os.path.join(HERE, "_work")


class Worker(QtCore.QThread):
    done = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, project):
        super().__init__()
        self.project = project

    def run(self):
        try:
            res = analyze(self.project, OUT_DIR)
            self.done.emit(res)
        except ModelUnstableError as e:
            self.failed.emit("MODEL_UNSTABLE::" + str(e))
        except Exception:
            import traceback
            self.failed.emit(traceback.format_exc())


class OptimizeWorker(QtCore.QThread):
    stepped = QtCore.pyqtSignal(object)   # IterRecord
    done = QtCore.pyqtSignal(object)      # OptimizeResult
    failed = QtCore.pyqtSignal(str)

    def __init__(self, project, prefs):
        super().__init__()
        self.project = project
        self.prefs = prefs

    def run(self):
        try:
            res = optimize(self.project, self.prefs, OUT_DIR,
                           progress_cb=lambda rec: self.stepped.emit(rec))
            self.done.emit(res)
        except ModelUnstableError as e:
            self.failed.emit("MODEL_UNSTABLE::" + str(e))
        except Exception:
            import traceback
            self.failed.emit(traceback.format_exc())


class DesignPrefsDialog(QtWidgets.QDialog):
    """试算风格 / 要求 选择对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("试算风格与要求")
        self.setMinimumWidth(420)
        f = QtWidgets.QFormLayout(self)
        intro = QtWidgets.QLabel("软件将据此自动迭代加大/减小截面，直到满足规范并优化用料。")
        intro.setWordWrap(True)
        f.addRow(intro)
        self.obj = QtWidgets.QComboBox(); self.obj.addItems(["经济（最省材料）", "均衡（推荐）", "稳健（留裕度）"])
        self.obj.setCurrentIndex(1)
        self.strat = QtWidgets.QComboBox(); self.strat.addItems(
            ["全优化（自动加大+减小）", "只加大到满足", "只配筋（不改截面）"])
        self.emp = QtWidgets.QComboBox(); self.emp.addItems(["标准", "严格（位移角/轴压比留更大裕度）"])
        self.maxit = QtWidgets.QSpinBox(); self.maxit.setRange(5, 80); self.maxit.setValue(30)
        f.addRow("试算风格", self.obj)
        f.addRow("截面策略", self.strat)
        f.addRow("控制重点", self.emp)
        f.addRow("最大迭代轮数", self.maxit)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        f.addRow(bb)

    def prefs(self) -> DesignPrefs:
        obj = ["经济", "均衡", "稳健"][self.obj.currentIndex()]
        strat = ["full", "grow", "fixed"][self.strat.currentIndex()]
        emp = ["标准", "严格"][self.emp.currentIndex()]
        return DesignPrefs(objective=obj, strategy=strat, emphasis=emp, max_iter=self.maxit.value())


class _AIWorker(QtCore.QThread):
    """LLM 智能对话后台线程（避免网络调用卡界面）。"""
    done = QtCore.pyqtSignal(str, object, str)   # reply, summaries, err

    def __init__(self, project, text, history):
        super().__init__()
        self.project = project; self.text = text; self.history = history

    def run(self):
        try:
            from . import commands as C
            reply, summaries = C.run_llm(self.project, self.text, self.history)
            self.done.emit(reply, summaries, "")
        except Exception as e:
            self.done.emit("", [], str(e))


class SteelToolboxDialog(QtWidgets.QDialog):
    """钢结构工具箱：型钢梁/柱(压弯) 按 GB 50017 验算。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        from structdesign.codes import gb50017_steel as st
        self.st = st
        self.setWindowTitle("钢结构工具箱（GB 50017）")
        self.setMinimumWidth(460)
        v = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.mode = QtWidgets.QComboBox(); self.mode.addItems(["钢梁", "钢柱(压弯)"])
        self.sec = QtWidgets.QComboBox(); self.sec.addItems(list(st.SECTIONS.keys()))
        self.grade = QtWidgets.QComboBox(); self.grade.addItems(["Q235", "Q355", "Q390", "Q420"])
        self.grade.setCurrentText("Q355")

        def sp(val, lo, hi, step, dec=0):
            s = QtWidgets.QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(step)
            s.setDecimals(dec); s.setValue(val); return s
        self.M = sp(200, 0, 5000, 10, 0); self.V = sp(100, 0, 3000, 10, 0)
        self.L = sp(6000, 500, 30000, 100, 0); self.l1 = sp(0, 0, 30000, 100, 0)
        self.N = sp(1000, 0, 30000, 50, 0)
        self.l0x = sp(4000, 500, 30000, 100, 0); self.l0y = sp(4000, 500, 30000, 100, 0)
        form.addRow("构件类型", self.mode); form.addRow("截面", self.sec); form.addRow("钢材", self.grade)
        form.addRow("弯矩 M(kN·m)", self.M); form.addRow("剪力 V(kN)", self.V)
        form.addRow("跨度 L(mm)", self.L); form.addRow("受压翼缘侧向支承 l1(mm,0=全约束)", self.l1)
        form.addRow("轴力 N(kN,柱)", self.N)
        form.addRow("计算长度 l0x(mm,柱)", self.l0x); form.addRow("计算长度 l0y(mm,柱)", self.l0y)
        v.addLayout(form)
        btn = QtWidgets.QPushButton("验算"); btn.clicked.connect(self._run)
        v.addWidget(btn)
        self.out = QtWidgets.QTableWidget(0, 4)
        self.out.setHorizontalHeaderLabels(["验算项", "计算值", "限值/强度", "利用率/判定"])
        self.out.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        v.addWidget(self.out)
        self.summary = QtWidgets.QLabel("选截面与内力后点「验算」。"); self.summary.setWordWrap(True)
        v.addWidget(self.summary)

    def _run(self):
        st = self.st
        try:
            if self.mode.currentIndex() == 0:
                chk = st.check_steel_beam(self.sec.currentText(), self.M.value(), self.V.value(),
                                          self.L.value(), grade=self.grade.currentText(),
                                          l1=self.l1.value())
            else:
                chk = st.check_steel_column(self.sec.currentText(), self.N.value(), self.M.value(),
                                            self.l0x.value(), self.l0y.value(),
                                            grade=self.grade.currentText())
        except Exception as e:
            self.summary.setText(f"验算失败：{e}"); return
        self.out.setRowCount(len(chk.items))
        for i, (name, (val, lim, util, ok)) in enumerate(chk.items.items()):
            self.out.setItem(i, 0, QtWidgets.QTableWidgetItem(name))
            self.out.setItem(i, 1, QtWidgets.QTableWidgetItem(str(val)))
            self.out.setItem(i, 2, QtWidgets.QTableWidgetItem(str(lim)))
            self.out.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{util} {'✔' if ok else '✗'}"))
        s = st.SECTIONS[self.sec.currentText()]
        self.summary.setText(
            f"{chk.section}（{self.grade.currentText()}）A={s.A/100:.1f}cm² Wx={s.Wx/1e3:.0f}cm³ "
            f"ix={s.ix:.1f} iy={s.iy:.1f}mm　控制利用率 {chk.util}　"
            f"{'✔ 满足' if chk.ok else '✗ 不满足'}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("structdesign 建模器 — 导入图纸 · 建模 · 计算")
        self.project = Project(floor=StandardFloor(slab=SlabLoad(6.0, 2.5)),
                               storeys=[Storey(3600, 6)], seismic=Seismic())
        self.drawing = None
        self.result = None
        self._worker = None

        self.selected = set()          # {(kind, idx)}
        self._undo = []; self._redo = []
        self._op = None                # 移动/复制/镜像进行中

        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.canvas.coordMoved.connect(self._on_coord)
        self.canvas.pointPicked.connect(self._on_pick)
        self.canvas.clickSelect.connect(self._on_click_select)
        self.canvas.boxSelected.connect(self._on_box_select)

        self._build_toolbar()
        self._build_right_dock()
        self._build_bottom_dock()
        self._build_ai_dock()
        self._build_shortcuts()
        self.statusBar().showMessage("就绪。先「导入图纸」或「一键轴网」，再放构件，然后「计算」。")
        self._refresh()

    def _build_shortcuts(self):
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo_do)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo_do)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self._redo_do)
        QShortcut(QKeySequence(QtCore.Qt.Key_Delete), self, self._delete_selected)
        QShortcut(QKeySequence(QtCore.Qt.Key_Escape), self, self._cancel_op)

    # ---------- UI 构建（CAD/YJK 风格分组工具条） ----------
    def _build_toolbar(self):
        self._tool_group = QtWidgets.QActionGroup(self); self._tool_group.setExclusive(True)

        def group(title, newrow=False):
            if newrow:
                self.addToolBarBreak()
            tb = self.addToolBar(title); tb.setIconSize(QtCore.QSize(16, 16))
            tb.setMovable(True)
            lab = QtWidgets.QLabel(f" {title} "); lab.setStyleSheet(
                "color:#456;font-weight:bold;font-size:11px;border-right:1px solid #bbb;margin-right:4px;")
            tb.addWidget(lab)
            return tb

        def act(tb, text, slot, tip=""):
            a = QtWidgets.QAction(text, self); a.triggered.connect(slot)
            a.setToolTip(tip or text); tb.addAction(a); return a

        # 文件
        tb = group("文件")
        act(tb, "📂 导入", self._import, "导入 DWG/DXF 作底图")
        act(tb, "🔎 识别构件", self._recognize, "按图层把底图自动转成柱/墙/梁/轴网")
        act(tb, "💾 保存", self._save); act(tb, "📁 打开", self._load)
        # 建模
        tb = group("建模")
        act(tb, "▦ 一键轴网", self._quick_grid, "按跨数生成轴网+柱+梁")
        act(tb, "▣ 一键楼板", self._auto_slabs, "按轴网各区格自动布置楼板")
        for name, label in [("select", "▶ 选择"), ("column", "■ 柱"),
                            ("beam", "／ 梁"), ("wall", "▮ 墙"), ("slab", "▣ 板"),
                            ("open", "◳ 板洞"), ("wopen", "◫ 墙洞"), ("stairp", "⛢ 楼梯"),
                            ("joint", "╎ 缝")]:
            a = QtWidgets.QAction(label, self); a.setCheckable(True)
            a.triggered.connect(lambda _, n=name: self._set_tool(n))
            self._tool_group.addAction(a); tb.addAction(a)
            if name == "select":
                a.setChecked(True)
        # 编辑
        tb = group("编辑")
        act(tb, "↶ 撤销", self._undo_do, "撤销 Ctrl+Z")
        act(tb, "↷ 重做", self._redo_do, "重做 Ctrl+Y")
        act(tb, "⧉ 复制", lambda: self._start_op("copy"), "复制选中：点基点→目标点")
        act(tb, "✥ 移动", lambda: self._start_op("move"), "移动选中：点基点→目标点")
        act(tb, "◫ 镜像", lambda: self._start_op("mirror"), "对称/镜像选中：点对称轴两点")
        act(tb, "▦ 阵列", self._array_dialog, "矩形阵列选中构件")
        act(tb, "✖ 删除", self._delete_selected, "删除选中 Del")
        act(tb, "🗑 清空", self._clear_members, "清除所有柱/梁/墙")
        act(tb, "⤢ 适应", self.canvas.fit, "适应窗口")
        # 分析（新行）
        tb = group("分析", newrow=True)
        a_opt = act(tb, "🤖 自动优化设计", self._auto_optimize, "选风格 → 自动迭代优化截面 → 配筋 + 计算书")
        a_opt.setToolTip("选试算风格与要求 → 自动加大/减小截面迭代至满足规范并优化用料 → 出配筋与计算书")
        act(tb, "▶ 单次计算", self._calculate, "按当前截面算一次")
        act(tb, "✓ 拼接检验", self._continuity_check, "检查各层竖向构件是否对齐/悬空(多塔/转换排查)")
        act(tb, "⌶ 自动转换梁", self._auto_transfer, "在悬空竖向构件下层两支承间自动设转换深梁")
        # 出图
        tb = group("出图")
        act(tb, "📐 配筋图", self._export_drawing, "配筋平面图(柱表/墙表/梁表/原位标注/大样/材料表)")
        act(tb, "▤ 板施工图", self._export_slab, "板底钢筋+支座负筋+板表")
        act(tb, "🏗 基础图", self._export_foundation, "独基/条基/筏板/桩基 + 选型建议")
        act(tb, "🪜 楼梯图", self._export_stair, "板式双跑楼梯剖面+平面+说明")
        act(tb, "🧊 3D视图", self._view3d, "实体(板洞/楼梯/地下室)/荷载/利用率/变形/振型动画")
        act(tb, "📄 计算书", self._open_calcbook, "打开专业计算书")
        # 工具
        tb = group("工具")
        act(tb, "🔧 钢结构", self._steel_toolbox, "型钢梁/柱按 GB 50017 验算")
        act(tb, "🏛 规范审查", self._heng_review,
            "「衡」规范引擎：逐条溯源校核 + 送审强条自查表(每个判定→rule_id条文锚点)")

    def _build_right_dock(self):
        dock = QtWidgets.QDockWidget("参数 / 属性", self)
        dock.setAllowedAreas(QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea)
        w = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(6)

        # 截面
        gb_sec = QtWidgets.QGroupBox("当前截面 (mm)"); f = QtWidgets.QFormLayout(gb_sec)
        self.col_b = self._spin(500, 100, 3000); self.col_h = self._spin(500, 100, 3000)
        self.beam_b = self._spin(300, 100, 1000); self.beam_h = self._spin(600, 100, 2000)
        self.wall_t = self._spin(400, 100, 1000)
        f.addRow("柱 b", self.col_b); f.addRow("柱 h", self.col_h)
        f.addRow("梁 b", self.beam_b); f.addRow("梁 h", self.beam_h)
        self.slab_t = self._spin(120, 80, 400, 10)
        f.addRow("墙厚 t", self.wall_t)
        f.addRow("板厚 t", self.slab_t)
        lay.addWidget(gb_sec)

        # 板荷载
        gb_load = QtWidgets.QGroupBox("板荷载 (kN/m²)"); fl = QtWidgets.QFormLayout(gb_load)
        self.dead = self._spin(6.0, 0, 50, 0.5, dec=1); self.live = self._spin(2.5, 0, 50, 0.5, dec=1)
        fl.addRow("恒载", self.dead); fl.addRow("活载", self.live)
        lay.addWidget(gb_load)

        # 标准层（大底盘/多塔）
        gb_fl = QtWidgets.QGroupBox("标准层（多塔/大底盘）"); vf = QtWidgets.QVBoxLayout(gb_fl)
        self.floor_combo = QtWidgets.QComboBox()
        self._rebuild_floor_combo()
        self.floor_combo.currentIndexChanged.connect(self._on_floor_switch)
        fb = QtWidgets.QHBoxLayout()
        b_nf = QtWidgets.QPushButton("新建"); b_nf.clicked.connect(self._new_floor)
        b_df = QtWidgets.QPushButton("删除"); b_df.clicked.connect(self._del_floor)
        fb.addWidget(b_nf); fb.addWidget(b_df)
        vf.addWidget(QtWidgets.QLabel("当前编辑标准层：")); vf.addWidget(self.floor_combo); vf.addLayout(fb)
        lay.addWidget(gb_fl)

        # 楼层表
        gb_st = QtWidgets.QGroupBox("楼层表"); v = QtWidgets.QVBoxLayout(gb_st)
        self.storey_tbl = QtWidgets.QTableWidget(0, 3)
        self.storey_tbl.setHorizontalHeaderLabels(["层高(mm)", "层数", "标准层"])
        self.storey_tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        for s in self.project.storeys:
            self._add_storey_row(s.height, s.count, s.floor_id)
        btns = QtWidgets.QHBoxLayout()
        b_add = QtWidgets.QPushButton("+ 行"); b_add.clicked.connect(lambda: self._add_storey_row(3600, 1))
        b_del = QtWidgets.QPushButton("- 行"); b_del.clicked.connect(self._del_storey_row)
        btns.addWidget(b_add); btns.addWidget(b_del)
        v.addWidget(self.storey_tbl); v.addLayout(btns)
        lay.addWidget(gb_st)

        # 工程地区（地区标准：自动填地震/风参数 + 计算书引地标）
        from .regions import list_regions
        gb_rg = QtWidgets.QGroupBox("工程地区（地区标准）"); frg = QtWidgets.QFormLayout(gb_rg)
        self.region = QtWidgets.QComboBox()
        self._region_keys = [r.key for r in list_regions()]
        for r in list_regions():
            self.region.addItem(r.name)
        self.region.currentIndexChanged.connect(self._on_region_change)
        frg.addRow("地区", self.region)
        lay.addWidget(gb_rg)

        # 地震
        gb_eq = QtWidgets.QGroupBox("地震参数"); fe = QtWidgets.QFormLayout(gb_eq)
        self.alpha = self._spin(0.16, 0.01, 1.0, 0.01, dec=2)
        self.tg = self._spin(0.45, 0.1, 2.0, 0.05, dec=2)
        self.grade = QtWidgets.QComboBox(); self.grade.addItems(["一级", "二级", "三级", "四级"]); self.grade.setCurrentText("二级")
        self.nmodes = self._spin(12, 3, 30, 1, dec=0)
        self.fak = self._spin(200, 80, 800, 10, dec=0)
        self.vseis = QtWidgets.QCheckBox("计算竖向地震（8/9度·大跨·长悬挑·转换）")
        self.vseis.setChecked(False)
        self.diaphragm = QtWidgets.QComboBox()
        self.diaphragm.addItems(["刚性楼盖", "半刚性(出柔性周期对比)", "弹性(出柔性周期对比)"])
        fe.addRow("α_max", self.alpha); fe.addRow("Tg(s)", self.tg)
        fe.addRow("抗震等级", self.grade); fe.addRow("振型数", self.nmodes)
        fe.addRow("楼盖假定", self.diaphragm)
        fe.addRow(self.vseis)
        fe.addRow("地基承载力 fak(kPa)", self.fak)
        lay.addWidget(gb_eq)

        # 风荷载 (GB 50009)
        gb_w = QtWidgets.QGroupBox("风荷载参数"); fw = QtWidgets.QFormLayout(gb_w)
        self.wind_on = QtWidgets.QCheckBox("计入风荷载"); self.wind_on.setChecked(True)
        self.w0 = self._spin(0.40, 0.10, 1.50, 0.05, dec=2)
        self.terrain = QtWidgets.QComboBox(); self.terrain.addItems(["A", "B", "C", "D"]); self.terrain.setCurrentText("B")
        self.mu_s = self._spin(1.30, 0.50, 2.50, 0.05, dec=2)
        fw.addRow(self.wind_on)
        fw.addRow("基本风压 w0(kN/m²)", self.w0)
        fw.addRow("地面粗糙度", self.terrain); fw.addRow("体型系数 μs", self.mu_s)
        lay.addWidget(gb_w)

        # 温度作用 (GB 50009 第9章)
        gb_t = QtWidgets.QGroupBox("温度作用"); ft = QtWidgets.QFormLayout(gb_t)
        self.thermal_on = QtWidgets.QCheckBox("计入温度作用（无伸缩缝/超长结构）")
        self.thermal_on.setChecked(False)
        self.dT = self._spin(25.0, 5.0, 60.0, 5.0, dec=0)
        ft.addRow(self.thermal_on); ft.addRow("均匀温差 ΔT(℃)", self.dT)
        lay.addWidget(gb_t)

        # 地下室 (GB 50010 地下室外墙 + 抗浮)
        gb_b = QtWidgets.QGroupBox("地下室"); fb = QtWidgets.QFormLayout(gb_b)
        self.bsmt_on = QtWidgets.QCheckBox("设地下室（外墙水土压力+抗浮）"); self.bsmt_on.setChecked(False)
        self.bsmt_n = self._spin(1, 1, 5, 1, dec=0)
        self.bsmt_h = self._spin(3600, 2400, 6000, 100, dec=0)
        self.bsmt_t = self._spin(300, 200, 600, 25, dec=0)
        self.bsmt_water = self._spin(1.0, 0.0, 30.0, 0.5, dec=1)
        fb.addRow(self.bsmt_on)
        fb.addRow("地下室层数", self.bsmt_n); fb.addRow("层高(mm)", self.bsmt_h)
        fb.addRow("外墙厚(mm)", self.bsmt_t); fb.addRow("地下水位埋深(m)", self.bsmt_water)
        lay.addWidget(gb_b)

        lay.addStretch(1)
        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(w); scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        dock.setWidget(scroll)
        dock.setMinimumWidth(260)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self._param_dock = dock

    def _build_bottom_dock(self):
        dock = QtWidgets.QDockWidget("计算结果", self)
        w = QtWidgets.QWidget(); lay = QtWidgets.QHBoxLayout(w)
        self.summary = QtWidgets.QLabel("尚未计算。")
        self.summary.setStyleSheet("font-size:13px;")
        self.summary.setAlignment(QtCore.Qt.AlignTop)
        self.summary.setMinimumWidth(320); self.summary.setWordWrap(True)
        self.checks_tbl = QtWidgets.QTableWidget(0, 4)
        self.checks_tbl.setHorizontalHeaderLabels(["指标", "计算值", "限值", "判定"])
        self.checks_tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        lay.addWidget(self.summary, 1); lay.addWidget(self.checks_tbl, 2)
        dock.setWidget(w)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)

    def _build_ai_dock(self):
        from . import commands as C
        self._ai = C
        self._ai_history = []
        dock = QtWidgets.QDockWidget("🤖 AI 助手（自然语言控制）", self)
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        bar = QtWidgets.QHBoxLayout()
        self.ai_mode_lbl = QtWidgets.QLabel()
        key_btn = QtWidgets.QPushButton("设置 API Key"); key_btn.clicked.connect(self._ai_set_key)
        bar.addWidget(self.ai_mode_lbl, 1); bar.addWidget(key_btn)
        v.addLayout(bar)
        self.ai_view = QtWidgets.QTextEdit(); self.ai_view.setReadOnly(True)
        self.ai_view.setStyleSheet("font-size:14px;")
        v.addWidget(self.ai_view, 1)
        row = QtWidgets.QHBoxLayout()
        self.ai_input = QtWidgets.QLineEdit()
        self.ai_input.setPlaceholderText("用中文下指令，如：标准层所有板 恒载5 活载2 / 所有窗户从中心扩大200 / 梁纵筋取大包罗 / 改用北京地标")
        self.ai_input.returnPressed.connect(self._ai_send)
        send = QtWidgets.QPushButton("发送"); send.clicked.connect(self._ai_send)
        row.addWidget(self.ai_input, 1); row.addWidget(send)
        v.addLayout(row)
        dock.setWidget(w)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        # 与参数面板并为右侧标签页（CAD/YJK 风格：右侧属性/AI 选项卡）
        if getattr(self, "_param_dock", None):
            self.tabifyDockWidget(self._param_dock, dock)
            self._param_dock.raise_()
        self._ai_refresh_mode()
        self._ai_say("助手", "你好！我可以按你的中文指令修改模型与设计规则。试试："
                     "「标准层所有板 恒载5 活载2」「所有窗户从中心扩大200」「梁纵筋取大包罗」「改用北京地标」。")

    def _ai_refresh_mode(self):
        on = self._ai.llm_available()
        self.ai_mode_lbl.setText("模式：LLM 智能对话（已联网）" if on else
                                 "模式：本地规则（离线可用；设 API Key 启用 LLM）")

    def _ai_set_key(self):
        import os
        key, ok = QtWidgets.QInputDialog.getText(self, "设置 Anthropic API Key",
                                                 "输入 API Key（仅本次会话；留空清除）：",
                                                 QtWidgets.QLineEdit.Password,
                                                 os.environ.get("ANTHROPIC_API_KEY", ""))
        if not ok:
            return
        if key.strip():
            os.environ["ANTHROPIC_API_KEY"] = key.strip()
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        self._ai_refresh_mode()

    def _ai_say(self, who, text):
        color = "#2a6fdb" if who == "你" else "#1a8a4a"
        self.ai_view.append(f"<b style='color:{color}'>{who}：</b> {text}")
        self.ai_view.verticalScrollBar().setValue(self.ai_view.verticalScrollBar().maximum())

    def _ai_send(self):
        text = self.ai_input.text().strip()
        if not text:
            return
        self.ai_input.clear()
        self._ai_last_text = text
        self._ai_say("你", text)
        if self._ai.llm_available():
            self._ai_say("助手", "（LLM 思考中…）")
            self._ai_thread = _AIWorker(self.project, text, list(self._ai_history))
            self._ai_thread.done.connect(self._ai_on_llm)
            self._ai_thread.start()
        else:
            msgs = self._ai.run_nl(self.project, text)
            for m in msgs:
                self._ai_say("助手", m)
            self._ai_after_change()

    def _ai_on_llm(self, reply, summaries, err):
        if err:
            self._ai_say("助手", f"LLM 调用失败：{err}。已回退本地规则。")
            for m in self._ai.run_nl(self.project, self._ai_history[-1]["content"] if self._ai_history else ""):
                self._ai_say("助手", m)
        else:
            for s in summaries:
                self._ai_say("助手", "✔ " + s)
            if reply:
                self._ai_say("助手", reply)
        self._ai_after_change()

    def _ai_after_change(self):
        # 同步参数面板(荷载/地区等可能被改) + 刷新画布
        try:
            self._sync_widgets_from_project()
        except Exception:
            pass
        self.selected.clear(); self._refresh()
        self.statusBar().showMessage("AI 指令已应用，模型已更新。")
        # 闭环：用户若要求"计算/分析"，直接触发计算(不断档)
        txt = getattr(self, "_ai_last_text", "")
        if any(k in txt for k in ("计算", "算一", "算下", "算一下", "分析", "跑一", "重算")):
            if self.project.edit_floor().columns:
                self._ai_say("助手", "正在按更新后的模型计算…（完成后见底部「计算结果」面板）")
                self._calculate()

    def _sync_widgets_from_project(self):
        fl = self.project.edit_floor()
        self.dead.setValue(fl.slab.dead); self.live.setValue(fl.slab.live)
        rk = getattr(self.project, "region", "national")
        if rk in self._region_keys:
            self.region.blockSignals(True); self.region.setCurrentIndex(self._region_keys.index(rk))
            self.region.blockSignals(False)
        self.w0.setValue(self.project.wind.w0); self.terrain.setCurrentText(self.project.wind.terrain)
        dock.setMinimumHeight(180)

    def _spin(self, val, lo, hi, step=10, dec=0):
        s = QtWidgets.QDoubleSpinBox() if dec > 0 or isinstance(val, float) and dec else QtWidgets.QDoubleSpinBox()
        s.setRange(lo, hi); s.setSingleStep(step); s.setDecimals(int(dec)); s.setValue(val)
        return s

    # ---------- 标准层管理 ----------
    def _floor_ids(self):
        return [""] + list(self.project.floors.keys())   # "" = 默认标准层

    def _rebuild_floor_combo(self):
        self.floor_combo.blockSignals(True)
        self.floor_combo.clear()
        for fid in self._floor_ids():
            self.floor_combo.addItem("默认标准层" if fid == "" else fid, fid)
        cur = self.project.active_floor
        idx = self._floor_ids().index(cur) if cur in self._floor_ids() else 0
        self.floor_combo.setCurrentIndex(idx)
        self.floor_combo.blockSignals(False)

    def _on_floor_switch(self, _):
        self.project.active_floor = self.floor_combo.currentData() or ""
        self.selected.clear(); self._undo.clear(); self._redo.clear()
        # 切换后同步板荷载控件到该层
        fl = self.project.edit_floor()
        self.dead.setValue(fl.slab.dead); self.live.setValue(fl.slab.live)
        self._refresh()
        self.statusBar().showMessage(f"当前编辑：{self.floor_combo.currentText()}")

    def _new_floor(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "新建标准层", "标准层名称(如 塔楼/裙房):")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self.project.floors:
            QtWidgets.QMessageBox.information(self, "提示", "同名标准层已存在。"); return
        self.project.floors[name] = StandardFloor(slab=SlabLoad(self.dead.value(), self.live.value()))
        self.project.active_floor = name
        self._rebuild_floor_combo(); self._refresh()
        self.statusBar().showMessage(f"已新建标准层「{name}」，可在其上建模；楼层表「标准层」列填该名以分配层段。")

    def _del_floor(self):
        cur = self.project.active_floor
        if not cur:
            QtWidgets.QMessageBox.information(self, "提示", "默认标准层不可删除。"); return
        self.project.floors.pop(cur, None)
        for s in self.project.storeys:
            if s.floor_id == cur:
                s.floor_id = ""
        self.project.active_floor = ""
        self._rebuild_floor_combo()
        self.storey_tbl.setRowCount(0)
        for s in self.project.storeys:
            self._add_storey_row(s.height, s.count, s.floor_id)
        self._refresh()
        self.statusBar().showMessage(f"已删除标准层「{cur}」。")

    # ---------- 楼层表 ----------
    def _add_storey_row(self, height, count, floor_id=""):
        r = self.storey_tbl.rowCount(); self.storey_tbl.insertRow(r)
        self.storey_tbl.setItem(r, 0, QtWidgets.QTableWidgetItem(str(int(height))))
        self.storey_tbl.setItem(r, 1, QtWidgets.QTableWidgetItem(str(int(count))))
        self.storey_tbl.setItem(r, 2, QtWidgets.QTableWidgetItem(floor_id))

    def _del_storey_row(self):
        r = self.storey_tbl.currentRow()
        if r >= 0:
            self.storey_tbl.removeRow(r)

    def _read_storeys(self):
        out = []
        for r in range(self.storey_tbl.rowCount()):
            try:
                h = float(self.storey_tbl.item(r, 0).text())
                c = int(float(self.storey_tbl.item(r, 1).text()))
                fid_item = self.storey_tbl.item(r, 2)
                fid = (fid_item.text().strip() if fid_item else "")
                if fid not in self.project.floors:
                    fid = ""
                if c > 0:
                    out.append(Storey(h, c, fid))
            except (ValueError, AttributeError):
                continue
        return out or [Storey(3600, 1)]

    # ---------- 交互 ----------
    def _set_tool(self, name):
        self.canvas.set_tool(name)
        self.statusBar().showMessage({
            "select": "选择模式",
            "column": "柱：在捕捉点上单击放置柱",
            "beam": "梁：依次单击两点",
            "wall": "墙：依次单击两点",
            "slab": "板：单击对角两点画矩形楼板",
            "open": "板洞：单击对角两点画矩形洞(打孔)",
            "wopen": "墙洞/结构洞：沿墙单击两点定洞宽(默认洞高1500/窗台900)",
            "stairp": "楼梯：单击对角两点画梯段区(长边为梯跑方向)",
            "joint": "结构缝：单击两点画缝线",
        }.get(name, name))

    def _on_coord(self, x, y):
        self.statusBar().showMessage(f"X={x:.0f}  Y={y:.0f} mm")

    def _on_pick(self, x, y):
        if self._op is not None:
            self._op["pts"].append((x, y))
            if len(self._op["pts"]) >= 2:
                self._apply_op()
            else:
                self.statusBar().showMessage("再点第二点完成（Esc 取消）。")
            return
        tool = self.canvas._tool
        if tool == "column":
            self._snapshot()
            self.project.edit_floor().columns.append(Column(x, y, self.col_b.value(), self.col_h.value()))
            self._refresh()
        elif tool in ("beam", "wall", "slab", "open", "wopen", "stairp", "joint"):
            if self.canvas.pending() is None:
                self.canvas.set_pending((x, y))
                self.statusBar().showMessage("再单击第二点完成。")
            else:
                x0, y0 = self.canvas.pending(); self.canvas.set_pending(None)
                if abs(x - x0) < 1 and abs(y - y0) < 1:
                    return
                self._snapshot()
                fl = self.project.edit_floor()
                if tool == "beam":
                    fl.beams.append(Beam(x0, y0, x, y, self.beam_b.value(), self.beam_h.value()))
                elif tool == "wall":
                    fl.walls.append(Wall(x0, y0, x, y, self.wall_t.value()))
                elif tool == "slab":
                    fl.slabs.append(Slab(x0, y0, x, y, self.slab_t.value()))
                elif tool == "open":
                    fl.openings.append(Opening(x0, y0, x, y))
                elif tool == "wopen":
                    fl.wall_openings.append(WallOpening(x0, y0, x, y))
                elif tool == "stairp":
                    run = "x" if abs(x - x0) >= abs(y - y0) else "y"
                    fl.stairs_placed.append(StairPlacement(x0, y0, x, y, run))
                elif tool == "joint":
                    self.project.joints.append(Joint(x0, y0, x, y))
                self._refresh()

    # ---------- 选择 / 编辑 ----------
    def _shift(self):
        return bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier)

    def _on_click_select(self, x, y):
        hit = edit.hit_test(self.project.edit_floor(), x, y, 400)
        if hit is None:
            if not self._shift():
                self.selected.clear()
        elif self._shift():
            self.selected ^= {hit}
        else:
            self.selected = {hit}
        self._refresh()
        self.statusBar().showMessage(f"已选 {len(self.selected)} 个构件")

    def _on_box_select(self, x0, y0, x1, y1):
        items = set(edit.in_box(self.project.edit_floor(), x0, y0, x1, y1))
        self.selected = (self.selected | items) if self._shift() else items
        self._refresh()
        self.statusBar().showMessage(f"已选 {len(self.selected)} 个构件")

    def _snapshot(self):
        self._undo.append(copy.deepcopy(self.project.edit_floor()))
        if len(self._undo) > 60:
            self._undo.pop(0)
        self._redo.clear()

    def _undo_do(self):
        if not self._undo:
            self.statusBar().showMessage("无可撤销"); return
        self._redo.append(copy.deepcopy(self.project.edit_floor()))
        self._set_edit_floor(self._undo.pop())
        self.selected.clear(); self._refresh()
        self.statusBar().showMessage("已撤销")

    def _redo_do(self):
        if not self._redo:
            self.statusBar().showMessage("无可重做"); return
        self._undo.append(copy.deepcopy(self.project.edit_floor()))
        self._set_edit_floor(self._redo.pop())
        self.selected.clear(); self._refresh()
        self.statusBar().showMessage("已重做")

    def _set_edit_floor(self, fl):
        if self.project.active_floor and self.project.active_floor in self.project.floors:
            self.project.floors[self.project.active_floor] = fl
        else:
            self.project.floor = fl

    def _delete_selected(self):
        if not self.selected:
            self.statusBar().showMessage("未选构件"); return
        self._snapshot()
        fl = self.project.edit_floor()
        lists = {"col": fl.columns, "beam": fl.beams, "wall": fl.walls, "slab": fl.slabs,
                 "open": fl.openings, "wopen": fl.wall_openings, "stairp": fl.stairs_placed}
        for kind, lst in lists.items():
            for i in sorted([i for (k, i) in self.selected if k == kind], reverse=True):
                if 0 <= i < len(lst):
                    del lst[i]
        self.selected.clear(); self._refresh()
        self.statusBar().showMessage("已删除选中构件")

    def _cancel_op(self):
        if self._op is not None:
            self._op = None; self.canvas.set_tool("select")
            self.statusBar().showMessage("已取消操作")

    def _start_op(self, kind):
        if not self.selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择构件（点选或框选，Shift 加选）。")
            return
        self._op = {"kind": kind, "pts": []}
        self.canvas.set_tool("pick")
        msg = {"move": "移动：点基点 → 目标点",
               "copy": "复制：点基点 → 目标点",
               "mirror": "镜像：点对称轴第1点 → 第2点"}[kind]
        self.statusBar().showMessage(msg + "（Esc 取消）")

    def _apply_op(self):
        op = self._op; self._op = None
        self.canvas.set_tool("select")
        kind = op["kind"]; pts = op["pts"]
        fl = self.project.edit_floor()
        objs = [edit.get_obj(fl, k, i) for (k, i) in sorted(self.selected)]
        self._snapshot()
        if kind == "move":
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
            for (k, i) in self.selected:
                self._replace(k, i, edit.move_obj(edit.get_obj(fl, k, i), dx, dy))
        elif kind == "copy":
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
            self._add_objs([edit.move_obj(o, dx, dy) for o in objs])
        elif kind == "mirror":
            (ax, ay), (bx, by) = pts
            self._add_objs([edit.mirror_obj(o, ax, ay, bx, by) for o in objs])
        self._refresh()
        self.statusBar().showMessage({"move": "移动", "copy": "复制", "mirror": "镜像"}[kind] + "完成")

    def _replace(self, kind, idx, obj):
        fl = self.project.edit_floor()
        {"col": fl.columns, "beam": fl.beams, "wall": fl.walls, "slab": fl.slabs,
         "open": fl.openings, "wopen": fl.wall_openings, "stairp": fl.stairs_placed}[kind][idx] = obj

    def _add_objs(self, objs):
        fl = self.project.edit_floor(); newsel = set()
        for o in objs:
            if isinstance(o, Column):
                fl.columns.append(o); newsel.add(("col", len(fl.columns) - 1))
            elif isinstance(o, Wall):
                fl.walls.append(o); newsel.add(("wall", len(fl.walls) - 1))
            elif isinstance(o, Slab):
                fl.slabs.append(o); newsel.add(("slab", len(fl.slabs) - 1))
            elif isinstance(o, Opening):
                fl.openings.append(o); newsel.add(("open", len(fl.openings) - 1))
            elif isinstance(o, WallOpening):
                fl.wall_openings.append(o); newsel.add(("wopen", len(fl.wall_openings) - 1))
            elif isinstance(o, StairPlacement):
                fl.stairs_placed.append(o); newsel.add(("stairp", len(fl.stairs_placed) - 1))
            elif isinstance(o, Beam):
                fl.beams.append(o); newsel.add(("beam", len(fl.beams) - 1))
        self.selected = newsel

    def _array_dialog(self):
        if not self.selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择构件。")
            return
        dlg = QtWidgets.QDialog(self); dlg.setWindowTitle("矩形阵列")
        f = QtWidgets.QFormLayout(dlg)
        nx = self._spin(2, 1, 20, 1); ny = self._spin(1, 1, 20, 1)
        dx = self._spin(6000, -30000, 30000, 100); dy = self._spin(6000, -30000, 30000, 100)
        for lb, wd in [("X 数量", nx), ("Y 数量", ny), ("X 间距(mm)", dx), ("Y 间距(mm)", dy)]:
            f.addRow(lb, wd)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); f.addRow(bb)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        fl = self.project.edit_floor()
        objs = [edit.get_obj(fl, k, i) for (k, i) in sorted(self.selected)]
        self._snapshot()
        self._add_objs(edit.array_objs(objs, int(nx.value()), int(ny.value()), dx.value(), dy.value()))
        self._refresh()
        self.statusBar().showMessage("阵列完成")

    def _refresh(self):
        self.canvas.render_all(self.drawing, self.project, self.selected)
        # 捕捉点 = 底图端点 + 已有构件点 + 轴网交点
        pts = list(self.drawing.snap_points()) if self.drawing else []
        for c in self.project.edit_floor().columns:
            pts.append((c.x, c.y))
        for gx in self.project.grid.x:
            for gy in self.project.grid.y:
                pts.append((gx, gy))
        self.canvas.set_snap_points(pts)

    def _clear_members(self):
        self._snapshot()
        self.project.edit_floor().columns.clear()
        self.project.edit_floor().beams.clear()
        self.project.edit_floor().walls.clear()
        self.project.edit_floor().slabs.clear()
        self.project.edit_floor().openings.clear()
        self.project.edit_floor().wall_openings.clear()
        self.project.edit_floor().stairs_placed.clear()
        self.project.joints.clear()
        self.selected.clear()
        self._refresh()

    def _auto_slabs(self):
        gx, gy = self.project.grid.x, self.project.grid.y
        if len(gx) < 2 or len(gy) < 2:
            QtWidgets.QMessageBox.information(self, "提示", "请先「一键轴网」或建立轴网后再自动布板。")
            return
        from .run.slab_design import auto_slabs
        self._snapshot()
        self.project.edit_floor().slabs = auto_slabs(gx, gy, self.slab_t.value())
        self.selected.clear(); self._refresh()
        self.statusBar().showMessage(f"已按轴网布置楼板 {len(self.project.edit_floor().slabs)} 块（板厚 {int(self.slab_t.value())}）。")

    # ---------- 导入 ----------
    def _import(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "导入图纸", "", "CAD 图纸 (*.dwg *.dxf);;DXF (*.dxf);;DWG (*.dwg)")
        if not path:
            return
        try:
            self.drawing = import_drawing(path)
        except Exception as e:
            msg = str(e)
            if path.lower().endswith(".dwg"):
                msg = ("读取 DWG 失败。原生 DWG 需安装免费的 ODA File Converter；"
                       "或在 CAD 里导出为 DXF 再导入。\n\n详情：" + msg)
            QtWidgets.QMessageBox.warning(self, "导入失败", msg)
            return
        self._refresh(); self.canvas.fit()
        self.statusBar().showMessage(
            f"已导入：{os.path.basename(path)}（线 {len(self.drawing.lines)}，图层 {len(self.drawing.layers)}）")

    def _recognize(self):
        if not getattr(self, "drawing", None) or not self.drawing.layers:
            QtWidgets.QMessageBox.information(self, "提示", "请先「导入图纸」再识别构件。")
            return
        fl, grid, rep = recognize(self.drawing)
        cls = "\n".join(f"  {ly} → {role}" for ly, role in sorted(rep["layers"].items()))
        msg = (f"识别结果：\n柱 {rep['n_col']} · 墙 {rep['n_wall']} · 梁 {rep['n_beam']} · "
               f"轴网 {rep['n_axis_x']}×{rep['n_axis_y']}\n\n图层归类：\n{cls}\n\n"
               f"未归类图层（不生成构件）：{', '.join(rep['unclassified']) or '无'}\n\n"
               "是否用识别结果替换当前模型？")
        if QtWidgets.QMessageBox.question(self, "按图层识别构件", msg) != QtWidgets.QMessageBox.Yes:
            return
        if rep["n_col"] + rep["n_wall"] + rep["n_beam"] == 0:
            QtWidgets.QMessageBox.warning(self, "识别为空",
                                          "未识别到柱/墙/梁。请检查图层命名（柱/墙/梁/轴线 或 COL/WALL/BEAM/AXIS）。")
            return
        self._snapshot()
        fl.slab = self.project.edit_floor().slab
        if self.project.active_floor and self.project.active_floor in self.project.floors:
            self.project.floors[self.project.active_floor] = fl
        else:
            self.project.floor = fl
        if grid.x and grid.y:
            self.project.grid = grid
        self.selected.clear(); self._refresh(); self.canvas.fit()
        self.statusBar().showMessage(
            f"已识别：柱{rep['n_col']} 墙{rep['n_wall']} 梁{rep['n_beam']}（可继续编辑或「单次计算」）")

    # ---------- 一键轴网 ----------
    def _quick_grid(self):
        dlg = QtWidgets.QDialog(self); dlg.setWindowTitle("一键生成规则轴网")
        f = QtWidgets.QFormLayout(dlg)
        nx = self._spin(3, 1, 12, 1); ny = self._spin(3, 1, 12, 1)
        bx = self._spin(6000, 1000, 15000, 100); by = self._spin(6000, 1000, 15000, 100)
        wall = QtWidgets.QCheckBox("中央 2×2 设核心墙"); wall.setChecked(False)
        for lbl, wdg in [("X 跨数", nx), ("Y 跨数", ny), ("X 跨度(mm)", bx), ("Y 跨度(mm)", by)]:
            f.addRow(lbl, wdg)
        f.addRow(wall)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); f.addRow(bb)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        self._snapshot(); self.selected.clear()
        NX, NY = int(nx.value()), int(ny.value())
        BX, BY = bx.value(), by.value()
        cb, ch = self.col_b.value(), self.col_h.value()
        bw, bh = self.beam_b.value(), self.beam_h.value()
        xs = [i * BX for i in range(NX + 1)]; ys = [k * BY for k in range(NY + 1)]
        self.project.grid = Grid(xs, ys)
        fl = self.project.edit_floor()
        fl.columns.clear(); fl.beams.clear(); fl.walls.clear()
        for x in xs:
            for y in ys:
                fl.columns.append(Column(x, y, cb, ch))
        for y in ys:
            for i in range(NX):
                fl.beams.append(Beam(xs[i], y, xs[i + 1], y, bw, bh))
        for x in xs:
            for k in range(NY):
                fl.beams.append(Beam(x, ys[k], x, ys[k + 1], bw, bh))
        if wall.isChecked():
            cx = [xs[(NX - 1) // 2], xs[(NX - 1) // 2 + 1]]
            cy = [ys[(NY - 1) // 2], ys[(NY - 1) // 2 + 1]]
            t = self.wall_t.value()
            self._add_core_walls(cx, cy, t)
        self._refresh(); self.canvas.fit()
        self.statusBar().showMessage(f"已生成 {NX}×{NY} 轴网：柱 {len(fl.columns)}、梁 {len(fl.beams)}。")

    def _add_core_walls(self, cx, cy, t):
        fl = self.project.edit_floor()
        fl.walls.append(Wall(cx[0], cy[0], cx[1], cy[0], t))
        fl.walls.append(Wall(cx[0], cy[1], cx[1], cy[1], t))
        fl.walls.append(Wall(cx[0], cy[0], cx[0], cy[1], t))
        fl.walls.append(Wall(cx[1], cy[0], cx[1], cy[1], t))

    def _steel_toolbox(self):
        SteelToolboxDialog(self).exec_()

    def _on_region_change(self, idx):
        if idx < 0 or idx >= len(getattr(self, "_region_keys", [])):
            return
        from .regions import get_region
        r = get_region(self._region_keys[idx])
        self.project.region = r.key
        self.alpha.setValue(r.alpha_max); self.tg.setValue(r.Tg)
        self.w0.setValue(r.w0); self.terrain.setCurrentText(r.terrain)
        self.statusBar().showMessage(
            f"已套用地区标准：{r.name}（αmax={r.alpha_max} Tg={r.Tg}s 风压{r.w0}）。{r.notes}")

    # ---------- 计算 ----------
    def _sync_params(self):
        self.project.edit_floor().slab = SlabLoad(self.dead.value(), self.live.value())
        self.project.storeys = self._read_storeys()
        self.project.seismic = Seismic(self.alpha.value(), self.tg.value(),
                                       self.grade.currentText(), int(self.nmodes.value()),
                                       vertical=self.vseis.isChecked(),
                                       diaphragm=["rigid", "semi_rigid", "elastic"][self.diaphragm.currentIndex()])
        self.project.wind = Wind(self.wind_on.isChecked(), self.w0.value(),
                                 self.terrain.currentText(), self.mu_s.value())
        self.project.thermal = Thermal(self.thermal_on.isChecked(), self.dT.value())
        self.project.basement = Basement(self.bsmt_on.isChecked(), int(self.bsmt_n.value()),
                                         self.bsmt_h.value(), self.bsmt_t.value(),
                                         water_depth=self.bsmt_water.value())
        self.project.region = self._region_keys[self.region.currentIndex()]
        self.project.fak = self.fak.value()

    def _calculate(self):
        if not self.project.edit_floor().columns:
            QtWidgets.QMessageBox.information(self, "提示", "请先建立模型（一键轴网或手动放柱/梁）。")
            return
        self._sync_params()
        self._progress = QtWidgets.QProgressDialog("正在三维分析与配筋计算 …", None, 0, 0, self)
        self._progress.setWindowModality(QtCore.Qt.WindowModal)
        self._progress.setMinimumDuration(0); self._progress.setCancelButton(None)
        self._progress.show()
        self._worker = Worker(self.project)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_done(self, result):
        self._progress.close()
        self.result = result
        self._populate_results(result)
        self.statusBar().showMessage("计算完成。")

    def _on_failed(self, tb):
        if getattr(self, "_progress", None):
            self._progress.close()
        if getattr(self, "_opt_progress", None):
            self._opt_progress.close()
        if tb.startswith("MODEL_UNSTABLE::"):
            QtWidgets.QMessageBox.warning(self, "模型不稳定", tb[len("MODEL_UNSTABLE::"):])
            return
        QtWidgets.QMessageBox.critical(self, "出错", tb[-1500:])

    # ---------- 自动优化 ----------
    def _auto_optimize(self):
        if not self.project.edit_floor().columns:
            QtWidgets.QMessageBox.information(self, "提示", "请先建立模型（一键轴网或手动放柱/梁）。")
            return
        dlg = DesignPrefsDialog(self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        prefs = dlg.prefs()
        self._sync_params()
        self._opt_history = []
        self._opt_progress = QtWidgets.QProgressDialog("自动迭代优化中 …", None, 0, 0, self)
        self._opt_progress.setWindowModality(QtCore.Qt.WindowModal)
        self._opt_progress.setMinimumDuration(0); self._opt_progress.setCancelButton(None)
        self._opt_progress.setMinimumWidth(460)
        self._opt_progress.show()
        self._optw = OptimizeWorker(self.project, prefs)
        self._optw.stepped.connect(self._on_opt_step)
        self._optw.done.connect(self._on_opt_done)
        self._optw.failed.connect(self._on_failed)
        self._optw.start()

    def _on_opt_step(self, rec):
        self._opt_history.append(rec)
        wall = f" 墙{rec.wall_t}" if rec.wall_t else ""
        flag = "✔满足" if rec.feasible else f"不足{rec.n_bad}"
        self._opt_progress.setLabelText(
            f"第 {rec.it} 轮 [{rec.phase}]\n柱 {rec.col} · 梁 {rec.beam_h}{wall}\n"
            f"用钢 {rec.steel_t} t   {flag}")

    def _on_opt_done(self, ores):
        self._opt_progress.close()
        self.project = ores.project
        self.result = ores.result
        self.selected.clear()
        c0 = self.project.edit_floor().columns[0]
        self.col_b.setValue(c0.b); self.col_h.setValue(c0.h)
        if self.project.edit_floor().beams:
            self.beam_b.setValue(self.project.edit_floor().beams[0].b)
            self.beam_h.setValue(self.project.edit_floor().beams[0].h)
        if self.project.edit_floor().walls:
            self.wall_t.setValue(self.project.edit_floor().walls[0].t)
        self._refresh()
        self._populate_results(self.result, ores)
        msg = "优化收敛 ✔" if ores.converged else "已尽力（未完全满足，建议人工复核/调整体系）"
        self.statusBar().showMessage(f"自动优化完成：共 {ores.iterations} 轮，{msg}")

    def _populate_results(self, r, ores=None):
        self.checks_tbl.setRowCount(0)
        for name, val, lim, ok in r.checks_table:
            row = self.checks_tbl.rowCount(); self.checks_tbl.insertRow(row)
            for col, text in enumerate([name, val, lim, "✔ 满足" if ok else "✗ 不满足"]):
                it = QtWidgets.QTableWidgetItem(text)
                if not ok:
                    it.setForeground(QtGui.QBrush(QtGui.QColor("#cf222e")))
                self.checks_tbl.setItem(row, col, it)
        strength_ok = (r.n_bad == 0)
        tors_fail = any((("周期比" in c[0]) or ("位移比" in c[0])) and not c[3] for c in r.checks_table)
        other_fail = any(not c[3] for c in r.checks_table if not (("周期比" in c[0]) or ("位移比" in c[0])))
        if strength_ok and not other_fail and not tors_fail:
            verdict = "✔ 方案可行"
        elif strength_ok and not other_fail and tors_fail:
            verdict = "✔ 承载力/位移满足；扭转指标见下注"
        else:
            verdict = "✗ 有不满足项"
        tors_note = ("<br><span style='color:#9a6700;font-size:11px'>注：周期比/位移比为扭转规则性指标，"
                     "靠均匀加大截面收效甚微，需调整结构布置（如周边设墙/偏心布置）；"
                     "且本模型楼面质量集中于柱节点，周期比偏保守。</span>") if tors_fail else ""
        col0 = self.project.edit_floor().columns[0] if self.project.edit_floor().columns else None
        sec_line = ""
        if col0:
            sec_line = f"优化截面：柱 {int(col0.b)}×{int(col0.h)}"
            if self.project.edit_floor().beams:
                b0 = self.project.edit_floor().beams[0]; sec_line += f"，梁 {int(b0.b)}×{int(b0.h)}"
            if self.project.edit_floor().walls:
                sec_line += f"，墙厚 {int(self.project.edit_floor().walls[0].t)}"
            sec_line += "<br>"
        hist_html = ""
        if ores is not None:
            rows = "".join(
                f"<tr><td>{h.it}</td><td>{h.phase}</td><td>{h.col}/{h.beam_h}"
                f"{('/' + str(h.wall_t)) if h.wall_t else ''}</td><td>{h.steel_t}</td>"
                f"<td>{'✔' if h.feasible else h.n_bad}</td></tr>"
                for h in ores.history)
            hist_html = (
                "<br><b>迭代历史</b>（轮/阶段/柱·梁·墙/用钢t/判定）："
                "<table border='1' cellspacing='0' cellpadding='2' style='font-size:11px'>"
                "<tr><th>#</th><th>阶段</th><th>截面</th><th>钢t</th><th>判</th></tr>"
                f"{rows}</table>")
        self.summary.setText(
            f"<b style='font-size:15px'>{verdict}</b><br><br>"
            f"{sec_line}"
            f"自振周期 Tx={r.Tx:.2f} Ty={r.Ty:.2f} Tt={r.Tt:.2f} s<br>"
            f"周期比 Tt/T1 = {r.period_ratio:.3f}<br>"
            f"基底剪力 Vx={r.base_x/1e3:.0f} Vy={r.base_y/1e3:.0f} kN<br>"
            + (f"风基底剪力 Wx={r.wind_base_x/1e3:.0f} Wy={r.wind_base_y/1e3:.0f} kN"
               f"（{'风控制' if r.wind_controls else '地震控制'}）<br>"
               if getattr(r, 'wind_base_x', 0) > 0 else "")
            + (f"温度作用最大柱弯矩 ≈ {r.thermal_col_M:.0f} kN·m<br>"
               if getattr(r, 'thermal_on', False) else "")
            + (f"竖向地震 F_Evk={r.vert_Evk/1e3:.0f} kN，柱轴力增量 ≈ {r.vert_col_N:.0f} kN<br>"
               if getattr(r, 'vert_on', False) else "")
            + f"剪重比 = {r.shear_weight*100:.2f}%<br>"
            f"位移比 X/Y = {r.disp_ratio_x:.2f}/{r.disp_ratio_y:.2f}<br>"
            f"最大层间位移角 = 1/{1/max(r.drift_x,1e-9):.0f}<br>"
            f"竖向构件 {r.n_members} 个，不足 {r.n_bad} 个<br>"
            f"纵筋估算 ≈ {r.total_steel_t:.1f} t<br>"
            + (f"材料：混凝土 {r.takeoff.get('conc_total',0):.0f} m³、钢筋 {r.takeoff.get('steel_total_t',0):.1f} t"
               f"（{r.takeoff.get('steel_kg_m2',0):.0f} kg/m²、{r.takeoff.get('conc_m3_per_m2',0):.2f} m³/m²）"
               if getattr(r, 'takeoff', None) else "")
            + f"{tors_note}<br>"
            f"{hist_html}<br>"
            f"<i>点「打开计算书」看完整专业计算书</i>")

    def _export_drawing(self):
        if not self.project.edit_floor().columns:
            QtWidgets.QMessageBox.information(self, "提示", "请先建立模型。")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出配筋平面图", "", "DXF 图纸 (*.dxf)")
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"
        base = os.path.splitext(path)[0]
        png = base + ".png"; pdf = base + ".pdf"
        try:
            self._sync_params()
            dxf_out, png_out, pdf_out = export_plan(self.project, self.result, path, png, pdf,
                                                    with_rebar=bool(self.result))
        except Exception as e:
            import traceback
            QtWidgets.QMessageBox.critical(self, "出图失败", traceback.format_exc()[-1200:])
            return
        if png_out and os.path.exists(png_out):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(png_out))
        note = "（含柱表·梁逐跨原位标注）" if self.result else "（仅结构布置；计算后出图才含配筋）"
        self.statusBar().showMessage(f"已出图{note}：{os.path.basename(path)}")
        QtWidgets.QMessageBox.information(
            self, "出图完成",
            f"配筋平面图已导出{note}：\nDXF：{path}\nPDF：{pdf}\n预览：{png}\n\nDXF 可用 AutoCAD 编辑，PDF 可直接打印/交付。")

    def _export_slab(self):
        if not self.result or not getattr(self.result, "slabs", None):
            QtWidgets.QMessageBox.information(self, "提示", "请先布置楼板并「计算」，板施工图需板配筋结果。")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出板配筋施工图", "", "DXF 图纸 (*.dxf)")
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"
        base = os.path.splitext(path)[0]
        try:
            self._sync_params()
            _, png, pdf = export_slab_plan(self.project, self.result, path, base + ".png", base + ".pdf")
        except Exception:
            import traceback
            QtWidgets.QMessageBox.critical(self, "出图失败", traceback.format_exc()[-1200:])
            return
        if png and os.path.exists(png):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(png))
        self.statusBar().showMessage(f"已出板施工图：{os.path.basename(path)}")
        QtWidgets.QMessageBox.information(self, "出图完成",
                                          f"板配筋施工图已导出：\nDXF：{path}\nPDF：{base}.pdf\n预览：{base}.png")

    def _export_foundation(self):
        if not self.project.edit_floor().columns:
            QtWidgets.QMessageBox.information(self, "提示", "请先建立模型。")
            return
        if not self.result:
            QtWidgets.QMessageBox.information(self, "提示", "请先「自动优化设计」或「单次计算」，基础需柱底轴力。")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出基础平面图", "", "DXF 图纸 (*.dxf)")
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"
        base = os.path.splitext(path)[0]
        self._sync_params()
        try:
            _, png, pdf = export_foundation(self.project, self.result, path,
                                            base + ".png", base + ".pdf", fak=self.project.fak)
        except Exception:
            import traceback
            QtWidgets.QMessageBox.critical(self, "出图失败", traceback.format_exc()[-1200:])
            return
        if png and os.path.exists(png):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(png))
        self.statusBar().showMessage(f"已出基础图（fak={self.project.fak:.0f}kPa）：{os.path.basename(path)}")
        QtWidgets.QMessageBox.information(self, "出图完成", f"基础平面图：\nDXF：{path}\nPDF：{base}.pdf")

    def _export_stair(self):
        h = self.project.storeys[0].height if self.project.storeys else 3600
        # 若布置了楼梯，用其梯段宽度
        sp = self.project.edit_floor().stairs_placed
        width = 1600
        if sp:
            width = min(abs(sp[0].x2 - sp[0].x1), abs(sp[0].y2 - sp[0].y1)) or 1600
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出楼梯详图", "", "DXF 图纸 (*.dxf)")
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"
        base = os.path.splitext(path)[0]
        try:
            s = design_stair(floor_h=h, width=width)
            _, png, pdf = export_stair(s, path, base + ".png", base + ".pdf")
        except Exception:
            import traceback
            QtWidgets.QMessageBox.critical(self, "出图失败", traceback.format_exc()[-1200:])
            return
        if png and os.path.exists(png):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(png))
        self.statusBar().showMessage(f"已出楼梯图（层高{h:.0f}）：{os.path.basename(path)}")
        QtWidgets.QMessageBox.information(self, "出图完成", f"楼梯详图：\nDXF：{path}\nPDF：{base}.pdf")

    def _view3d(self):
        if not self.project.edit_floor().columns:
            QtWidgets.QMessageBox.information(self, "提示", "请先建立模型。")
            return
        dlg = QtWidgets.QDialog(self); dlg.setWindowTitle("三维视图")
        f = QtWidgets.QFormLayout(dlg)
        mode = QtWidgets.QComboBox()
        mode.addItems(["实体模型(含板洞/楼梯/地下室)", "荷载分布(重力+风)", "利用率云图(需先计算)",
                       "变形位移(需先计算)", "振型动画-扭转(需先计算)", "振型动画-X平动(需先计算)"])
        fmt = QtWidgets.QComboBox(); fmt.addItems(["浏览器交互(HTML)", "静态图片(PNG)"])
        f.addRow("内容", mode); f.addRow("形式", fmt)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); f.addRow(bb)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        idx = mode.currentIndex()
        m = {0: "model", 1: "load", 2: "util", 3: "disp", 4: "anim_t", 5: "anim_x"}[idx]
        if m in ("util", "disp") and not self.result:
            QtWidgets.QMessageBox.information(self, "提示", "利用率/变形需先「自动优化设计」或「单次计算」。")
            return
        self._sync_params()
        anim = m.startswith("anim")
        ext = "html" if (fmt.currentIndex() == 0 or anim) else "png"
        out = os.path.join(OUT_DIR, f"view3d_{m}.{ext}")
        try:
            if anim:
                which = "扭转" if m == "anim_t" else "X"
                view3d.export_mode_animation(self.project, self.result, out, which)
            elif ext == "html":
                view3d.export_html(self.project, self.result, out, m)
            else:
                view3d.export_png(self.project, self.result, out, m)
        except Exception:
            import traceback
            QtWidgets.QMessageBox.critical(self, "3D 生成失败", traceback.format_exc()[-1200:])
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(out))
        self.statusBar().showMessage(f"已生成三维视图：{os.path.basename(out)}")

    def _continuity_check(self):
        self._sync_params()
        issues = continuity_check(self.project)
        self.canvas.set_issues([(i["x"], i["y"]) for i in issues])
        self._refresh()
        if not issues:
            QtWidgets.QMessageBox.information(self, "拼接检验", "✔ 各层竖向构件均连续(无悬空)。")
            self.statusBar().showMessage("拼接检验：通过，无悬空竖向构件。")
        else:
            txt = "\n".join("· " + i["msg"] for i in issues[:30])
            more = f"\n… 共 {len(issues)} 处" if len(issues) > 30 else ""
            QtWidgets.QMessageBox.warning(self, "拼接检验：发现悬空竖向构件",
                                          f"以下竖向构件下层无支承，需设转换梁/转换层(平面已红圈标注)：\n\n{txt}{more}")
            self.statusBar().showMessage(f"拼接检验：{len(issues)} 处悬空，需转换(红圈标注)。")

    def _auto_transfer(self):
        self._sync_params()
        added = auto_transfer(self.project)
        self.canvas.set_issues([]); self.selected.clear(); self._refresh()
        if not added:
            QtWidgets.QMessageBox.information(self, "自动转换梁",
                                             "未生成：无悬空竖向构件，或悬空点两侧无可作支承的柱。")
            self.statusBar().showMessage("自动转换梁：无需或无法生成。")
            return
        txt = "\n".join("· " + a["msg"] for a in added[:30])
        QtWidgets.QMessageBox.information(
            self, "自动转换梁",
            f"已在下层自动生成 {len(added)} 处转换深梁（每处两段、相交于悬空点形成支承）：\n\n{txt}\n\n"
            f"请「单次计算/自动优化」复核转换梁配筋（其承托上部荷载，截面已按深梁取大）。")
        self.statusBar().showMessage(f"已生成 {len(added)} 道转换梁，请重新计算复核。")

    def _open_calcbook(self):
        if not self.result:
            QtWidgets.QMessageBox.information(self, "提示", "请先计算。")
            return
        path = self.result.calcbook_docx or self.result.calcbook_md
        if path and os.path.exists(path):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        else:
            QtWidgets.QMessageBox.information(self, "提示", "未找到计算书文件。")

    def _heng_review(self):
        """「衡」规范引擎：逐条溯源校核章节 + 送审强条自查表(玻璃盒·每判定→条文锚点)。"""
        if not self.result:
            QtWidgets.QMessageBox.information(self, "提示", "请先计算。")
            return
        try:
            self._sync_params()
            from heng.review import review_package, render_markdown
            from heng.calcsection import compliance_section
            jur = getattr(self.project, "jurisdiction", "CN")
            pkg = review_package(self.result, self.project, jur)      # 送审包(未签名=AI起草)
            md = (render_markdown(pkg) + "\n\n---\n\n"
                  + compliance_section(self.result, self.project, jur))
            out = (os.path.dirname(self.result.calcbook_md)
                   if self.result.calcbook_md else os.getcwd())
            fp = os.path.join(out, "规范审查_强条自查表.md")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(md)
        except Exception:
            QtWidgets.QMessageBox.critical(self, "规范审查出错", traceback.format_exc()[-1500:])
            return
        n = len(pkg["mandatory"]["rows"])
        bad = sum(1 for r in pkg["mandatory"]["rows"] if not r["verdict"])
        head = ("⚠ <b>存在强制性条文不满足（红线），不得送审</b>" if pkg["red_line"]
                else "✔ 强制性条文全部满足")
        QtWidgets.QMessageBox.information(
            self, "「衡」规范审查",
            f"辖区 <b>{pkg['jurisdiction']}</b>　强条自查 {n} 项，不满足 {bad} 项<br>{head}<br>"
            f"送审快照：<code>{pkg['ssm_commit']}</code>（{'已签名' if pkg['signed'] else '未签名·AI起草待确认'}）<br><br>"
            f"逐条溯源审查表已生成，每个判定可点击溯源至 rule_id 条文原文。")
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(fp))

    # ---------- 存读 ----------
    def _save(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "保存工程", "", "建模工程 (*.sdproj)")
        if not path:
            return
        if not path.endswith(".sdproj"):
            path += ".sdproj"
        self._sync_params(); self.project.save(path)
        self.statusBar().showMessage(f"已保存：{os.path.basename(path)}")

    def _load(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "打开工程", "", "建模工程 (*.sdproj)")
        if not path:
            return
        self.project = Project.load(path)
        self.selected.clear(); self._undo.clear(); self._redo.clear()
        # 同步控件
        self._rebuild_floor_combo()
        self.storey_tbl.setRowCount(0)
        for s in self.project.storeys:
            self._add_storey_row(s.height, s.count, s.floor_id)
        self.dead.setValue(self.project.edit_floor().slab.dead); self.live.setValue(self.project.edit_floor().slab.live)
        self.alpha.setValue(self.project.seismic.alpha_max); self.tg.setValue(self.project.seismic.Tg)
        self.grade.setCurrentText(self.project.seismic.grade); self.nmodes.setValue(self.project.seismic.n_modes)
        self.vseis.setChecked(getattr(self.project.seismic, "vertical", False))
        self.diaphragm.setCurrentIndex(
            {"rigid": 0, "semi_rigid": 1, "elastic": 2}.get(getattr(self.project.seismic, "diaphragm", "rigid"), 0))
        rk = getattr(self.project, "region", "national")
        self.region.blockSignals(True)
        self.region.setCurrentIndex(self._region_keys.index(rk) if rk in self._region_keys else 0)
        self.region.blockSignals(False)
        self.fak.setValue(getattr(self.project, "fak", 200))
        wd = getattr(self.project, "wind", None) or Wind()
        self.wind_on.setChecked(wd.enabled); self.w0.setValue(wd.w0)
        self.terrain.setCurrentText(wd.terrain); self.mu_s.setValue(wd.mu_s)
        tm = getattr(self.project, "thermal", None) or Thermal()
        self.thermal_on.setChecked(tm.enabled); self.dT.setValue(tm.dT)
        bm = getattr(self.project, "basement", None) or Basement()
        self.bsmt_on.setChecked(bm.enabled); self.bsmt_n.setValue(bm.n_levels)
        self.bsmt_h.setValue(bm.height); self.bsmt_t.setValue(bm.wall_t); self.bsmt_water.setValue(bm.water_depth)
        self._refresh(); self.canvas.fit()
        self.statusBar().showMessage(f"已打开：{os.path.basename(path)}")
