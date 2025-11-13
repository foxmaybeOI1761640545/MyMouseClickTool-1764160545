import tkinter as tk
from tkinter import messagebox
import threading
from app.config import ConfigManager
from app.input_controller import InputController
from app.hotkey_listener import HotkeyListener


class AutoInputGUI:
    """自动输入工具GUI界面"""
    
    def __init__(self):
        """初始化GUI"""
        self.root = tk.Tk()
        self.root.title("自动输入工具")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        # 初始化组件
        self.config_manager = ConfigManager()
        self.input_controller = InputController()
        self.hotkey_listener = None
        
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
        # 文本输入区域
        text_label = tk.Label(self.root, text="输入字符串:", font=("Arial", 10))
        text_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.text_entry = tk.Text(self.root, height=5, width=50, wrap=tk.WORD)
        self.text_entry.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        
        # 间隔时间输入
        interval_label = tk.Label(self.root, text="时间间隔(毫秒):", font=("Arial", 10))
        interval_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        
        self.interval_entry = tk.Entry(self.root, width=20)
        self.interval_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        # 状态显示
        self.status_label = tk.Label(self.root, text="状态: 未运行", font=("Arial", 10), fg="gray")
        self.status_label.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
        
        # 按钮区域
        button_frame = tk.Frame(self.root)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
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
        save_button.grid(row=5, column=0, columnspan=2, pady=10)
        
        # 快捷键提示
        hotkey_label = tk.Label(self.root, text="提示: 按 F1 键可启动/暂停", 
                               font=("Arial", 9), fg="blue")
        hotkey_label.grid(row=6, column=0, columnspan=2, pady=5)
        
        # 配置列权重
        self.root.columnconfigure(0, weight=1)
    
    def _load_config(self):
        """从配置管理器加载配置并填充到界面"""
        config = self.config_manager.load_config()
        self.text_entry.delete("1.0", tk.END)
        self.text_entry.insert("1.0", config.get("text", ""))
        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, str(config.get("interval_ms", 1000)))
    
    def _save_config(self):
        """保存当前界面配置"""
        text = self.text_entry.get("1.0", tk.END).strip()
        try:
            interval_ms = int(self.interval_entry.get().strip())
            if interval_ms <= 0:
                messagebox.showerror("错误", "时间间隔必须大于0")
                return
        except ValueError:
            messagebox.showerror("错误", "时间间隔必须是有效的正整数")
            return
        
        self.config_manager.save_config(text, interval_ms)
        messagebox.showinfo("成功", "配置已保存")
    
    def _start_input(self):
        """启动输入循环"""
        text = self.text_entry.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("警告", "请输入要循环的字符串")
            return
        
        try:
            interval_ms = int(self.interval_entry.get().strip())
            if interval_ms <= 0:
                messagebox.showerror("错误", "时间间隔必须大于0")
                return
        except ValueError:
            messagebox.showerror("错误", "时间间隔必须是有效的正整数")
            return
        
        self.input_controller.start(text, interval_ms)
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

