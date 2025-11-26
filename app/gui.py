import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
import threading
from pynput import keyboard
from app.config import ConfigManager
from app.input_controller import InputController
from app.hotkey_listener import HotkeyListener


# 配色方案
COLOR_SCHEME = {
    'bg_main': '#FFF8E1',           # 主背景-浅黄
    'bg_card': '#FFFBF0',           # 卡片背景-更浅黄
    'btn_primary': '#FFB74D',       # 主按钮-黄橙色
    'btn_success': '#81C784',       # 成功按钮-柔和绿
    'btn_warning': '#FFD54F',       # 警告按钮-金黄色
    'btn_danger': '#FF8A80',        # 危险按钮-浅红色
    'text_dark': '#424242',         # 深色文字
    'text_light': '#FFFFFF',        # 浅色文字
    'border': '#FFE082',            # 边框色-金黄
}


class RoundedButton(tk.Canvas):
    """圆角按钮组件"""
    
    def __init__(self, parent, text="Button", command=None, width=120, height=40, 
                 bg_color="#FFB74D", fg_color="#FFFFFF", radius=15, **kwargs):
        """
        初始化圆角按钮
        
        Args:
            parent: 父组件
            text: 按钮文字
            command: 点击回调函数
            width: 按钮宽度
            height: 按钮高度
            bg_color: 背景颜色
            fg_color: 文字颜色
            radius: 圆角半径
        """
        tk.Canvas.__init__(self, parent, width=width, height=height, 
                          highlightthickness=0, **kwargs)
        
        self.command = command
        self.text = text
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.radius = radius
        self.width = width
        self.height = height
        
        # 绘制圆角矩形
        self._draw_rounded_rect()
        
        # 绑定事件
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _draw_rounded_rect(self, hover=False):
        """绘制圆角矩形"""
        self.delete("all")
        
        # 如果是悬停状态，颜色稍微变暗
        color = self._darken_color(self.bg_color) if hover else self.bg_color
        
        # 设置canvas背景为透明（使用父组件背景色）
        self.configure(bg=COLOR_SCHEME['bg_main'])
        
        x1, y1, x2, y2 = 2, 2, self.width - 2, self.height - 2
        r = self.radius
        
        # 绘制圆角矩形
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1
        ]
        
        self.create_polygon(points, smooth=True, fill=color, outline="")
        
        # 添加文字
        self.create_text(self.width/2, self.height/2, text=self.text, 
                        fill=self.fg_color, font=("Arial", 10, "bold"))
    
    def _darken_color(self, color):
        """使颜色变暗（用于悬停效果）"""
        # 简单的变暗算法
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        r = int(r * 0.85)
        g = int(g * 0.85)
        b = int(b * 0.85)
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def _on_click(self, event):
        """点击事件"""
        if self.command:
            self.command()
    
    def _on_enter(self, event):
        """鼠标进入事件"""
        self._draw_rounded_rect(hover=True)
        self.configure(cursor="hand2")
    
    def _on_leave(self, event):
        """鼠标离开事件"""
        self._draw_rounded_rect(hover=False)
        self.configure(cursor="")
    
    def config(self, **kwargs):
        """配置按钮属性"""
        if 'state' in kwargs:
            state = kwargs['state']
            if state == tk.DISABLED:
                self.unbind("<Button-1>")
                self.unbind("<Enter>")
                self.unbind("<Leave>")
                # 绘制灰色状态
                old_color = self.bg_color
                self.bg_color = "#CCCCCC"
                self._draw_rounded_rect()
                self.bg_color = old_color
            elif state == tk.NORMAL:
                self.bind("<Button-1>", self._on_click)
                self.bind("<Enter>", self._on_enter)
                self.bind("<Leave>", self._on_leave)
                self._draw_rounded_rect()
        
        if 'text' in kwargs:
            self.text = kwargs['text']
            self._draw_rounded_rect()


