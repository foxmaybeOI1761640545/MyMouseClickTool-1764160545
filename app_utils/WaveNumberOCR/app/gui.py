# -*- coding: utf-8 -*-
"""
gui.py - WaveNumberOCR 图形界面

负责：
- 坐标输入（x1, y1, x2, y2）
- 矩形高亮（在屏幕上用半透明窗口标出选区）
- 预览截取区域（弹出窗口显示截图）
- 调用后端执行 OCR，并在控制台和界面显示结果
"""

from typing import Tuple, Optional

import tkinter as tk
from tkinter import ttk, messagebox

from PIL import ImageTk  # 用于在 Tk 窗口中显示 PIL 图像

from backend import ScreenTextRecognizer, ScreenCaptureError


# ----------------- 默认坐标（图示坐标）-----------------
# 这里填的是你现在截图示例中使用的那组坐标：
# 左上：(800, 250)，右下：(1080, 350)
DEFAULT_X1 = 800
DEFAULT_Y1 = 250
DEFAULT_X2 = 1080
DEFAULT_Y2 = 350


class WaveNumberApp:
    """
    WaveNumberOCR 主界面类。
    """

    def __init__(self, recognizer: ScreenTextRecognizer):
        self.recognizer = recognizer

        self.root = tk.Tk()
        self.root.title("WaveNumberOCR - 第X波识别工具")
        self.root.resizable(False, False)

        # 用于显示识别结果
        self.result_var = tk.StringVar(value="识别结果：尚未识别")

        # 存放覆盖矩形窗口和预览窗口的引用（便于更新/关闭）
        self._overlay_window: Optional[tk.Toplevel] = None
        self._preview_window: Optional[tk.Toplevel] = None
        self._preview_photo: Optional[ImageTk.PhotoImage] = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------- UI 构建 -----------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", **pad)

        # 坐标输入区（两行：左上、右下）
        coord_frame = ttk.LabelFrame(main_frame, text="坐标输入（屏幕像素）")
        coord_frame.grid(row=0, column=0, sticky="ew", **pad)

        # 左上角坐标
        ttk.Label(coord_frame, text="左上 X：").grid(row=0, column=0, sticky="e", **pad)
        self.entry_x1 = ttk.Entry(coord_frame, width=10)
        self.entry_x1.grid(row=0, column=1, **pad)

        ttk.Label(coord_frame, text="左上 Y：").grid(row=0, column=2, sticky="e", **pad)
        self.entry_y1 = ttk.Entry(coord_frame, width=10)
        self.entry_y1.grid(row=0, column=3, **pad)

        # 右下角坐标
        ttk.Label(coord_frame, text="右下 X：").grid(row=1, column=0, sticky="e", **pad)
        self.entry_x2 = ttk.Entry(coord_frame, width=10)
        self.entry_x2.grid(row=1, column=1, **pad)

        ttk.Label(coord_frame, text="右下 Y：").grid(row=1, column=2, sticky="e", **pad)
        self.entry_y2 = ttk.Entry(coord_frame, width=10)
        self.entry_y2.grid(row=1, column=3, **pad)

        # —— 新增：初始化坐标为默认图示值 ——
        self.entry_x1.insert(0, str(DEFAULT_X1))
        self.entry_y1.insert(0, str(DEFAULT_Y1))
        self.entry_x2.insert(0, str(DEFAULT_X2))
        self.entry_y2.insert(0, str(DEFAULT_Y2))

        # 按钮区
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=0, sticky="ew", **pad)

        btn_preview = ttk.Button(btn_frame, text="预览选区（截图）", command=self._on_preview_region)
        btn_preview.grid(row=0, column=0, **pad)

        btn_highlight = ttk.Button(btn_frame, text="高亮显示选区", command=self._on_highlight_region)
        btn_highlight.grid(row=0, column=1, **pad)

        btn_recognize = ttk.Button(btn_frame, text="开始识别“第X波”", command=self._on_recognize)
        btn_recognize.grid(row=0, column=2, **pad)

        btn_quit = ttk.Button(btn_frame, text="退出", command=self._on_close)
        btn_quit.grid(row=0, column=3, **pad)

        # 结果显示
        result_label = ttk.Label(main_frame, textvariable=self.result_var, foreground="blue")
        result_label.grid(row=2, column=0, sticky="w", **pad)

        # 提示
        hint_label = ttk.Label(
            main_frame,
            text="提示：坐标为屏幕像素，左上角大致为 (0, 0)，向右为 X+，向下为 Y+。",
            foreground="gray"
        )
        hint_label.grid(row=3, column=0, sticky="w", **pad)

    # ----------------- 事件处理 -----------------

    def _get_coords_from_entries(self) -> Tuple[int, int, int, int]:
        """
        从文本框中读取坐标，并转换为整数。
        若输入不合法，抛出 ValueError，由调用方处理。
        """
        try:
            x1 = int(self.entry_x1.get())
            y1 = int(self.entry_y1.get())
            x2 = int(self.entry_x2.get())
            y2 = int(self.entry_y2.get())
        except ValueError as exc:
            raise ValueError("坐标必须为整数，请检查输入。") from exc

        if x1 == x2 or y1 == y2:
            raise ValueError("选区宽度和高度都必须大于 0，请重新输入坐标。")

        return x1, y1, x2, y2

    def _on_preview_region(self) -> None:
        """
        预览选区：截取屏幕指定区域并在弹出窗口中显示截图。
        """
        try:
            coords = self._get_coords_from_entries()
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc), parent=self.root)
            return

        try:
            img = self.recognizer.capture_region(*coords)
        except ScreenCaptureError as exc:
            messagebox.showerror("截屏失败", str(exc), parent=self.root)
            return

        # 若之前有预览窗口，复用/更新之
        if self._preview_window is None or not self._preview_window.winfo_exists():
            self._preview_window = tk.Toplevel(self.root)
            self._preview_window.title("选区预览")
        else:
            self._preview_window.deiconify()
            self._preview_window.lift()

        # 将 PIL Image 转为 PhotoImage
        self._preview_photo = ImageTk.PhotoImage(img)

        label = ttk.Label(self._preview_window, image=self._preview_photo)
        label.image = self._preview_photo  # 防止被垃圾回收
        label.pack()

        # 根据图像大小调整窗口大小
        self._preview_window.geometry(f"{img.width}x{img.height}")

    def _on_highlight_region(self) -> None:
        """
        在屏幕上用半透明红色矩形高亮显示用户输入的坐标区域。
        这是一个独立的无边框顶层窗口。
        现在改为：显示 3 秒后自动隐藏。
        """
        try:
            x1, y1, x2, y2 = self._get_coords_from_entries()
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc), parent=self.root)
            return

        left, top, right, bottom = self.recognizer.normalize_box(x1, y1, x2, y2)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            messagebox.showerror("坐标错误", "选区宽度和高度必须大于 0。", parent=self.root)
            return

        # 若之前已有 overlay 窗口，更新它；否则新建
        if self._overlay_window is None or not self._overlay_window.winfo_exists():
            self._overlay_window = tk.Toplevel(self.root)
            self._overlay_window.overrideredirect(True)  # 无边框
            self._overlay_window.attributes("-topmost", True)
            # 半透明红色矩形；注意某些平台可能不支持 alpha 或颜色设置
            self._overlay_window.attributes("-alpha", 0.3)
            self._overlay_window.configure(bg="red")

        self._overlay_window.geometry(f"{width}x{height}+{left}+{top}")
        self._overlay_window.deiconify()
        self._overlay_window.lift()

        # —— 新增：3 秒后自动隐藏高亮窗口 ——
        self.root.after(3000, self._hide_overlay)

    def _hide_overlay(self) -> None:
        """
        隐藏高亮窗口（如果存在）。
        使用 withdraw 而不是 destroy，这样下次还能复用。
        """
        if self._overlay_window is not None and self._overlay_window.winfo_exists():
            self._overlay_window.withdraw()

    def _on_recognize(self) -> None:
        """
        触发识别：截屏 + OCR + 解析 “第X波”。
        在控制台打印结果，并在 GUI 中显示。
        """
        try:
            coords = self._get_coords_from_entries()
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc), parent=self.root)
            return

        try:
            number = self.recognizer.capture_and_recognize(*coords)
        except ScreenCaptureError as exc:
            messagebox.showerror("截屏失败", str(exc), parent=self.root)
            return
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("识别失败", f"OCR 过程中出现错误：{exc}", parent=self.root)
            return

        if number is None:
            # 没有找到 "第…波" 模式，按需求返回 null
            print("识别结果: null")
            self.result_var.set("识别结果：null（未找到“第…波”模式）")
        else:
            print(f"识别结果: {number}")
            self.result_var.set(f"识别结果：{number}")

    def _on_close(self) -> None:
        """
        关闭主窗口及所有子窗口。
        """
        # 先关闭 overlay
        if self._overlay_window is not None and self._overlay_window.winfo_exists():
            self._overlay_window.destroy()

        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.destroy()

        self.root.destroy()

    # ----------------- 外部调用 -----------------

    def run(self) -> None:
        """启动 GUI 主循环。"""
        self.root.mainloop()
