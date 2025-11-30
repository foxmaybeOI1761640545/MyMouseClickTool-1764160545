# -*- coding: utf-8 -*-
"""
gui.py - WaveNumberOCR 图形界面

负责：
- 坐标输入（x1, y1, x2, y2）
- 矩形高亮（在屏幕上用半透明窗口标出选区）
- 预览截取区域（弹出窗口显示截图）
- 调用后端执行 OCR，并在控制台和界面显示结果
- 在连续识别时，同时读取一个指定坐标像素的颜色
"""

from typing import Tuple, Optional
import threading
import time

import tkinter as tk
from tkinter import ttk, messagebox

from PIL import ImageTk  # 用于在 Tk 窗口中显示 PIL 图像
import keyboard  # 全局快捷键

from backend import ScreenTextRecognizer, ScreenCaptureError


# ----------------- 默认坐标（图示坐标）-----------------
# 左上：(800, 250)，右下：(1080, 350)
DEFAULT_X1 = 800
DEFAULT_Y1 = 250
DEFAULT_X2 = 1080
DEFAULT_Y2 = 350

# 需要读取像素颜色的默认坐标
DEFAULT_COLOR_X = 935
DEFAULT_COLOR_Y = 300


class WaveNumberApp:
    """
    WaveNumberOCR 主界面类。
    """

    def __init__(self, recognizer: ScreenTextRecognizer) -> None:
        self.recognizer = recognizer

        self.root = tk.Tk()
        self.root.title("WaveNumberOCR - 第X波识别工具")
        self.root.resizable(False, False)

        # 用于显示识别结果
        self.result_var = tk.StringVar(value="识别结果：尚未识别")
        # 用于显示高亮倒计时
        self.highlight_countdown_var = tk.StringVar(value="")
        self._highlight_remaining: int = 0
        self._highlight_timer_id: Optional[str] = None

        # 用于预览/覆盖窗口
        self._overlay_window: Optional[tk.Toplevel] = None
        self._preview_window: Optional[tk.Toplevel] = None
        self._preview_photo: Optional[ImageTk.PhotoImage] = None
        self._preview_label: Optional[ttk.Label] = None

        # 连续识别相关状态
        self._recognizing: bool = False
        self._recognize_thread: Optional[threading.Thread] = None
        self._recognize_seconds: int = 0
        self._recognize_coords: Optional[Tuple[int, int, int, int]] = None

        self._build_ui()

        # 固定一个最小窗口大小，避免点击按钮后主窗口被自动缩小
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())

        # 注册全局快捷键 Ctrl+Q，用于开始/暂停连续识别
        self._register_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------- UI 构建 -----------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", **pad)

        # 坐标输入区
        coord_frame = ttk.LabelFrame(main_frame, text="坐标输入（屏幕像素）")
        coord_frame.grid(row=0, column=0, sticky="ew", **pad)

        # 左上角
        ttk.Label(coord_frame, text="左上 X：").grid(row=0, column=0, sticky="e", **pad)
        self.entry_x1 = ttk.Entry(coord_frame, width=10)
        self.entry_x1.grid(row=0, column=1, **pad)

        ttk.Label(coord_frame, text="左上 Y：").grid(row=0, column=2, sticky="e", **pad)
        self.entry_y1 = ttk.Entry(coord_frame, width=10)
        self.entry_y1.grid(row=0, column=3, **pad)

        # 右下角
        ttk.Label(coord_frame, text="右下 X：").grid(row=1, column=0, sticky="e", **pad)
        self.entry_x2 = ttk.Entry(coord_frame, width=10)
        self.entry_x2.grid(row=1, column=1, **pad)

        ttk.Label(coord_frame, text="右下 Y：").grid(row=1, column=2, sticky="e", **pad)
        self.entry_y2 = ttk.Entry(coord_frame, width=10)
        self.entry_y2.grid(row=1, column=3, **pad)

        # 初始化默认坐标
        self.entry_x1.insert(0, str(DEFAULT_X1))
        self.entry_y1.insert(0, str(DEFAULT_Y1))
        self.entry_x2.insert(0, str(DEFAULT_X2))
        self.entry_y2.insert(0, str(DEFAULT_Y2))

        # 按钮区
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=0, sticky="ew", **pad)

        btn_preview = ttk.Button(btn_frame, text="预览选区截图", command=self._on_preview_region)
        btn_preview.grid(row=0, column=0, **pad)

        btn_highlight = ttk.Button(btn_frame, text="高亮显示选区", command=self._on_highlight_region)
        btn_highlight.grid(row=0, column=1, **pad)

        self.btn_recognize = ttk.Button(btn_frame, text="开始识别关卡", command=self._on_recognize)
        self.btn_recognize.grid(row=0, column=2, **pad)

        btn_quit = ttk.Button(btn_frame, text="退出当前程序", command=self._on_close)
        btn_quit.grid(row=0, column=3, **pad)

        # 高亮倒计时
        highlight_label = ttk.Label(
            main_frame, textvariable=self.highlight_countdown_var, foreground="darkred"
        )
        highlight_label.grid(row=2, column=0, sticky="w", **pad)

        # 识别结果 + 像素颜色
        self.result_label = ttk.Label(main_frame, textvariable=self.result_var, foreground="blue")
        self.result_label.grid(row=3, column=0, sticky="w", **pad)

        hint_label = ttk.Label(
            main_frame,
            text=(
                "提示：坐标为屏幕像素，左上角大致为 (0, 0)，向右为 X+，向下为 Y+。"
            ),
            foreground="gray",
        )
        hint_label.grid(row=4, column=0, sticky="w", **pad)

    # ----------------- 全局快捷键 -----------------

    def _register_hotkeys(self) -> None:
        """
        注册全局快捷键 Ctrl+Q：与“开始/暂停识别关卡”按钮行为相同。
        """
        try:
            keyboard.add_hotkey("ctrl+q", lambda: self.root.after(0, self._on_recognize))
            print("已注册全局快捷键：Ctrl+Q 用于开始/暂停连续识别。")
        except Exception as exc:  # pylint: disable=broad-except
            print(f"注册全局快捷键失败：{exc}")

    # ----------------- 工具方法 -----------------

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

    # ----------------- 事件处理：预览 / 高亮 -----------------

    def _on_preview_region(self) -> None:
        """
        预览选区：截取屏幕指定区域并在弹出窗口中显示截图。
        多次点击时只保留最新的一张截图。
        同时修复：如果用户手动放大预览窗口，再次点击按钮时不再把窗口变小。
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

        # 若之前有预览窗口，则复用；否则新建
        if self._preview_window is None or not self._preview_window.winfo_exists():
            self._preview_window = tk.Toplevel(self.root)
            self._preview_window.title("选区预览")
            self._preview_window.resizable(True, True)
            self._preview_label = ttk.Label(self._preview_window)
            self._preview_label.pack(fill="both", expand=True)
        else:
            self._preview_window.deiconify()
            self._preview_window.lift()
            if self._preview_label is None or not self._preview_label.winfo_exists():
                self._preview_label = ttk.Label(self._preview_window)
                self._preview_label.pack(fill="both", expand=True)

        # 更新截图
        self._preview_photo = ImageTk.PhotoImage(img)
        self._preview_label.configure(image=self._preview_photo)
        self._preview_label.image = self._preview_photo  # 避免被 GC 回收

        # 根据图像大小调整窗口大小：
        # 只在需要变大时扩大窗口尺寸，不会把用户已经放大的窗口再缩回去。
        img_w, img_h = img.width, img.height
        self._preview_window.update_idletasks()
        cur_w = self._preview_window.winfo_width()
        cur_h = self._preview_window.winfo_height()
        new_w = max(cur_w, img_w)
        new_h = max(cur_h, img_h)
        # 如果窗口刚创建，cur_w/cur_h 会很小，此时会被提升到图片大小；
        # 如果用户手动拉大过窗口，则保持较大的值，不会被缩小。
        self._preview_window.geometry(f"{new_w}x{new_h}")

    def _on_highlight_region(self) -> None:
        """
        在屏幕上用半透明红色矩形高亮显示用户输入的坐标区域。
        新增 3 秒自动消失的倒计时显示。
        """
        try:
            x1, y1, x2, y2 = self._get_coords_from_entries()
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc), parent=self.root)
            return

        from backend import ScreenTextRecognizer as _STR  # 避免循环导入类型检查报错
        left, top, right, bottom = _STR.normalize_box(x1, y1, x2, y2)
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
            self._overlay_window.attributes("-alpha", 0.3)
            self._overlay_window.configure(bg="red")

        self._overlay_window.geometry(f"{width}x{height}+{left}+{top}")
        self._overlay_window.deiconify()
        self._overlay_window.lift()

        # 取消之前的倒计时（如果有）
        if self._highlight_timer_id is not None:
            try:
                self.root.after_cancel(self._highlight_timer_id)
            except Exception:
                pass
            self._highlight_timer_id = None

        # 开始新的 3 秒倒计时
        self._highlight_remaining = 3
        self._update_highlight_countdown()

    def _update_highlight_countdown(self) -> None:
        """
        高亮倒计时更新：每秒更新一次显示，倒计时结束后隐藏高亮窗口。
        """
        if self._highlight_remaining <= 0:
            self.highlight_countdown_var.set("")
            self._hide_overlay()
            self._highlight_timer_id = None
            return

        self.highlight_countdown_var.set(f"高亮剩余：{self._highlight_remaining} 秒")
        self._highlight_remaining -= 1
        self._highlight_timer_id = self.root.after(1000, self._update_highlight_countdown)

    def _hide_overlay(self) -> None:
        """
        隐藏高亮窗口（如果存在）。
        """
        if self._overlay_window is not None and self._overlay_window.winfo_exists():
            self._overlay_window.withdraw()

    # ----------------- 连续识别（多线程） -----------------

    def _on_recognize(self) -> None:
        """
        触发/暂停连续识别：
        - 第一次触发时，读取当前坐标，启动后台线程每秒识别一次；
        - 再次触发时，暂停识别；
        - 可通过按钮点击或全局快捷键 Ctrl+Q 触发本方法。
        """
        if not self._recognizing:
            try:
                coords = self._get_coords_from_entries()
            except ValueError as exc:
                messagebox.showerror("输入错误", str(exc), parent=self.root)
                return

            self._recognizing = True
            self._recognize_seconds = 0
            self._recognize_coords = coords
            self._update_recognize_button_text()
            self.result_var.set(
                "识别结果：开始连续识别（Ctrl+Q 可暂停）"
            )

            self._recognize_thread = threading.Thread(
                target=self._recognize_loop, daemon=True
            )
            self._recognize_thread.start()
        else:
            self._recognizing = False
            self._update_recognize_button_text()
            self.result_var.set("识别结果：已暂停连续识别（Ctrl+Q 再次开始）")

    def _update_recognize_button_text(self) -> None:
        if self._recognizing:
            self.btn_recognize.configure(text="暂停识别关卡")
        else:
            self.btn_recognize.configure(text="开始识别关卡")

    def _recognize_loop(self) -> None:
        """
        后台线程：每秒执行一次识别，直到 _recognizing 被置为 False。
        日志格式：第n秒: 识别结果 / 像素颜色。
        同时返回指定坐标 (DEFAULT_COLOR_X, DEFAULT_COLOR_Y) 的像素颜色。
        """
        assert self._recognize_coords is not None

        while self._recognizing:
            self._recognize_seconds += 1

            # 先进行关卡文字识别
            try:
                number = self.recognizer.capture_and_recognize(
                    *self._recognize_coords
                )
                if number is None:
                    wave_content = "null"
                    base_gui_text = "识别结果：null（未找到“第…波”模式）"
                else:
                    wave_content = str(number)
                    base_gui_text = f"识别结果：{number}"
            except ScreenCaptureError as exc:
                wave_content = f"截屏失败：{exc}"
                base_gui_text = f"识别结果：截屏失败：{exc}"
            except Exception as exc:  # pylint: disable=broad-except
                wave_content = f"OCR 错误：{exc}"
                base_gui_text = f"识别结果：OCR 错误：{exc}"

            # 读取指定坐标像素颜色
            color_info = ""
            try:
                r, g, b = self.recognizer.get_pixel_color(
                    DEFAULT_COLOR_X, DEFAULT_COLOR_Y
                )
                hex_color = f"#{r:02X}{g:02X}{b:02X}"
                color_info = (
                    f"像素({DEFAULT_COLOR_X}, {DEFAULT_COLOR_Y}) 颜色："
                    f"RGB({r}, {g}, {b}) / {hex_color}"
                )
            except ScreenCaptureError as exc:
                color_info = f"像素颜色获取失败：{exc}"
            except Exception as exc:  # pylint: disable=broad-except
                color_info = f"像素颜色错误：{exc}"

            log_line = f"第{self._recognize_seconds}秒: {wave_content} | {color_info}"
            print(log_line)

            gui_text = f"{base_gui_text} | {color_info}"

            # 更新 GUI 文本（回到主线程）
            self.root.after(0, self._update_result_text, gui_text)

            # 每秒执行一次识别，注意在等待期间检查停止标志
            for _ in range(10):
                if not self._recognizing:
                    break
                time.sleep(0.1)

    def _update_result_text(self, text: str) -> None:
        self.result_var.set(text)

    # ----------------- 关闭 -----------------

    def _on_close(self) -> None:
        """
        关闭主窗口及所有子窗口。
        """
        # 停止连续识别线程
        self._recognizing = False

        # 清理全局快捷键
        try:
            keyboard.clear_all_hotkeys()
        except Exception:
            pass

        if self._overlay_window is not None and self._overlay_window.winfo_exists():
            self._overlay_window.destroy()

        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.destroy()

        self.root.destroy()

    # ----------------- 外部调用 -----------------

    def run(self) -> None:
        """启动 GUI 主循环。"""
        self.root.mainloop()