class HotkeyRecorderDialog(tk.Toplevel):
    """快捷键录制对话框"""
    
    def __init__(self, parent):
        """
        初始化快捷键录制对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.title("设置快捷键")
        self.geometry("350x200")
        self.configure(bg=COLOR_SCHEME['bg_main'])
        self.resizable(False, False)
        
        # 居中显示
        self.transient(parent)
        self.grab_set()
        
        # 结果
        self.result = None
        self.listener = None
        
        # 创建UI
        self._create_widgets()
        
        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # 开始监听
        self._start_listening()
    
    def _create_widgets(self):
        """创建对话框组件"""
        # 提示标签
        prompt_label = tk.Label(self, text="请按下您想要设置的快捷键", 
                               font=("Arial", 12, "bold"),
                               bg=COLOR_SCHEME['bg_main'], 
                               fg=COLOR_SCHEME['text_dark'])
        prompt_label.pack(pady=30)
        
        # 显示当前按键
        self.key_label = tk.Label(self, text="等待输入...", 
                                 font=("Arial", 14, "bold"),
                                 bg=COLOR_SCHEME['bg_card'], 
                                 fg=COLOR_SCHEME['btn_primary'],
                                 relief=tk.FLAT, padx=20, pady=10)
        self.key_label.pack(pady=10)
        
        # 提示文字
        hint_label = tk.Label(self, text="支持功能键 (F1-F12) 和字母键 (A-Z)", 
                             font=("Arial", 9),
                             bg=COLOR_SCHEME['bg_main'], 
                             fg="gray")
        hint_label.pack(pady=5)
        
        # 按钮区域
        button_frame = tk.Frame(self, bg=COLOR_SCHEME['bg_main'])
        button_frame.pack(pady=20)
        
        # 取消按钮
        cancel_btn = RoundedButton(button_frame, text="取消", command=self._on_cancel,
                                  width=100, height=35, bg_color="#9E9E9E",
                                  fg_color=COLOR_SCHEME['text_light'], radius=15)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def _start_listening(self):
        """开始监听键盘"""
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()
    
    def _on_key_press(self, key):
        """
        处理按键事件
        
        Args:
            key: 按下的键
        """
        try:
            # 获取按键名称
            key_name = None
            if hasattr(key, 'name'):
                key_name = key.name.lower()
            elif hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
            
            if key_name:
                # 验证快捷键是否有效
                if self._is_valid_hotkey(key_name):
                    self.key_label.config(text=key_name.upper())
                    self.result = key_name
                    # 延迟关闭，让用户看到按键显示
                    self.after(500, self._on_confirm)
                else:
                    self.key_label.config(text="无效按键，请重试")
                    self.after(1000, lambda: self.key_label.config(text="等待输入..."))
        except Exception as e:
            print(f"按键处理错误: {e}")
    
    def _is_valid_hotkey(self, key_name):
        """
        验证快捷键是否有效
        
        Args:
            key_name: 按键名称
            
        Returns:
            bool: 是否有效
        """
        # 支持功能键 F1-F12 和字母键 A-Z
        valid_keys = [f"f{i}" for i in range(1, 13)] + [chr(i) for i in range(ord('a'), ord('z') + 1)]
        return key_name in valid_keys
    
    def _on_confirm(self):
        """确认并关闭对话框"""
        if self.listener:
            self.listener.stop()
        self.destroy()
    
    def _on_cancel(self):
        """取消并关闭对话框"""
        self.result = None
        if self.listener:
            self.listener.stop()
        self.destroy()


class ScrollableFrame(tk.Frame):
    """可滚动的Frame"""
    
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, bg=COLOR_SCHEME['bg_main'], *args, **kwargs)
        
        # 创建Canvas和滚动条
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg=COLOR_SCHEME['bg_main'])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLOR_SCHEME['bg_main'])
        
        # 配置滚动区域
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # 创建窗口
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # 配置canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # 绑定canvas大小变化
        self.canvas.bind('<Configure>', self._on_canvas_configure)
    
    def _on_mousewheel(self, event):
        """鼠标滚轮事件"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _on_canvas_configure(self, event):
        """Canvas大小变化时，调整内部frame宽度"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)


class AutoInputGUI:
    """自动输入工具GUI界面"""
    
    def __init__(self):
        """初始化GUI"""
        self.root = tk.Tk()
        self.root.title("自动输入工具")
        self.root.geometry("650x700")
        self.root.resizable(True, True)
        self.root.configure(bg=COLOR_SCHEME['bg_main'])
        
        # 初始化组件
        self.config_manager = ConfigManager()
        self.input_controller = InputController()
        self.hotkey_listener = None
        
        # 存储字符串卡片的列表
        self.string_cards = []
        
        # 当前快捷键配置
        self.current_hotkey = "f1"
        
        # 创建GUI组件
        self._create_widgets()
        
        # 加载配置（会设置current_hotkey）
        self._load_config()
        
        # 更新快捷键显示
        self.hotkey_display.config(text=f"当前: {self.current_hotkey.upper()}")
        
        # 启动全局快捷键监听
        self._start_hotkey_listener()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _create_widgets(self):
        """创建并布局所有GUI组件"""
        # 顶部：字符间隔设置
        char_interval_frame = tk.Frame(self.root, bg=COLOR_SCHEME['bg_main'])
        char_interval_frame.grid(row=0, column=0, columnspan=2, padx=15, pady=15, sticky="ew")
        
        char_interval_label = tk.Label(char_interval_frame, text="字符间隔(毫秒):", 
                                       font=("Arial", 11), bg=COLOR_SCHEME['bg_main'], 
                                       fg=COLOR_SCHEME['text_dark'])
        char_interval_label.pack(side=tk.LEFT, padx=8)
        
        self.char_interval_entry = tk.Entry(char_interval_frame, width=15, font=("Arial", 10),
                                           relief=tk.FLAT, bd=2, bg=COLOR_SCHEME['bg_card'],
                                           highlightthickness=2, highlightcolor=COLOR_SCHEME['border'],
                                           highlightbackground=COLOR_SCHEME['border'])
        self.char_interval_entry.pack(side=tk.LEFT, padx=8, ipady=4)
        self.char_interval_entry.insert(0, "1")
        self.char_interval_entry.bind("<Leave>", lambda e: self._unfocus_entry())
        
        # 中间：可滚动的字符串列表区域
        strings_label = tk.Label(self.root, text="字符串列表:", font=("Arial", 11, "bold"),
                                bg=COLOR_SCHEME['bg_main'], fg=COLOR_SCHEME['text_dark'])
        strings_label.grid(row=1, column=0, padx=15, pady=(5, 10), sticky="w")
        
        # 创建可滚动区域
        self.scrollable_frame = ScrollableFrame(self.root)
        self.scrollable_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=5, sticky="nsew")
        
        # 添加字符串按钮
        self.add_button = RoundedButton(self.root, text="+ 添加字符串", command=self._add_string_card,
                                       width=150, height=40, bg_color=COLOR_SCHEME['btn_primary'],
                                       fg_color=COLOR_SCHEME['text_light'], radius=20)
        self.add_button.grid(row=3, column=0, columnspan=2, pady=10)
        
        # 状态显示
        self.status_label = tk.Label(self.root, text="状态: 未运行", font=("Arial", 11, "bold"),
                                     bg=COLOR_SCHEME['bg_main'], fg="gray")
        self.status_label.grid(row=4, column=0, columnspan=2, padx=15, pady=15)
        
        # 控制按钮区域
        button_frame = tk.Frame(self.root, bg=COLOR_SCHEME['bg_main'])
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        self.start_button = RoundedButton(button_frame, text="启动", command=self._start_input,
                                         width=120, height=50, bg_color=COLOR_SCHEME['btn_success'],
                                         fg_color=COLOR_SCHEME['text_light'], radius=20)
        self.start_button.pack(side=tk.LEFT, padx=8)
        
        self.pause_button = RoundedButton(button_frame, text="暂停", command=self._pause_resume_input,
                                         width=120, height=50, bg_color=COLOR_SCHEME['btn_warning'],
                                         fg_color=COLOR_SCHEME['text_dark'], radius=20)
        self.pause_button.pack(side=tk.LEFT, padx=8)
        self.pause_button.config(state=tk.DISABLED)
        
        self.stop_button = RoundedButton(button_frame, text="停止", command=self._stop_input,
                                        width=120, height=50, bg_color=COLOR_SCHEME['btn_danger'],
                                        fg_color=COLOR_SCHEME['text_light'], radius=20)
        self.stop_button.pack(side=tk.LEFT, padx=8)
        self.stop_button.config(state=tk.DISABLED)
        
        # 保存配置按钮
        self.save_button = RoundedButton(self.root, text="保存配置", command=self._save_config,
                                        width=150, height=40, bg_color=COLOR_SCHEME['btn_primary'],
                                        fg_color=COLOR_SCHEME['text_light'], radius=20)
        self.save_button.grid(row=6, column=0, columnspan=2, pady=10)
        
        # 快捷键设置区域
        hotkey_frame = tk.Frame(self.root, bg=COLOR_SCHEME['bg_main'])
        hotkey_frame.grid(row=7, column=0, columnspan=2, pady=(5, 10))
        
        hotkey_hint = tk.Label(hotkey_frame, text="快捷键设置:", 
                              font=("Arial", 10, "bold"), bg=COLOR_SCHEME['bg_main'],
                              fg=COLOR_SCHEME['text_dark'])
        hotkey_hint.pack(side=tk.LEFT, padx=5)
        
        self.hotkey_display = tk.Label(hotkey_frame, text=f"当前: {self.current_hotkey.upper()}", 
                                      font=("Arial", 10), bg=COLOR_SCHEME['bg_card'],
                                      fg=COLOR_SCHEME['btn_primary'], relief=tk.FLAT,
                                      padx=10, pady=5)
        self.hotkey_display.pack(side=tk.LEFT, padx=5)
        
        change_hotkey_btn = RoundedButton(hotkey_frame, text="修改", command=self._change_hotkey,
                                         width=80, height=30, bg_color=COLOR_SCHEME['btn_primary'],
                                         fg_color=COLOR_SCHEME['text_light'], radius=12)
        change_hotkey_btn.pack(side=tk.LEFT, padx=5)
        
        # 配置列和行权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
    
    def _add_string_card(self, text: str = "", interval_ms: int = 100):
        """
        添加字符串卡片
        
        Args:
            text: 字符串内容，默认为空
            interval_ms: 间隔时间（毫秒），默认为100
        """
        # 创建卡片Frame - 使用浅色背景和圆润边框效果
        card_frame = tk.Frame(self.scrollable_frame.scrollable_frame, 
                             bg=COLOR_SCHEME['bg_card'],
                             relief=tk.FLAT, 
                             borderwidth=2,
                             highlightbackground=COLOR_SCHEME['border'],
                             highlightthickness=2)
        card_frame.pack(fill=tk.X, padx=8, pady=8, ipady=8, ipadx=8)
        
        # 字符串输入区域
        text_label = tk.Label(card_frame, text="字符串:", font=("Arial", 10, "bold"),
                             bg=COLOR_SCHEME['bg_card'], fg=COLOR_SCHEME['text_dark'])
        text_label.grid(row=0, column=0, padx=8, pady=8, sticky="w")
        
        text_entry = tk.Entry(card_frame, width=40, font=("Arial", 10), 
                             relief=tk.FLAT, bd=2, bg="#FFFFFF", 
                             fg=COLOR_SCHEME['text_dark'],
                             highlightthickness=2, highlightcolor=COLOR_SCHEME['border'],
                             highlightbackground=COLOR_SCHEME['border'])
        text_entry.grid(row=0, column=1, padx=8, pady=8, sticky="ew", ipady=4)
        text_entry.insert(0, text)
        text_entry.bind("<Leave>", lambda e: self._unfocus_entry())
        
        # 间隔时间输入
        interval_label = tk.Label(card_frame, text="间隔(ms):", font=("Arial", 10, "bold"),
                                 bg=COLOR_SCHEME['bg_card'], fg=COLOR_SCHEME['text_dark'])
        interval_label.grid(row=1, column=0, padx=8, pady=8, sticky="w")
        
        interval_entry = tk.Entry(card_frame, width=15, font=("Arial", 10),
                                 relief=tk.FLAT, bd=2, bg="#FFFFFF",
                                 highlightthickness=2, highlightcolor=COLOR_SCHEME['border'],
                                 highlightbackground=COLOR_SCHEME['border'])
        interval_entry.grid(row=1, column=1, padx=8, pady=8, sticky="w")
        interval_entry.insert(0, str(interval_ms))
        interval_entry.bind("<Leave>", lambda e: self._unfocus_entry())
        
        # 删除按钮
        delete_button = RoundedButton(card_frame, text="删除", 
                                     command=lambda: self._remove_string_card(card_frame),
                                     width=80, height=60, 
                                     bg_color=COLOR_SCHEME['btn_danger'],
                                     fg_color=COLOR_SCHEME['text_light'],
                                     radius=15)
        delete_button.grid(row=0, column=2, rowspan=2, padx=8, pady=8, sticky="nsew")
        
        # 配置列权重
        card_frame.columnconfigure(1, weight=1)
        
        # 存储卡片信息
        card_info = {
            "frame": card_frame,
            "text_entry": text_entry,
            "interval_entry": interval_entry
        }
        self.string_cards.append(card_info)
    
    def _unfocus_entry(self):
        """移除输入框焦点"""
        self.root.focus()
    
    def _remove_string_card(self, card_frame):
        """删除字符串卡片"""
        # 找到对应的卡片信息
        for i, card_info in enumerate(self.string_cards):
            if card_info["frame"] == card_frame:
                # 销毁卡片
                card_frame.destroy()
                # 从列表中移除
                self.string_cards.pop(i)
                break
    
    def _get_all_strings(self):
        """
        从所有卡片收集字符串数据
        
        Returns:
            tuple: (strings列表, char_interval_ms)
        """
        strings = []
        
        # 获取字符间隔
        try:
            char_interval_ms = int(self.char_interval_entry.get().strip())
            if char_interval_ms < 0:
                raise ValueError("字符间隔不能为负数")
        except ValueError:
            raise ValueError("字符间隔必须是有效的非负整数")
        
        # 收集所有字符串
        for card_info in self.string_cards:
            text = card_info["text_entry"].get().strip()
            if text:  # 只添加非空字符串
                try:
                    interval_ms = int(card_info["interval_entry"].get().strip())
                    if interval_ms < 0:
                        raise ValueError("间隔时间不能为负数")
                except ValueError:
                    raise ValueError(f"字符串 '{text[:20]}...' 的间隔时间必须是有效的非负整数")
                
                strings.append({
                    "text": text,
                    "interval_ms": interval_ms
                })
        
        return strings, char_interval_ms
    
    def _load_config(self):
        """从配置管理器加载配置并填充到界面"""
        config = self.config_manager.load_config()
        
        # 加载快捷键配置
        self.current_hotkey = config.get("hotkey", "f1")
        
        # 加载字符间隔
        self.char_interval_entry.delete(0, tk.END)
        self.char_interval_entry.insert(0, str(config.get("char_interval_ms", 1)))
        
        # 清空现有卡片
        for card_info in self.string_cards[:]:
            self._remove_string_card(card_info["frame"])
        
        # 加载字符串列表
        strings = config.get("strings", [])
        if not strings:
            # 如果没有字符串，添加一个空卡片
            self._add_string_card()
        else:
            for string_item in strings:
                text = string_item.get("text", "")
                interval_ms = string_item.get("interval_ms", 100)
                self._add_string_card(text, interval_ms)
    
    def _save_config(self):
        """保存当前界面配置"""
        try:
            strings, char_interval_ms = self._get_all_strings()
        except ValueError as e:
            messagebox.showerror("错误", str(e))
            return
        
        if not strings:
            messagebox.showwarning("警告", "至少需要添加一个字符串")
            return
        
        self.config_manager.save_config(strings, char_interval_ms, self.current_hotkey)
        messagebox.showinfo("成功", "配置已保存")
    
    def _start_input(self):
        """启动输入循环"""
        try:
            strings, char_interval_ms = self._get_all_strings()
        except ValueError as e:
            messagebox.showerror("错误", str(e))
            return
        
        if not strings:
            messagebox.showwarning("警告", "至少需要添加一个字符串")
            return
        
        self.input_controller.start(strings, char_interval_ms)
        self._update_status("状态: 运行中")
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL, text="暂停")
        self.stop_button.config(state=tk.NORMAL)
    
    def _pause_resume_input(self):
        """暂停/恢复输入循环"""
        if self.input_controller.is_paused():
            self.input_controller.resume()
            self._update_status("状态: 运行中")
            self.pause_button.config(text="暂停")
        else:
            self.input_controller.pause()
            self._update_status("状态: 已暂停")
            self.pause_button.config(text="恢复")
    
    def _stop_input(self):
        """紧急停止输入循环"""
        self.input_controller.stop()
        self._update_status("状态: 已停止")
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="暂停")
        self.stop_button.config(state=tk.DISABLED)
    
    def _toggle_by_hotkey(self):
        """快捷键回调，切换启动/暂停状态"""
        if not self.input_controller.is_running():
            # 如果未运行，启动
            self._start_input()
        elif self.input_controller.is_paused():
            # 如果暂停，恢复
            self.input_controller.resume()
            self._update_status("状态: 运行中")
            self.pause_button.config(text="暂停")
        else:
            # 如果运行中，暂停
            self.input_controller.pause()
            self._update_status("状态: 已暂停")
            self.pause_button.config(text="恢复")
    
    def _update_status(self, status: str):
        """更新状态标签显示"""
        self.status_label.config(text=status, bg=COLOR_SCHEME['bg_main'])
        if "运行中" in status:
            self.status_label.config(fg=COLOR_SCHEME['btn_success'])
        elif "已暂停" in status:
            self.status_label.config(fg="#F57C00")  # 深橙色
        elif "已停止" in status:
            self.status_label.config(fg=COLOR_SCHEME['btn_danger'])
        else:
            self.status_label.config(fg="#9E9E9E")  # 灰色
    
    def _start_hotkey_listener(self):
        """启动全局快捷键监听"""
        self.hotkey_listener = HotkeyListener(self._toggle_by_hotkey, self.current_hotkey)
        self.hotkey_listener.start()
    
    def _restart_hotkey_listener(self):
        """重启全局快捷键监听（用于快捷键变更）"""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self._start_hotkey_listener()
    
    def _change_hotkey(self):
        """修改快捷键"""
        # 暂停当前监听，避免冲突
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        
        # 打开快捷键录制对话框
        dialog = HotkeyRecorderDialog(self.root)
        self.root.wait_window(dialog)
        
        # 获取结果
        if dialog.result:
            old_hotkey = self.current_hotkey
            self.current_hotkey = dialog.result
            self.hotkey_display.config(text=f"当前: {self.current_hotkey.upper()}")
            
            # 保存配置
            try:
                strings, char_interval_ms = self._get_all_strings()
                self.config_manager.save_config(strings, char_interval_ms, self.current_hotkey)
                messagebox.showinfo("成功", f"快捷键已更改为: {self.current_hotkey.upper()}")
            except ValueError:
                # 如果获取字符串失败，至少保存快捷键
                config = self.config_manager.load_config()
                self.config_manager.save_config(
                    config.get("strings", []), 
                    config.get("char_interval_ms", 1), 
                    self.current_hotkey
                )
                messagebox.showinfo("成功", f"快捷键已更改为: {self.current_hotkey.upper()}")
        
        # 重启监听
        self._restart_hotkey_listener()
    
    def on_closing(self):
        """窗口关闭事件处理，停止所有线程和监听器"""
        self.input_controller.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.destroy()
    
    def run(self):
        """运行GUI主循环"""
        self.root.mainloop()
