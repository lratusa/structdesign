# -*- coding: utf-8 -*-
"""
structdesign 测试界面 (Flask) —— 浏览器里填参数 → 跑三维一键总流程 → 看结果。

输入参数表单 → design_project_3d(三维分析+配筋) → 结果页：
  规范指标(过/不过) · 自振周期 · 基底剪力 · 构件配筋表 · 5 张工程图 · 专业计算书(在线看/下载 Word)。

本机用 `python`(3.9.7，含 numpy/matplotlib)，不要用 python3。
启动见根目录 run_app.py 或 启动界面.bat。
"""
import sys

# Windows 控制台 UTF-8（图表标题/日志含中文）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import shutil
import subprocess
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, render_template, request, send_from_directory, abort

from structdesign.design_project_3d import design_project_3d

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # 静态文件每次重新校验，避免浏览器缓存旧 CSS/JS

WORK = os.path.join(HERE, "_work")               # design_project_3d 原始产物(中文名)
STATIC_OUT = os.path.join(HERE, "static", "out")  # 复制成 ASCII 名供浏览器访问
os.makedirs(WORK, exist_ok=True)
os.makedirs(STATIC_OUT, exist_ok=True)

# 表单默认值（取自 demo_project_3d.py，一个能跑通且物理合理的算例）
DEFAULTS = dict(
    nx=3, ny=3, nz=12, bx=8000, by=8000, hz=3600,
    col_b=750, col_h=750, beam_b=350, beam_h=750,
    wall=True, wall_b=400, wall_h=4000,
    dead=6.0, live=2.5, alpha_max=0.16, Tg=0.45,
    grade="二级", n_modes=12,
)

GRADES = ["一级", "二级", "三级", "四级"]

# 规模上限：内核为稠密杆系有限元 + Guyan 静凝聚，耗时随节点数陡增
# （实测 208节点≈10s、325≈17s、576≈48s）。超此上限直接拒绝，避免浏览器无限转圈。
MAX_NODES = 400

# design_project_3d 写出的中文图名 → 浏览器用的 ASCII 名
FIG_MAP = [
    ("平面简图.png", "plan.png", "结构平面简图"),
    ("三维模型图.png", "model.png", "三维轴测模型"),
    ("柱大样.png", "col.png", "代表柱配筋大样"),
    ("墙大样.png", "wall.png", "墙肢配筋大样"),
    ("楼层曲线.png", "curves.png", "楼层剪力 / 层间位移角曲线"),
]


def _central_pair(n):
    """grid 线 0..n 中取中央两条，做核心墙位置。"""
    lo = (n - 1) // 2
    return [max(0, lo), min(n, lo + 1)]


