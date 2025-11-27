# gui.py
"""
ScreenRegionMarker 图形界面模块

使用 Tkinter + pyautogui 实现：
- 获取单点坐标
- 获取范围坐标（两次捕获）
- 保存范围坐标到 JSON
- 选择已保存的范围，并显示 / 高亮范围坐标
- 通过“应用窗口设置”控制主窗口的位置和大小，并在保存后锁定窗口
"""

import tkinter as tk
from tkinter import ttk, messagebox

import json
import os

import pyautogui

from backend import (
    Region,
    load_regions,
    save_regions,
    create_region_from_points,
    format_region,
    get_region_by_name,
    DEFAULT_STORAGE_FILE,
)

# ---------------- 窗口配置相关 ---------------- #

# 窗口配置文件放在 app 目录下
WINDOW_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "window_config.json",
)

# 默认窗口参数：left=-9, top=0, width=780, height=991
DEFAULT_WINDOW_CONFIG = {
    "left": -9,
    "top": 0,
    "width": 780,
    "height": 991,
}


def _to_int_safe(value, default):
    try:
        return int(value)
    except Exception:
        return default


def load_window_config() -> dict:
    """
    加载窗口位置和大小配置，不存在或错误时使用默认值。
    """
    config = DEFAULT_WINDOW_CONFIG.copy()
    if os.path.exists(WINDOW_CONFIG_FILE):
        try:
            with open(WINDOW_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key in ("left", "top", "width", "height"):
                    if key in data:
                        config[key] = _to_int_safe(data[key], config[key])
        except Exception:
            # 解析失败时直接使用默认值
            pass
    return config


def save_window_config(config: dict) -> None:
    """
    持久化窗口位置和大小配置到 JSON 文件。
    """
    data = {
        "left": _to_int_safe(config.get("left"), DEFAULT_WINDOW_CONFIG["left"]),
        "top": _to_int_safe(config.get("top"), DEFAULT_WINDOW_CONFIG["top"]),
        "width": _to_int_safe(config.get("width"), DEFAULT_WINDOW_CONFIG["width"]),
        "height": _to_int_safe(config.get("height"), DEFAULT_WINDOW_CONFIG["height"]),
    }
    with open(WINDOW_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class ScreenRegionMarkerApp:
    def __init__(self, root: tk.Tk, window_config=None):
        self.root = root
        self.root.title("ScreenRegionMarker - 屏幕区域标记器")

        # PyAutoGUI 设置（保留 failsafe，防止卡死）
        pyautogui.FAILSAFE = True

        # 窗口配置（位置 + 大小）
        self.window_config = (window_config or DEFAULT_WINDOW_CONFIG).copy()

        # 窗口锁定相关状态
        # _window_locked 为 True 时，不允许通过拖动或拉伸改变窗口位置和大小
        self._window_locked = True  # 启动时即按照配置锁定
        # _updating_geometry 用来避免我们主动调用 geometry 时反复触发 Configure 递归
        self._updating_geometry = False

        # 绑定窗口配置变化事件
        self.root.bind("<Configure>", self._on_root_configure)

        # 数据
        self.regions = load_regions(DEFAULT_STORAGE_FILE)
        self.current_region = None  # type: Region | None

        # 状态变量（用于界面显示）
        self.single_point_var = tk.StringVar(value="(尚未捕获)")
        self.range_step1_var = tk.StringVar(value="第一点：未捕获")
        self.range_step2_var = tk.StringVar(value="第二点：未捕获")
        self.range_result_var = tk.StringVar(value="范围：未计算")
        self.status_var = tk.StringVar(value="欢迎使用 ScreenRegionMarker。")
        self.range_name_var = tk.StringVar()
        self.saved_region_var = tk.StringVar(value="未选择范围。")

        # 窗口设置相关变量（可在“应用窗口设置”中修改）
        self.window_left_var = tk.StringVar(value=str(self.window_config["left"]))
        self.window_top_var = tk.StringVar(value=str(self.window_config["top"]))
        self.window_width_var = tk.StringVar(value=str(self.window_config["width"]))
        self.window_height_var = tk.StringVar(value=str(self.window_config["height"]))

        # UI
        self._create_widgets()

    # ---------------- UI 构建 ---------------- #

    def _create_widgets(self):
        # 主容器
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 单点捕获区域
        single_frame = ttk.LabelFrame(main_frame, text="获取指定位置坐标（单点）", padding=10)
        single_frame.pack(fill=tk.X, pady=5)

        ttk.Label(single_frame, text="当前单点坐标：").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(single_frame, textvariable=self.single_point_var).grid(
            row=0,
            column=1,
            sticky=tk.W,
        )

        self.btn_capture_single = ttk.Button(
            single_frame,
            text="捕获单点坐标（3秒后）",
            command=self.capture_single_point,
        )
        self.btn_capture_single.grid(row=1, column=0, columnspan=2, pady=5, sticky=tk.W)

        ttk.Label(
            single_frame,
            text="提示：点击按钮后，3 秒内将鼠标移动到你想要获取的屏幕位置。",
            foreground="gray",
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        # 范围捕获区域
        range_frame = ttk.LabelFrame(main_frame, text="指定范围坐标（两次捕获）", padding=10)
        range_frame.pack(fill=tk.X, pady=5)

        ttk.Label(range_frame, textvariable=self.range_step1_var).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky=tk.W,
        )
        ttk.Label(range_frame, textvariable=self.range_step2_var).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky=tk.W,
        )
        ttk.Label(range_frame, textvariable=self.range_result_var).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(5, 0),
        )

        self.btn_capture_range = ttk.Button(
            range_frame,
            text="捕获范围（第一点→第二点）",
            command=self.capture_range,
        )
        self.btn_capture_range.grid(
            row=3,
            column=0,
            columnspan=2,
            pady=5,
            sticky=tk.W,
        )

        ttk.Label(
            range_frame,
            text="提示：先捕获左上角（或任意一角），再捕获对角位置。",
            foreground="gray",
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        # 保存范围
        save_frame = ttk.LabelFrame(main_frame, text="保存范围坐标", padding=10)
        save_frame.pack(fill=tk.X, pady=5)

        ttk.Label(save_frame, text="范围名称：").grid(row=0, column=0, sticky=tk.W)
        name_entry = ttk.Entry(save_frame, textvariable=self.range_name_var, width=30)
        name_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 5))

        btn_save_region = ttk.Button(
            save_frame,
            text="保存当前范围",
            command=self.save_current_region,
        )
        btn_save_region.grid(row=0, column=2, sticky=tk.W)

        ttk.Label(
            save_frame,
            text="（例如：状态栏、按钮区域、左上 200x200 等）",
            foreground="gray",
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        # 选择已保存范围
        saved_frame = ttk.LabelFrame(main_frame, text="选择已保存的范围并显示坐标", padding=10)
        saved_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        saved_frame.columnconfigure(1, weight=1)

        ttk.Label(saved_frame, text="已保存的范围：").grid(row=0, column=0, sticky=tk.W)

        self.region_selector = ttk.Combobox(
            saved_frame,
            state="readonly",
        )
        self.region_selector.grid(row=0, column=1, sticky=tk.EW)
        self.region_selector.bind("<<ComboboxSelected>>", self.on_select_saved_region)

        btn_refresh = ttk.Button(
            saved_frame,
            text="刷新列表",
            command=self.refresh_region_list,
        )
        btn_refresh.grid(row=0, column=2, sticky=tk.W, padx=(5, 0))

        btn_show_region = ttk.Button(
            saved_frame,
            text="显示覆盖范围",
            command=self.show_selected_region_overlay,
        )
        btn_show_region.grid(row=0, column=3, sticky=tk.W, padx=(5, 0))

        btn_delete_region = ttk.Button(
            saved_frame,
            text="删除所选范围",
            command=self.delete_selected_region,
        )
        btn_delete_region.grid(row=0, column=4, sticky=tk.W, padx=(5, 0))

        ttk.Label(saved_frame, text="当前选择的范围坐标：").grid(
            row=1,
            column=0,
            sticky=tk.NW,
            pady=(10, 0),
        )
        ttk.Label(
            saved_frame,
            textvariable=self.saved_region_var,
            anchor="w",
        ).grid(
            row=1,
            column=1,
            columnspan=4,
            sticky=tk.W,
            pady=(10, 0),
        )

        # 窗口设置区域
        settings_frame = ttk.LabelFrame(main_frame, text="应用窗口设置", padding=10)
        settings_frame.pack(fill=tk.X, pady=5)

        ttk.Label(settings_frame, text="left：").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(
            settings_frame,
            textvariable=self.window_left_var,
            width=8,
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

        ttk.Label(settings_frame, text="top：").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(
            settings_frame,
            textvariable=self.window_top_var,
            width=8,
        ).grid(row=0, column=3, sticky=tk.W, padx=(0, 10))

        ttk.Label(settings_frame, text="width：").grid(
            row=1,
            column=0,
            sticky=tk.W,
            pady=(5, 0),
        )
        ttk.Entry(
            settings_frame,
            textvariable=self.window_width_var,
            width=8,
        ).grid(
            row=1,
            column=1,
            sticky=tk.W,
            padx=(0, 10),
            pady=(5, 0),
        )

        ttk.Label(settings_frame, text="height：").grid(
            row=1,
            column=2,
            sticky=tk.W,
            pady=(5, 0),
        )
        ttk.Entry(
            settings_frame,
            textvariable=self.window_height_var,
            width=8,
        ).grid(
            row=1,
            column=3,
            sticky=tk.W,
            padx=(0, 10),
            pady=(5, 0),
        )

        ttk.Button(
            settings_frame,
            text="保存窗口设置并锁定",
            command=self.apply_window_settings,
        ).grid(row=0, column=4, rowspan=2, sticky=tk.NW, padx=(10, 0))

        ttk.Label(
            settings_frame,
            text=(
                "说明：保存后窗口会按照上述参数定位，并禁止通过边框改变大小和位置（仍可最小化）。"
                " 如需调整，请修改参数后再次保存。"
            ),
            foreground="gray",
            wraplength=500,
        ).grid(row=2, column=0, columnspan=5, sticky=tk.W, pady=(8, 0))

        # 状态栏
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(5, 2),
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 初始化下拉框
        self.refresh_region_list()

    # ---------------- 功能逻辑 ---------------- #

    def set_status(self, text: str):
        self.status_var.set(text)

    # --- 单点捕获 --- #

    def capture_single_point(self):
        """
        捕获单点坐标（3 秒倒计时）
        """
        self.set_status("单点捕获即将开始，请在 3 秒内将鼠标移动到目标位置。")
        self.btn_capture_single.config(state=tk.DISABLED)
        self._single_point_countdown(3)

    def _single_point_countdown(self, seconds_left: int):
        if seconds_left > 0:
            self.set_status(
                f"将在 {seconds_left} 秒后捕获单点坐标，请把鼠标移动到目标位置。"
            )
            self.root.after(1000, self._single_point_countdown, seconds_left - 1)
        else:
            # 倒计时结束，读取鼠标位置
            x, y = pyautogui.position()
            self.single_point_var.set(f"({x}, {y})")
            self.set_status(f"单点坐标已捕获：({x}, {y})")
            self.btn_capture_single.config(state=tk.NORMAL)

    # --- 范围捕获 --- #

    def capture_range(self):
        """
        分两次捕获范围：第一点和第二点
        """
        self.set_status(
            "范围捕获即将开始，先捕获第一点（如左上角）。3 秒内移动鼠标到第一点。"
        )
        self.btn_capture_range.config(state=tk.DISABLED)
        self.range_step1_var.set("第一点：准备捕获中…")
        self.range_step2_var.set("第二点：未捕获")
        self.range_result_var.set("范围：未计算")
        self._range_first_point = None  # 内部记录第一点
        self._range_countdown_first(3)

    def _range_countdown_first(self, seconds_left: int):
        if seconds_left > 0:
            self.set_status(
                f"将在 {seconds_left} 秒后捕获第一点，请移动鼠标到范围的一角（建议左上角）。"
            )
            self.root.after(1000, self._range_countdown_first, seconds_left - 1)
        else:
            x1, y1 = pyautogui.position()
            self._range_first_point = (x1, y1)
            self.range_step1_var.set(f"第一点：({x1}, {y1})")
            self.set_status(
                "第一点已捕获，请在 3 秒内移动鼠标到对角位置（如右下角），将捕获第二点。"
            )
            self._range_countdown_second(3)

    def _range_countdown_second(self, seconds_left: int):
        if seconds_left > 0:
            self.set_status(
                f"将在 {seconds_left} 秒后捕获第二点，请移动鼠标到范围的对角位置。({seconds_left})"
            )
            self.root.after(1000, self._range_countdown_second, seconds_left - 1)
        else:
            x2, y2 = pyautogui.position()
            self.range_step2_var.set(f"第二点：({x2}, {y2})")

            if self._range_first_point is None:
                self.set_status("第一点丢失，范围捕获失败，请重试。")
                self.btn_capture_range.config(state=tk.NORMAL)
                return

            x1, y1 = self._range_first_point
            # 临时名称，真正保存时用户会填写
            temp_name = self.range_name_var.get().strip() or "未命名范围"
            region = create_region_from_points(temp_name, x1, y1, x2, y2)
            self.current_region = region

            self.range_result_var.set(
                f"范围：left={region.left}, top={region.top}, "
                f"width={region.width}, height={region.height}"
            )
            self.set_status("范围已捕获，可为其命名并点击“保存当前范围”。")
            self.btn_capture_range.config(state=tk.NORMAL)

    # --- 保存 / 加载范围 --- #

    def save_current_region(self):
        """
        将 current_region 以指定名称保存到 JSON 并刷新列表
        """
        if self.current_region is None:
            messagebox.showwarning("没有范围", "当前没有可保存的范围，请先捕获范围。")
            return

        name = self.range_name_var.get().strip()
        if not name:
            messagebox.showwarning("名称为空", "请先为范围输入一个名称。")
            return

        # 使用当前名称创建一个新的 Region（覆盖原来的临时名称）
        region = Region(
            name=name,
            left=self.current_region.left,
            top=self.current_region.top,
            width=self.current_region.width,
            height=self.current_region.height,
        )

        # 覆盖或新增（如果之前被软删除，会自动恢复）
        self.regions[name] = region
        try:
            save_regions(self.regions, DEFAULT_STORAGE_FILE)
        except Exception as e:
            messagebox.showerror("保存失败", f"保存到文件时出错：\n{e}")
            return

        self.set_status(f"范围“{name}”已保存。")
        self.refresh_region_list(select_name=name)

    def refresh_region_list(self, select_name: str | None = None):
        """
        刷新下拉框中的范围列表（只显示未软删除的）
        """
        names = [
            name
            for name, region in self.regions.items()
            if not getattr(region, "deleted", False)
        ]
        names.sort()
        self.region_selector["values"] = names

        if select_name and select_name in names:
            self.region_selector.set(select_name)
            self.on_select_saved_region()
        elif names:
            # 如果没有指定要选的，就默认选第一个
            self.region_selector.set(names[0])
            self.on_select_saved_region()
        else:
            self.region_selector.set("")
            self.saved_region_var.set("未选择范围。")

    def on_select_saved_region(self, event=None):
        """
        当用户在下拉框中选择一个范围时，显示其坐标
        """
        name = self.region_selector.get().strip()
        if not name:
            return

        region = get_region_by_name(self.regions, name)
        if not region or getattr(region, "deleted", False):
            self.saved_region_var.set("未找到该范围。")
            return

        self.saved_region_var.set(format_region(region))
        self.set_status(f"已选择范围“{name}”。")

    # --- 显示覆盖范围 / 软删除 --- #

    def show_selected_region_overlay(self):
        """
        用一个半透明方块在屏幕上高亮显示当前选择的范围
        """
        name = self.region_selector.get().strip()
        if not name:
            messagebox.showinfo("未选择范围", "请先在下拉列表中选择一个范围。")
            return

        region = get_region_by_name(self.regions, name)
        if not region or getattr(region, "deleted", False):
            messagebox.showwarning("范围不存在", "所选范围不存在或已被删除。")
            self.refresh_region_list()
            return

        # 创建覆盖窗口
        overlay = tk.Toplevel(self.root)
        overlay.title(f"区域预览 - {name}")
        overlay.overrideredirect(True)  # 无边框
        overlay.attributes("-topmost", True)  # 置顶

        # 半透明背景颜色
        try:
            overlay.attributes("-alpha", 0.3)
        except tk.TclError:
            # 部分平台可能不支持 alpha
            pass

        overlay.configure(bg="red")

        width = max(int(region.width), 1)
        height = max(int(region.height), 1)
        left = int(region.left)
        top = int(region.top)

        overlay.geometry(f"{width}x{height}+{left}+{top}")

        # 简单的提示文本
        label = tk.Label(
            overlay,
            text=name,
            bg="red",
            fg="white",
        )
        label.pack(fill=tk.BOTH, expand=True)

        # 点击或 2 秒后关闭
        overlay.bind("<Button-1>", lambda e: overlay.destroy())
        overlay.bind("<Escape>", lambda e: overlay.destroy())
        overlay.after(2000, overlay.destroy)

        self.set_status(f"已在屏幕上高亮显示范围“{name}”（点击红框或 2 秒后自动关闭）。")

    def delete_selected_region(self):
        """
        将当前选择的范围软删除，并持久化到文件
        """
        name = self.region_selector.get().strip()
        if not name:
            messagebox.showinfo("未选择范围", "请先在下拉列表中选择一个范围。")
            return

        region = get_region_by_name(self.regions, name)
        if not region:
            messagebox.showwarning("范围不存在", "所选范围不存在。")
            self.refresh_region_list()
            return

        if getattr(region, "deleted", False):
            messagebox.showinfo("已删除", "该范围已经被删除。")
            return

        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除范围“{name}”吗？\n删除后将不会在列表中显示（软删除，可在数据文件中恢复）。",
        ):
            return

        region.deleted = True

        try:
            save_regions(self.regions, DEFAULT_STORAGE_FILE)
        except Exception as e:
            region.deleted = False
            messagebox.showerror("删除失败", f"保存到文件时出错：\n{e}")
            return

        self.set_status(f"范围“{name}”已删除。")
        self.refresh_region_list()

    # --- 应用窗口设置 & 锁定逻辑 --- #

    def apply_window_settings(self):
        """
        从“应用窗口设置”读取窗口参数，保存到配置文件并锁定窗口位置和大小。
        """
        try:
            left = int(self.window_left_var.get().strip())
            top = int(self.window_top_var.get().strip())
            width = int(self.window_width_var.get().strip())
            height = int(self.window_height_var.get().strip())
        except ValueError:
            messagebox.showerror("输入错误", "窗口参数必须是整数，请检查后重新输入。")
            return

        if width <= 0 or height <= 0:
            messagebox.showerror("输入错误", "width 和 height 必须为正整数。")
            return

        # 更新内存中的配置
        self.window_config["left"] = left
        self.window_config["top"] = top
        self.window_config["width"] = width
        self.window_config["height"] = height

        # 持久化
        try:
            save_window_config(self.window_config)
        except Exception as e:
            messagebox.showerror("保存失败", f"保存窗口配置时出错：\n{e}")
            return

        geometry_str = f"{width}x{height}+{left}+{top}"

        # 只在窗口为 normal 状态时强制应用几何（最小化时不干预）
        if self.root.state() == "normal":
            self._updating_geometry = True
            try:
                self.root.geometry(geometry_str)
            finally:
                self._updating_geometry = False

        # 禁止通过边框改变大小
        self.root.resizable(False, False)

        # 打开锁定标记：后续任何拖动或尝试改变大小都会被还原
        self._window_locked = True

        self.set_status(
            "窗口设置已保存并锁定。若需调整，请在“应用窗口设置”中修改参数后再次保存。"
        )

    def _on_root_configure(self, event):
        """
        当主窗口尺寸或位置变化时的回调。

        在 _window_locked 为 True 时，如果当前几何与配置不一致，
        则自动恢复到配置指定的位置和大小，从而禁止通过拖拽或拉伸改变窗口。
        """
        # 未锁定时放行
        if not self._window_locked:
            return

        # 避免我们主动调用 geometry 导致的递归
        if self._updating_geometry:
            return

        # 只在 normal 状态下约束位置和大小，最小化 / 最大化状态不干预
        state = self.root.state()
        if state != "normal":
            return

        current_geometry = self.root.geometry()
        desired_geometry = (
            f'{int(self.window_config["width"])}x{int(self.window_config["height"])}'
            f'+{int(self.window_config["left"])}+{int(self.window_config["top"])}'
        )

        if current_geometry != desired_geometry:
            self._updating_geometry = True
            try:
                self.root.geometry(desired_geometry)
            finally:
                self._updating_geometry = False


def run_app():
    root = tk.Tk()

    # 先加载窗口配置（默认：left=0, top=1, width=780, height=1025）
    window_config = load_window_config()
    geometry_str = (
        f'{int(window_config["width"])}x{int(window_config["height"])}'
        f'+{int(window_config["left"])}+{int(window_config["top"])}'
    )

    # 设置初始几何
    root.geometry(geometry_str)

    # 启动时就禁止通过边框改变大小（位置由 _on_root_configure 负责锁定）
    root.resizable(False, False)

    app = ScreenRegionMarkerApp(root, window_config=window_config)
    root.mainloop()
