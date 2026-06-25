"""CAD 画布（QGraphicsView）：底图显示 + 网格 + 缩放/平移 + 捕捉 + 构件绘制。

世界坐标 = 工程毫米，Y 向上为正。鼠标移动发 coordMoved；放置工具下左键点击发 pointPicked(已捕捉)。
"""
from PyQt5 import QtWidgets, QtGui, QtCore


class Canvas(QtWidgets.QGraphicsView):
    coordMoved = QtCore.pyqtSignal(float, float)
    pointPicked = QtCore.pyqtSignal(float, float)
    clickSelect = QtCore.pyqtSignal(float, float)
    boxSelected = QtCore.pyqtSignal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_ = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene_)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#fbfcfe")))
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.scale(1, -1)                 # Y 向上为正
        self._snap_pts = []
        self._tool = "select"
        self._panning = False
        self._pan_start = None
        self._pending = None              # 梁/墙第一点
        self._marker = None
        self._rb = None                   # 框选橡皮筋
        self._rb_origin = None
        self._issues = []                 # 拼接检验问题点 [(x,y)]

    def set_issues(self, pts):
        self._issues = list(pts)

    # ---- 工具 / 捕捉 ----
    def set_tool(self, name):
        self._tool = name
        self._pending = None
        self.setCursor(QtCore.Qt.CrossCursor if name != "select" else QtCore.Qt.ArrowCursor)

    def set_snap_points(self, pts):
        self._snap_pts = list(pts)

    def world(self, ev):
        p = self.mapToScene(ev.pos())
        return p.x(), p.y()

    def _snap(self, x, y, r_px=14):
        # 像素半径换算到世界半径
        r = r_px / max(self.transform().m11(), 1e-9)
        best, bd = None, r * r
        for (sx, sy) in self._snap_pts:
            d = (sx - x) ** 2 + (sy - y) ** 2
            if d < bd:
                bd = d; best = (sx, sy)
        return best or (x, y)

    # ---- 鼠标 ----
    def mouseMoveEvent(self, ev):
        if self._panning and self._pan_start is not None:
            delta = ev.pos() - self._pan_start
            self._pan_start = ev.pos()
            h = self.horizontalScrollBar(); v = self.verticalScrollBar()
            h.setValue(h.value() - delta.x()); v.setValue(v.value() - delta.y())
            return
        if self._rb is not None and self._rb_origin is not None:
            self._rb.setGeometry(QtCore.QRect(self._rb_origin, ev.pos()).normalized())
        x, y = self.world(ev)
        sx, sy = self._snap(x, y)
        self.coordMoved.emit(sx, sy)
        super().mouseMoveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
            self._panning = True; self._pan_start = ev.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor); return
        if ev.button() == QtCore.Qt.LeftButton:
            if self._tool == "select":
                self._rb_origin = ev.pos()
                if self._rb is None:
                    self._rb = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self.viewport())
                self._rb.setGeometry(QtCore.QRect(self._rb_origin, QtCore.QSize()))
                self._rb.show(); return
            x, y = self.world(ev); sx, sy = self._snap(x, y)
            self.pointPicked.emit(sx, sy); return
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
            self._panning = False
            self.setCursor(QtCore.Qt.CrossCursor if self._tool != "select" else QtCore.Qt.ArrowCursor)
            return
        if ev.button() == QtCore.Qt.LeftButton and self._rb is not None and self._rb_origin is not None:
            r = QtCore.QRect(self._rb_origin, ev.pos()).normalized()
            self._rb.hide(); self._rb_origin = None
            p0 = self.mapToScene(r.topLeft()); p1 = self.mapToScene(r.bottomRight())
            if r.width() < 5 and r.height() < 5:      # 视为点选
                self.clickSelect.emit(p0.x(), p0.y())
            else:
                self.boxSelected.emit(p0.x(), p0.y(), p1.x(), p1.y())
            return
        super().mouseReleaseEvent(ev)

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    # ---- 绘制 ----
    def render_all(self, drawing, project, selected=None):
        self.scene_.clear()
        self._marker = None
        # 底图
        if drawing:
            pen_u = QtGui.QPen(QtGui.QColor("#c4ccd6")); pen_u.setCosmetic(True)
            for (x1, y1, x2, y2) in drawing.lines:
                self.scene_.addLine(x1, y1, x2, y2, pen_u)
            br_u = QtGui.QBrush(QtGui.QColor("#c4ccd6"))
            for (x, y) in drawing.points:
                self.scene_.addEllipse(x - 40, y - 40, 80, 80, QtGui.QPen(QtCore.Qt.NoPen), br_u)
        # 楼板（半透明填充，置于最底层）
        br_s = QtGui.QBrush(QtGui.QColor(120, 170, 230, 55))
        pen_s = QtGui.QPen(QtGui.QColor(70, 120, 190)); pen_s.setCosmetic(True)
        pen_s.setStyle(QtCore.Qt.DashLine)
        for s in getattr(project.edit_floor(), "slabs", []):
            x0s = min(s.x1, s.x2); y0s = min(s.y1, s.y2)
            self.scene_.addRect(x0s, y0s, abs(s.x2 - s.x1), abs(s.y2 - s.y1), pen_s, br_s)
        # 板洞(打孔)：白底 + 对角斜线，盖住板表示开洞
        br_o = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        pen_o = QtGui.QPen(QtGui.QColor(200, 60, 60)); pen_o.setCosmetic(True)
        for o in getattr(project.edit_floor(), "openings", []):
            ox = min(o.x1, o.x2); oy = min(o.y1, o.y2); ow = abs(o.x2 - o.x1); oh = abs(o.y2 - o.y1)
            self.scene_.addRect(ox, oy, ow, oh, pen_o, br_o)
            self.scene_.addLine(ox, oy, ox + ow, oy + oh, pen_o)
            self.scene_.addLine(ox, oy + oh, ox + ow, oy, pen_o)
        # 楼梯布置：淡色区 + 踏步线 + 上行箭头
        br_st = QtGui.QBrush(QtGui.QColor(180, 210, 180, 90))
        pen_st = QtGui.QPen(QtGui.QColor(60, 130, 60)); pen_st.setCosmetic(True)
        for s in getattr(project.edit_floor(), "stairs_placed", []):
            sx = min(s.x1, s.x2); sy = min(s.y1, s.y2); sw = abs(s.x2 - s.x1); sh = abs(s.y2 - s.y1)
            self.scene_.addRect(sx, sy, sw, sh, pen_st, br_st)
            n = 8
            if s.run == "x":
                for i in range(1, n):
                    xx = sx + sw * i / n
                    self.scene_.addLine(xx, sy, xx, sy + sh, pen_st)
                self.scene_.addLine(sx + sw * 0.1, sy + sh / 2, sx + sw * 0.9, sy + sh / 2, pen_st)
            else:
                for i in range(1, n):
                    yy = sy + sh * i / n
                    self.scene_.addLine(sx, yy, sx + sw, yy, pen_st)
                self.scene_.addLine(sx + sw / 2, sy + sh * 0.1, sx + sw / 2, sy + sh * 0.9, pen_st)
        # 轴网
        pen_g = QtGui.QPen(QtGui.QColor("#e6b800")); pen_g.setCosmetic(True)
        pen_g.setStyle(QtCore.Qt.DashLine)
        gx = project.grid.x; gy = project.grid.y
        if gx and gy:
            y0, y1 = min(gy), max(gy); x0, x1 = min(gx), max(gx)
            for x in gx:
                self.scene_.addLine(x, y0, x, y1, pen_g)
            for y in gy:
                self.scene_.addLine(x0, y, x1, y, pen_g)
        # 梁
        pen_b = QtGui.QPen(QtGui.QColor("#1a9e5a")); pen_b.setCosmetic(True); pen_b.setWidth(2)
        for b in project.edit_floor().beams:
            self.scene_.addLine(b.x1, b.y1, b.x2, b.y2, pen_b)
        # 墙
        pen_w = QtGui.QPen(QtGui.QColor("#1f6feb")); pen_w.setCosmetic(True); pen_w.setWidth(6)
        for w in project.edit_floor().walls:
            self.scene_.addLine(w.x1, w.y1, w.x2, w.y2, pen_w)
        # 墙洞/结构洞：白色粗线盖住墙(表示开洞) + 红色端线
        pen_wo = QtGui.QPen(QtGui.QColor("#ffffff")); pen_wo.setCosmetic(True); pen_wo.setWidth(6)
        pen_woe = QtGui.QPen(QtGui.QColor("#cf222e")); pen_woe.setCosmetic(True); pen_woe.setWidth(2)
        for o in getattr(project.edit_floor(), "wall_openings", []):
            self.scene_.addLine(o.x1, o.y1, o.x2, o.y2, pen_wo)
            dx, dy = o.x2 - o.x1, o.y2 - o.y1; L = (dx * dx + dy * dy) ** 0.5 or 1.0
            nx, ny = -dy / L * 120, dx / L * 120
            self.scene_.addLine(o.x1 + nx, o.y1 + ny, o.x1 - nx, o.y1 - ny, pen_woe)
            self.scene_.addLine(o.x2 + nx, o.y2 + ny, o.x2 - nx, o.y2 - ny, pen_woe)
        # 柱
        br_c = QtGui.QBrush(QtGui.QColor("#d83a3a"))
        pen_c = QtGui.QPen(QtGui.QColor("#a01f1f")); pen_c.setCosmetic(True)
        for c in project.edit_floor().columns:
            self.scene_.addRect(c.x - c.b / 2, c.y - c.h / 2, c.b, c.h, pen_c, br_c)
        # 结构缝：橙色双虚线
        pen_j = QtGui.QPen(QtGui.QColor("#ff8c00")); pen_j.setCosmetic(True); pen_j.setWidth(2)
        pen_j.setStyle(QtCore.Qt.DashLine)
        for j in getattr(project, "joints", []):
            dx, dy = j.x2 - j.x1, j.y2 - j.y1
            L = (dx * dx + dy * dy) ** 0.5 or 1.0
            ox, oy = -dy / L * j.width / 2, dx / L * j.width / 2
            self.scene_.addLine(j.x1 + ox, j.y1 + oy, j.x2 + ox, j.y2 + oy, pen_j)
            self.scene_.addLine(j.x1 - ox, j.y1 - oy, j.x2 - ox, j.y2 - oy, pen_j)
        # 选中高亮
        if selected:
            ph = QtGui.QPen(QtGui.QColor("#ff00ff")); ph.setCosmetic(True); ph.setWidth(3)
            for (kind, idx) in selected:
                try:
                    if kind == "col":
                        c = project.edit_floor().columns[idx]
                        self.scene_.addRect(c.x - c.b / 2, c.y - c.h / 2, c.b, c.h, ph)
                    elif kind == "beam":
                        b = project.edit_floor().beams[idx]
                        self.scene_.addLine(b.x1, b.y1, b.x2, b.y2, ph)
                    elif kind == "wall":
                        w = project.edit_floor().walls[idx]
                        self.scene_.addLine(w.x1, w.y1, w.x2, w.y2, ph)
                    elif kind == "wopen":
                        o = project.edit_floor().wall_openings[idx]
                        self.scene_.addLine(o.x1, o.y1, o.x2, o.y2, ph)
                    elif kind in ("slab", "open", "stairp"):
                        lst = {"slab": project.edit_floor().slabs, "open": project.edit_floor().openings,
                               "stairp": project.edit_floor().stairs_placed}[kind]
                        s = lst[idx]
                        self.scene_.addRect(min(s.x1, s.x2), min(s.y1, s.y2),
                                            abs(s.x2 - s.x1), abs(s.y2 - s.y1), ph)
                except IndexError:
                    pass
        # 拼接检验问题点：红圈警示
        if self._issues:
            pen_i = QtGui.QPen(QtGui.QColor("#ff1744")); pen_i.setCosmetic(True); pen_i.setWidth(3)
            for (x, y) in self._issues:
                self.scene_.addEllipse(x - 500, y - 500, 1000, 1000, pen_i)
                self.scene_.addLine(x - 700, y, x + 700, y, pen_i)
                self.scene_.addLine(x, y - 700, x, y + 700, pen_i)
        self.setSceneRect(self.scene_.itemsBoundingRect().adjusted(-2000, -2000, 2000, 2000))

    def set_pending(self, pt):
        self._pending = pt

    def pending(self):
        return self._pending

    def fit(self):
        r = self.scene_.itemsBoundingRect()
        if not r.isNull():
            self.fitInView(r.adjusted(-1000, -1000, 1000, 1000), QtCore.Qt.KeepAspectRatio)