def _f(form, key, cast, default):
    raw = form.get(key, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


@app.route("/")
def index():
    return render_template("index.html", d=DEFAULTS, grades=GRADES)


@app.route("/run", methods=["POST"])
def run():
    f = request.form
    p = dict(
        nx=_f(f, "nx", int, 3), ny=_f(f, "ny", int, 3), nz=_f(f, "nz", int, 12),
        bx=_f(f, "bx", float, 8000), by=_f(f, "by", float, 8000), hz=_f(f, "hz", float, 3600),
        col_b=_f(f, "col_b", float, 750), col_h=_f(f, "col_h", float, 750),
        beam_b=_f(f, "beam_b", float, 350), beam_h=_f(f, "beam_h", float, 750),
        wall=(f.get("wall") == "on"),
        wall_b=_f(f, "wall_b", float, 400), wall_h=_f(f, "wall_h", float, 4000),
        dead=_f(f, "dead", float, 6.0), live=_f(f, "live", float, 2.5),
        alpha_max=_f(f, "alpha_max", float, 0.16), Tg=_f(f, "Tg", float, 0.45),
        grade=f.get("grade", "二级"), n_modes=_f(f, "n_modes", int, 12),
    )
    # 护栏：先夹紧到可交互范围，再用节点预算硬拦截（防止界面无限转圈）
    p["nx"] = min(max(p["nx"], 1), 6)
    p["ny"] = min(max(p["ny"], 1), 6)
    p["nz"] = min(max(p["nz"], 1), 20)
    p["n_modes"] = min(max(p["n_modes"], 3), 18)
    if p["grade"] not in GRADES:
        p["grade"] = "二级"

    nodes = (p["nx"] + 1) * (p["ny"] + 1) * (p["nz"] + 1)
    print(f"[run] {p['nx']}x{p['ny']}x{p['nz']} wall={p['wall']} "
          f"modes={p['n_modes']} nodes={nodes}", flush=True)
    if nodes > MAX_NODES:
        return render_template("toolarge.html", p=p, nodes=nodes,
                               max_nodes=MAX_NODES), 200

    wall_cols = set()
    if p["wall"]:
        xs = _central_pair(p["nx"])
        ys = _central_pair(p["ny"])
        wall_cols = {(i, k) for i in xs for k in ys}

    # 清空上次产物，避免旧图残留
    for d in (WORK, STATIC_OUT):
        for fn in os.listdir(d):
            fp = os.path.join(d, fn)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass

    import time as _t
    _t0 = _t.time()
    try:
        out = design_project_3d(
            nx=p["nx"], ny=p["ny"], nz=p["nz"], bx=p["bx"], by=p["by"], hz=p["hz"],
            out_dir=WORK,
            col_bh=(p["col_b"], p["col_h"]), beam_bh=(p["beam_b"], p["beam_h"]),
            wall_cols=wall_cols, wall_bh=(p["wall_b"], p["wall_h"]),
            dead_kpa=p["dead"], live_kpa=p["live"],
            alpha_max=p["alpha_max"], Tg=p["Tg"],
            seismic_grade=p["grade"], n_modes=p["n_modes"],
        )
        print(f"[run] done in {_t.time()-_t0:.1f}s", flush=True)
    except Exception:
        print(f"[run] ERROR after {_t.time()-_t0:.1f}s", flush=True)
        return render_template("error.html", params=p,
                               tb=traceback.format_exc()), 500

    # 图：复制成 ASCII 名
    figs = []
    for zh, ascii_name, caption in FIG_MAP:
        src = os.path.join(WORK, zh)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(STATIC_OUT, ascii_name))
            figs.append((ascii_name, caption))

    # Word 计算书：复制供下载
    docx_src = os.path.join(WORK, "三维计算书.docx")
    has_docx = os.path.exists(docx_src)
    if has_docx:
        shutil.copy(docx_src, os.path.join(STATIC_OUT, "calcbook.docx"))

    # 计算书在线版：pandoc md → 自包含 HTML（图片内嵌），cwd=WORK 让相对图名可解析
    has_html = False
    md_src = os.path.join(WORK, "三维计算书.md")
    if shutil.which("pandoc") and os.path.exists(md_src):
        try:
            subprocess.run(
                ["pandoc", "三维计算书.md", "-o", os.path.join(STATIC_OUT, "calcbook.html"),
                 "--self-contained", "--metadata", "title=结构计算书", "--toc"],
                cwd=WORK, check=True, capture_output=True, timeout=120)
            has_html = True
        except Exception:
            has_html = False

    book = getattr(out, "_book_data", {}) or {}
    members = book.get("members", [])
    cols = [m for m in members if m.get("kind") == "柱"]
    walls = [m for m in members if m.get("kind") == "墙"]
    beams = [m for m in members if m.get("kind") == "梁"]
    checks = book.get("checks_table", [])

    return render_template(
        "result.html", out=out, p=p, wall_cols=sorted(wall_cols),
        checks=checks, cols=cols, walls=walls, beams=beams,
        figs=figs, has_docx=has_docx, has_html=has_html,
    )


@app.route("/download/<path:name>")
def download(name):
    safe = os.path.basename(name)
    fp = os.path.join(STATIC_OUT, safe)
    if not os.path.exists(fp):
        abort(404)
    return send_from_directory(STATIC_OUT, safe, as_attachment=True)


if __name__ == "__main__":
    print("structdesign 测试界面启动中 …  打开 http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
