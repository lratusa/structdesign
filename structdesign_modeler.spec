# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包规格：structdesign 建模器（PyQt5 桌面）。
构建：python -m PyInstaller structdesign_modeler.spec --noconfirm
产物：dist/structdesign_modeler/structdesign_modeler.exe（onedir，免安装 Python 可运行）。
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

datas, binaries, hiddenimports = [], [], []

# ezdxf：整包收集（需字体/数据，且体量小、无重依赖）
try:
    d, b, h = collect_all("ezdxf"); datas += d; binaries += b; hiddenimports += h
except Exception:
    pass

# plotly / matplotlib：只取「数据文件」(plotly 内嵌 plotly.js；matplotlib 字体/样式) +
# 指定关键子模块，**不**整包 collect_submodules —— 否则会牵入 plotly.express→pandas→dask、
# matplotlib.testing 乃至 anaconda 里的 torch 等无关重包。
datas += collect_data_files("plotly")
datas += collect_data_files("matplotlib")
hiddenimports += [
    "plotly.graph_objects", "plotly.io", "plotly.offline", "_plotly_utils",
    "matplotlib.backends.backend_agg", "mpl_toolkits.mplot3d",
]

# 本项目两个包的全部子模块（很多是函数内惰性 import，需显式收集；二者均无重依赖）
for pkg in ("structdesign", "modeler"):
    hiddenimports += collect_submodules(pkg)

hiddenimports += [
    "ezdxf.addons.drawing.matplotlib", "ezdxf.addons.drawing.config",
    "ezdxf.addons.odafc", "PyQt5.QtPrintSupport",
]

a = Analysis(
    ["launch_modeler.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[
        # 本程序仅用 QtWidgets/QtGui/QtCore；排除 WebEngine 等(其 locales 缺失会致命且体积巨大)
        "PyQt5.QtWebEngineWidgets", "PyQt5.QtWebEngineCore", "PyQt5.QtWebEngine",
        "PyQt5.QtWebEngineQuick", "PyQt5.QtWebChannel", "PyQt5.QtQuick", "PyQt5.QtQml",
        "PyQt5.QtMultimedia", "PyQt5.QtBluetooth", "PyQt5.QtDesigner",
        # notebook / 科学栈中本程序用不到的(随 anaconda 被牵连进来的)大件
        "nbconvert", "nbformat", "notebook", "jupyter", "jupyter_core", "jupyter_client",
        "IPython", "ipykernel", "ipywidgets", "tornado", "zmq", "sqlalchemy",
        "dask", "bokeh", "h5py", "xyzservices", "pandas", "scipy", "numba", "numexpr",
        "sphinx", "pytest", "PIL.ImageQt",
        "tkinter", "PyQt6", "PySide2", "PySide6",
        # 重型 ML/科学栈（anaconda 自带但本程序完全用不到）
        "torch", "torchvision", "torchaudio", "tensorflow", "tensorboard", "keras",
        "sympy", "sklearn", "scikit_learn", "cv2", "llvmlite", "statsmodels",
        "seaborn", "pyarrow", "openseespy", "numpy.f2py", "numpy.distutils",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="structdesign_modeler",
    debug=False, strip=False, upx=False, console=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="structdesign_modeler",
)
