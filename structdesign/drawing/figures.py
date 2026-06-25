"""
计算书插图（matplotlib → PNG，供 Word 嵌入）。

  - axon_png：三维模型轴测图（墙/柱/梁着色）。
  - section_png：构件截面配筋大样（纵筋点位 + 箍筋 + 尺寸）。
"""
from __future__ import annotations
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa
from matplotlib.patches import Rectangle, Circle

plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def axon_png(model, path, title="3D Model"):
    """三维框架轴测图。"""
    fig = plt.figure(figsize=(6.4, 6.0))
    ax = fig.add_subplot(111, projection="3d")
    for m in model.members.values():
        ni, nj = model.nodes[m.ni], model.nodes[m.nj]
        xs = [ni.x/1000, nj.x/1000]; ys = [ni.y/1000, nj.y/1000]; zs = [ni.z/1000, nj.z/1000]
        if max(m.Iy, m.Iz) > 5e10:
            c, lw = "#c0392b", 2.4           # 墙
        elif m.id.startswith("Z"):
            c, lw = "#34495e", 1.2           # 柱
        else:
            c, lw = "#5dade2", 0.6           # 梁
        ax.plot(xs, ys, zs, color=c, linewidth=lw)
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
    ax.set_title(title)
    try:
        ax.set_box_aspect((1, 1, 1.4))
    except Exception:
        pass
    ax.view_init(elev=18, azim=-55)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def section_png(b, h, n_top, n_bot, d_main, stirrup_d, path,
                title="Section", cover=30, n_side=0):
    """矩形截面配筋大样（mm）。"""
    fig, ax = plt.subplots(figsize=(3.6, 3.6 * h / b if h >= b else 3.6))
    ax.add_patch(Rectangle((0, 0), b, h, fill=False, lw=2, ec="black"))
    c = cover
    ax.add_patch(Rectangle((c, c), b-2*c, h-2*c, fill=False, lw=1.2, ec="#c0392b"))
    r = max(d_main/2, 6)

    def row(n, yy, color):
        if n <= 0:
            return
        xs0, xs1 = c + r, b - c - r
        for i in range(n):
            xx = xs0 if n == 1 else xs0 + (xs1 - xs0) * i / (n - 1)
            ax.add_patch(Circle((xx, yy), r, color=color))
    row(n_top, h - c - r, "#2c3e50")
    row(n_bot, c + r, "#c0392b")
    if n_side > 0:
        ys0, ys1 = c + r, h - c - r
        for i in range(1, n_side + 1):
            yy = ys0 + (ys1 - ys0) * i / (n_side + 1)
            ax.add_patch(Circle((c + r, yy), r*0.8, color="#7f8c8d"))
            ax.add_patch(Circle((b - c - r, yy), r*0.8, color="#7f8c8d"))
    ax.set_xlim(-b*0.12, b*1.12); ax.set_ylim(-h*0.12, h*1.12)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{title}  {int(b)}x{int(h)}", fontsize=10)
    ax.text(b/2, -h*0.08, f"{int(b)}", ha="center", fontsize=9)
    ax.text(-b*0.08, h/2, f"{int(h)}", va="center", rotation=90, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def wall_section_png(bw, lw, be_d, n_be, vd_d, path, title="Wall", cover=20):
    """剪力墙墙肢水平截面配筋大样（bw 厚 × lw 长，两端约束/构造边缘构件）。"""
    fig, ax = plt.subplots(figsize=(8.4, 8.4 * bw / lw + 1.2))
    ax.add_patch(Rectangle((0, 0), lw, bw, fill=False, lw=2, ec="black"))
    lc = max(bw, 400)                       # 边缘构件长度(简化)
    for x0 in (0, lw - lc):                 # 两端边缘构件(阴影)
        ax.add_patch(Rectangle((x0, 0), lc, bw, facecolor="#f2d7d5", edgecolor="#c0392b", lw=1.2))
    r = max(be_d/2, 8)
    # 边缘构件纵筋(两排)
    for x0 in (0, lw - lc):
        for col in range(max(n_be//2, 2)):
            xx = x0 + cover + r + col*(lc-2*cover-2*r)/max(n_be//2-1, 1)
            ax.add_patch(Circle((xx, cover+r), r, color="#922b21"))
            ax.add_patch(Circle((xx, bw-cover-r), r, color="#922b21"))
    # 竖向分布筋(双层小点) 沿墙长
    rd = max(vd_d/2, 4)
    x = lc + 200
    while x < lw - lc:
        ax.add_patch(Circle((x, cover+rd), rd, color="#2c3e50"))
        ax.add_patch(Circle((x, bw-cover-rd), rd, color="#2c3e50"))
        x += 200
    ax.set_xlim(-lw*0.04, lw*1.04); ax.set_ylim(-bw*2, bw*3)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{title}  {int(bw)}x{int(lw)}  (boundary {n_be}D{int(be_d)})", fontsize=10)
    ax.annotate("", xy=(0, -bw*0.6), xytext=(lw, -bw*0.6),
                arrowprops=dict(arrowstyle="<->", color="black"))
    ax.text(lw/2, -bw*1.0, f"{int(lw)}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def story_curves_png(profiles_x, profiles_y, drift_limit, path,
                     title="Story Shear & Drift"):
    """沿高度的楼层剪力 V 与层间位移角分布曲线（X/Y）。

    profiles: list[(z, V, U, drift)] 自下而上。
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 5.4))
    fl = list(range(1, len(profiles_x) + 1))   # 楼层号
    Vx = [p[1]/1e3 for p in profiles_x]; Vy = [p[1]/1e3 for p in profiles_y]
    dx = [p[3] for p in profiles_x]; dy = [p[3] for p in profiles_y]

    ax1.step(Vx, fl, where="pre", color="#2c3e50", marker="o", ms=3, label="X")
    ax1.step(Vy, fl, where="pre", color="#c0392b", marker="s", ms=3, label="Y")
    ax1.set_xlabel("Story shear V (kN)"); ax1.set_ylabel("Floor")
    ax1.set_title("Story Shear"); ax1.grid(alpha=0.3); ax1.legend(fontsize=8)

    ax2.plot([1/max(v, 1e-9) for v in dx], fl, color="#2c3e50", marker="o", ms=3, label="X")
    ax2.plot([1/max(v, 1e-9) for v in dy], fl, color="#c0392b", marker="s", ms=3, label="Y")
    lim = 1/drift_limit
    ax2.axvline(lim, color="green", ls="--", lw=1, label=f"limit 1/{lim:.0f}")
    ax2.set_xlabel("Drift ratio (1/x, larger=safer)"); ax2.set_title("Inter-story Drift")
    ax2.grid(alpha=0.3); ax2.legend(fontsize=8)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def floor_plan_png(nx, ny, bx, by, wall_cols, col_b, wall_lw, path, title="Floor Plan"):
    """楼层结构平面简图：柱(方块)、墙(粗块)、梁(细线)、轴线编号。"""
    wall_cols = set(wall_cols or [])
    fig, ax = plt.subplots(figsize=(6.4, 6.4 * (ny*by)/(nx*bx)))
    # 梁(细线)
    for i in range(nx + 1):
        for k in range(ny + 1):
            x, y = i*bx/1000, k*by/1000
            if i < nx:
                ax.plot([x, (i+1)*bx/1000], [y, y], color="#aab", lw=0.8, zorder=1)
            if k < ny:
                ax.plot([x, x], [y, (k+1)*by/1000], color="#aab", lw=0.8, zorder=1)
    # 柱/墙
    cs = col_b/1000
    for i in range(nx + 1):
        for k in range(ny + 1):
            x, y = i*bx/1000, k*by/1000
            if (i, k) in wall_cols:
                ax.add_patch(Rectangle((x-wall_lw/2000, y-0.2), wall_lw/1000, 0.4,
                                       color="#c0392b", zorder=3))
            else:
                ax.add_patch(Rectangle((x-cs/2, y-cs/2), cs, cs, color="#34495e", zorder=3))
    # 轴线编号
    for i in range(nx + 1):
        ax.text(i*bx/1000, -by/1000*0.35, str(i+1), ha="center", fontsize=10)
    for k in range(ny + 1):
        ax.text(-bx/1000*0.35, k*by/1000, chr(ord("A")+k), va="center", fontsize=10)
    ax.set_xlim(-bx/1000*0.6, nx*bx/1000 + bx/1000*0.3)
    ax.set_ylim(-by/1000*0.6, ny*by/1000 + by/1000*0.3)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title, fontsize=11)
    ax.text(nx*bx/2000, ny*by/1000+by/1000*0.15,
            "■ column   ▬ wall   — beam", ha="center", fontsize=8, color="#555")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
