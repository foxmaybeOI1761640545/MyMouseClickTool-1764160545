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

        # 鼠标捕获覆盖层相关状态（红色十字准星替代鼠标箭头）
        self._capture_overlay: tk.Toplevel | None = None
        self._capture_canvas: tk.Canvas | None = None
        self._capture_dot_id: int | None = None  # 保留字段，当前用于记录圆点图元
        self._capture_point_callback = None
        self._capture_cancel_callback = None

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

        # 使用一行内部小容器，避免“当前单点坐标”和坐标值之间出现过长间隔
        coord_line = ttk.Frame(single_frame)
        coord_line.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(coord_line, text="当前单点坐标：").pack(side=tk.LEFT)
        ttk.Label(coord_line, textvariable=self.single_point_var).pack(side=tk.LEFT)

        self.btn_capture_single = ttk.Button(
            single_frame,
            text="捕获单点坐标",
            command=self.capture_single_point,
        )
        self.btn_capture_single.grid(row=1, column=0, columnspan=2, pady=5, sticky=tk.W)

        ttk.Label(
            single_frame,
            text="提示：点击按钮后，用鼠标左键单击需要获取坐标的位置（按 Esc 取消）。",
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
            text="提示：先用左键单击选择范围一角（建议左上角），再单击选择对角位置。",
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

        # 调整 wraplength=700，根据控件实际可用宽度自动换行，避免文本显示不全或者超出边界
        ttk.Label(
            settings_frame,
            text=(
                "说明：保存后窗口会按照上述参数定位，并禁止通过边框改变大小和位置（仍可最小化）。"
                " 如需调整，请修改参数后再次保存。"
            ),
            foreground="gray",
            wraplength=700,
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

    # ---------------- 公共工具方法 ---------------- #

    def set_status(self, text: str):
        self.status_var.set(text)

    # --- 鼠标捕获辅助：在全屏透明覆盖层中用十字准星代替鼠标箭头 --- #

    def _end_mouse_capture(self, cancelled: bool = False):
        """
        结束当前的鼠标捕获会话，销毁覆盖层并回调取消逻辑。
        """
        if self._capture_overlay is not None:
            try:
                # 若有全局抓取，先释放
                self._capture_overlay.grab_release()
            except tk.TclError:
                pass
            try:
                self._capture_overlay.destroy()
            except tk.TclError:
                pass

        self._capture_overlay = None
        self._capture_canvas = None
        self._capture_dot_id = None

        if cancelled and self._capture_cancel_callback:
            cb = self._capture_cancel_callback
            self._capture_cancel_callback = None
            self._capture_point_callback = None
            cb()
        else:
            self._capture_cancel_callback = None
            self._capture_point_callback = None

    def _start_mouse_capture(self, on_point_captured, on_cancel=None):
        """
        启动一次鼠标坐标捕获：创建一个覆盖整个屏幕的透明窗口，
        隐藏系统鼠标指针，并用一个跟随鼠标移动的红色十字准星进行提示。
        左键单击时记录当前屏幕坐标并调用回调，Esc 取消。
        """
        # 若已有捕获会话，则先结束
        if self._capture_overlay is not None:
            self._end_mouse_capture(cancelled=True)

        self._capture_point_callback = on_point_captured
        self._capture_cancel_callback = on_cancel

        overlay = tk.Toplevel(self.root)
        self._capture_overlay = overlay
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)

        # 覆盖整个主显示屏
        screen_w = overlay.winfo_screenwidth()
        screen_h = overlay.winfo_screenheight()
        overlay.geometry(f"{screen_w}x{screen_h}+0+0")

        # 使用透明色，让背景完全透明，只显示红色十字准星
        try:
            overlay.configure(bg="#ff00ff")
            overlay.attributes("-transparentcolor", "#ff00ff")
        except tk.TclError:
            # 某些平台可能不支持 transparentcolor，就退化为近乎透明的窗口
            overlay.configure(bg="black")
            try:
                overlay.attributes("-alpha", 0.01)
            except tk.TclError:
                pass

        # 隐藏系统鼠标指针
        overlay.config(cursor="none")

        canvas = tk.Canvas(
            overlay,
            bg=overlay["bg"],
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        self._capture_canvas = canvas

        # 使用更精确的准星：中心小圆点 + 十字线，中心交点即为捕获的像素点
        DOT_RADIUS = 3  # 原来为 5，减小半径便于精确定位
        CROSS_HALF = 10  # 十字线从中心向四周延伸的长度

        dot = canvas.create_oval(0, 0, 0, 0, fill="red", outline="red")
        h_line = canvas.create_line(0, 0, 0, 0, fill="red")
        v_line = canvas.create_line(0, 0, 0, 0, fill="red")
        self._capture_dot_id = dot

        def update_marker(x: int, y: int):
            """
            更新十字准星的位置。传入的 (x, y) 即为将要捕获的坐标。
            """
            r = DOT_RADIUS
            canvas.coords(dot, x - r, y - r, x + r, y + r)
            canvas.coords(h_line, x - CROSS_HALF, y, x + CROSS_HALF, y)
            canvas.coords(v_line, x, y - CROSS_HALF, x, y + CROSS_HALF)

        def on_motion(event):
            # event.x / y 是在当前窗口内的坐标（即屏幕坐标）
            update_marker(event.x, event.y)

        def on_click(event):
            if self._capture_point_callback:
                cb = self._capture_point_callback
                self._capture_point_callback = None  # 防止重复调用
                # 使用全局坐标（相对于屏幕）
                x, y = event.x_root, event.y_root
                self._end_mouse_capture(cancelled=False)
                cb(x, y)
            else:
                self._end_mouse_capture(cancelled=False)

        def on_escape(event):
            self._end_mouse_capture(cancelled=True)

        canvas.bind("<Motion>", on_motion)
        overlay.bind("<Motion>", on_motion)
        overlay.bind("<Button-1>", on_click)
        overlay.bind("<Key-Escape>", on_escape)

        # 让覆盖层获得键盘焦点并捕获所有输入，保证 Esc 可以生效
        try:
            overlay.focus_force()
        except tk.TclError:
            pass
        try:
            overlay.grab_set()
        except tk.TclError:
            pass

        # 初始时将十字准星放在当前鼠标位置
        try:
            x0, y0 = pyautogui.position()
            update_marker(x0, y0)
        except Exception:
            pass

        # 额外使用轮询方式跟踪系统鼠标位置，避免快速移动时红点与鼠标脱节
        def track_cursor():
            # 如果此次调用对应的 overlay 已经不存在，则停止轮询
            if self._capture_overlay is not overlay:
                return
            try:
                if not overlay.winfo_exists():
                    return
            except tk.TclError:
                return

            try:
                x, y = pyautogui.position()
                update_marker(x, y)
            except Exception:
                pass

            # 10ms 更新一次，跟随实际鼠标位置
            try:
                overlay.after(10, track_cursor)
            except tk.TclError:
                pass

        track_cursor()

    # ---------------- 功能逻辑 ---------------- #

    # --- 单点捕获 --- #

    def capture_single_point(self):
        """
        通过一次鼠标左键单击捕获单点坐标。
        """
        self.set_status("单点捕获：请用鼠标左键单击要获取坐标的位置，按 Esc 取消。")
        self.btn_capture_single.config(state=tk.DISABLED)

        def on_point(x: int, y: int):
            self.single_point_var.set(f"({x}, {y})")
            self.set_status(f"单点坐标已捕获：({x}, {y})")
            self.btn_capture_single.config(state=tk.NORMAL)

        def on_cancel():
            self.set_status("单点捕获已取消。")
            self.btn_capture_single.config(state=tk.NORMAL)

        self._start_mouse_capture(on_point_captured=on_point, on_cancel=on_cancel)

    # --- 范围捕获 --- #

    def capture_range(self):
        """
        通过两次鼠标左键单击捕获范围：第一点和第二点。
        """
        self.set_status("范围捕获：请先用鼠标左键单击选择第一点（如左上角），按 Esc 取消。")
        self.btn_capture_range.config(state=tk.DISABLED)
        self.range_step1_var.set("第一点：等待捕获…")
        self.range_step2_var.set("第二点：未捕获")
        self.range_result_var.set("范围：未计算")
        self._range_first_point = None  # 内部记录第一点

        def on_first_cancel():
            self.set_status("范围捕获已取消。")
            self.range_step1_var.set("第一点：未捕获")
            self.btn_capture_range.config(state=tk.NORMAL)

        def on_first_point(x1: int, y1: int):
            self._range_first_point = (x1, y1)
            self.range_step1_var.set(f"第一点：({x1}, {y1})")
            self.set_status(
                "第一点已捕获，请用鼠标左键单击选择第二点（对角位置），按 Esc 取消。"
            )

            def on_second_cancel():
                self.set_status("范围捕获已取消。")
                self.btn_capture_range.config(state=tk.NORMAL)

            def on_second_point(x2: int, y2: int):
                self.range_step2_var.set(f"第二点：({x2}, {y2})")

                if self._range_first_point is None:
                    self.set_status("第一点丢失，范围捕获失败，请重试。")
                    self.btn_capture_range.config(state=tk.NORMAL)
                    return

                fx, fy = self._range_first_point
                # 临时名称，真正保存时用户会填写
                temp_name = self.range_name_var.get().strip() or "未命名范围"
                region = create_region_from_points(temp_name, fx, fy, x2, y2)
                self.current_region = region

                self.range_result_var.set(
                    f"范围：left={region.left}, top={region.top}, "
                    f"width={region.width}, height={region.height}"
                )
                self.set_status("范围已捕获，可为其命名并点击“保存当前范围”。")
                self.btn_capture_range.config(state=tk.NORMAL)

            self._start_mouse_capture(
                on_point_captured=on_second_point,
                on_cancel=on_second_cancel,
            )

        self._start_mouse_capture(
            on_point_captured=on_first_point,
            on_cancel=on_first_cancel,
        )

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

        self.set_status(f"已在屏幕上高亮显示范围“【name】”（点击红框或 2 秒后自动关闭）。")

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
