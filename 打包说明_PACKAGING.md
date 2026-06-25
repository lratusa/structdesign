# structdesign 建模器 — Windows 打包/分发说明

把桌面建模器打包成**免安装 exe / 便携 zip / 安装包 setup.exe**，发给试用人员（其电脑无需装 Python）。

## 一键构建
```bat
build_installer.bat
```
该脚本依次：① PyInstaller 生成免安装程序 → ② 压缩便携版 zip → ③（若装了 Inno Setup）生成 setup.exe。

> 必须用装了依赖的 `python`(=3.9.7，含 PyQt5/numpy/matplotlib/ezdxf/plotly + PyInstaller)。

## 产物（任选其一发给试用人员）
1. **★ 安装版 zip（推荐发这个）**：`dist\structdesign_modeler_安装版.zip`
   —— 对方解压后双击「安装.bat」，**免管理员**安装到当前用户目录 + 桌面/开始菜单快捷方式；卸载用「卸载.bat」。
   已实测：安装后程序自检（分析→配筋图→3D→计算书）通过。
2. **便携 zip**：`dist\structdesign_modeler_portable.zip`
   —— 解压后直接双击里面的 `structdesign_modeler.exe` 运行（不安装）。
3. **免安装目录**：`dist\structdesign_modeler\`（同上，未压缩）。
4. **正式安装包 setup.exe**：`Output\structdesign_modeler_setup.exe`
   —— 更专业的单文件安装包，**需 [Inno Setup 6](https://jrsoftware.org/isdl.php)**：在你自己的电脑上装一次 Inno
   （安装时点一下 UAC 允许即可），再运行 `build_installer.bat` 或编译 `installer.iss` 即生成。
   （注：自动化构建环境无法点 UAC，故 setup.exe 需在你本机生成；安装版 zip 已可直接发测试。）

## 健康自检
安装/解压后命令行运行：`structdesign_modeler.exe --selftest`
跑通分析+配筋图+3D+计算书后，在 `用户目录\structdesign_work\_selftest\` 写 `SELFTEST_OK.txt`（失败写 `SELFTEST_FAIL.txt` 含堆栈）。

## 单独步骤
```bat
:: 只生成免安装程序
python -m PyInstaller structdesign_modeler.spec --noconfirm

:: 只生成 setup.exe（已有 dist\ 后）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

## 文件
- `structdesign_modeler.spec` —— PyInstaller 规格（已含 plotly/ezdxf/matplotlib 数据、structdesign/modeler 全子模块、PyQt5 等隐藏导入）。
- `installer.iss` —— Inno Setup 安装包脚本（中文界面、桌面快捷方式、卸载）。
- `build_installer.bat` —— 一键构建。

## 试用人员使用须知（随包附上）
- 打开后：导入图纸/一键轴网 → 建模（含撤销/复制/镜像/阵列）→ 🤖自动优化设计 → 看指标/3D视图 →
  📐配筋图 / 🏗基础图 / 🪜楼梯图 / 📄计算书。
- **输出位置**：程序产物（计算书、各种图）写到 `C:\Users\<用户名>\structdesign_work\`；出图/计算书也会弹文件对话框可另存。
- **可选外部工具**（缺了不影响核心功能，但相应输出会跳过）：
  - `pandoc`：把计算书转成 **Word(.docx)**；没装则只出 Markdown。
  - `ODA File Converter`：直接导入**原生 .dwg**；没装则请用 **.dxf**。
- 研发原型，结果须注册结构工程师复核签字。

## 已知打包要点（维护备查）
- `app.py` 中 `OUT_DIR`：打包(frozen)后写到 `~/structdesign_work`（Program Files 只读）。
- plotly 出 HTML 用 `include_plotlyjs=True`（内嵌，离线可看）；故 spec 必须 `collect_all('plotly')`。
- ezdxf 渲染/odafc、matplotlib Agg/3D 已列入 hiddenimports。
- 很多 import 在函数内惰性触发，故 spec 用 `collect_submodules('structdesign'/'modeler')` 全收。
