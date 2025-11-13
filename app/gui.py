import tkinter as tk
from tkinter import messagebox, ttk
import threading
from app.config import ConfigManager
from app.input_controller import InputController
from app.hotkey_listener import HotkeyListener


class ScrollableFrame(tk.Frame):
    """可滚动的Frame"""
    
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        
        # 创建Canvas和滚动条
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
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
        self.root.geometry("650x650")
        self.root.resizable(True, True)
        
        # 初始化组件
        self.config_manager = ConfigManager()
        self.input_controller = InputController()
        self.hotkey_listener = None
        
        # 存储字符串卡片的列表
        self.string_cards = []
        
        # 创建GUI组件
        self._create_widgets()
        
        # 加载配置
        self._load_config()
        
        # 启动全局快捷键监听
        self._start_hotkey_listener()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _create_widgets(self):
        """创建并布局所有GUI组件"""
        # 顶部：字符间隔设置
        char_interval_frame = tk.Frame(self.root)
        char_interval_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        char_interval_label = tk.Label(char_interval_frame, text="字符间隔(毫秒):", font=("Arial", 10))
        char_interval_label.pack(side=tk.LEFT, padx=5)
        
        self.char_interval_entry = tk.Entry(char_interval_frame, width=15)
        self.char_interval_entry.pack(side=tk.LEFT, padx=5)
        self.char_interval_entry.insert(0, "1")
        
        # 中间：可滚动的字符串列表区域
        strings_label = tk.Label(self.root, text="字符串列表:", font=("Arial", 10))
        strings_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        
        # 创建可滚动区域
        self.scrollable_frame = ScrollableFrame(self.root)
        self.scrollable_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")
        
        # 添加字符串按钮
        add_button = tk.Button(self.root, text="+ 添加字符串", command=self._add_string_card, 
                              width=15, height=1, font=("Arial", 9), bg="#2196F3", fg="white")
        add_button.grid(row=3, column=0, columnspan=2, pady=5)
        
        # 状态显示
        self.status_label = tk.Label(self.root, text="状态: 未运行", font=("Arial", 10), fg="gray")
        self.status_label.grid(row=4, column=0, columnspan=2, padx=10, pady=10)
        
        # 控制按钮区域
        button_frame = tk.Frame(self.root)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        self.start_button = tk.Button(button_frame, text="启动", command=self._start_input, 
                                      width=10, height=2, bg="#4CAF50", fg="white", font=("Arial", 10))
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = tk.Button(button_frame, text="暂停", command=self._pause_resume_input, 
                                     width=10, height=2, bg="#FF9800", fg="white", font=("Arial", 10), 
                                     state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(button_frame, text="停止", command=self._stop_input, 
                                     width=10, height=2, bg="#F44336", fg="white", font=("Arial", 10), 
                                     state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 保存配置按钮
        save_button = tk.Button(self.root, text="保存配置", command=self._save_config, 
                               width=15, height=1, font=("Arial", 9))
        save_button.grid(row=6, column=0, columnspan=2, pady=5)
        
        # 快捷键提示
        hotkey_label = tk.Label(self.root, text="提示: 按 F1 键可启动/暂停", 
                               font=("Arial", 9), fg="blue")
        hotkey_label.grid(row=7, column=0, columnspan=2, pady=5)
        
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
        # 创建卡片Frame
        card_frame = tk.Frame(self.scrollable_frame.scrollable_frame, relief=tk.RAISED, borderwidth=1)
        card_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 字符串输入区域
        text_label = tk.Label(card_frame, text="字符串:", font=("Arial", 9))
        text_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
        
        text_entry = tk.Text(card_frame, height=2, width=40, wrap=tk.WORD)
        text_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        text_entry.insert("1.0", text)
        
        # 间隔时间输入
        interval_label = tk.Label(card_frame, text="间隔(ms):", font=("Arial", 9))
        interval_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        interval_entry = tk.Entry(card_frame, width=15)
        interval_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        interval_entry.insert(0, str(interval_ms))
        
        # 删除按钮
        delete_button = tk.Button(card_frame, text="删除", command=lambda: self._remove_string_card(card_frame),
                                 width=8, height=1, font=("Arial", 8), bg="#F44336", fg="white")
        delete_button.grid(row=0, column=2, rowspan=2, padx=5, pady=5, sticky="nsew")
        
        # 配置列权重
        card_frame.columnconfigure(1, weight=1)
        
        # 存储卡片信息
        card_info = {
            "frame": card_frame,
            "text_entry": text_entry,
            "interval_entry": interval_entry
        }
        self.string_cards.append(card_info)
    
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
            text = card_info["text_entry"].get("1.0", tk.END).strip()
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
        
        self.config_manager.save_config(strings, char_interval_ms)
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
        self.status_label.config(text=status)
        if "运行中" in status:
            self.status_label.config(fg="green")
        elif "已暂停" in status:
            self.status_label.config(fg="orange")
        elif "已停止" in status:
            self.status_label.config(fg="red")
        else:
            self.status_label.config(fg="gray")
    
    def _start_hotkey_listener(self):
        """启动全局快捷键监听"""
        self.hotkey_listener = HotkeyListener(self._toggle_by_hotkey)
        self.hotkey_listener.start()
    
    def on_closing(self):
        """窗口关闭事件处理，停止所有线程和监听器"""
        self.input_controller.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.destroy()
    
    def run(self):
        """运行GUI主循环"""
        self.root.mainloop()
