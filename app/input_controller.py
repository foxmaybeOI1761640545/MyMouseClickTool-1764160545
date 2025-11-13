import threading
import time
from pynput.keyboard import Controller


class InputController:
    """输入控制器，负责控制字符串输入循环"""
    
    def __init__(self):
        """初始化输入控制器"""
        self.controller = Controller()
        self.running = threading.Event()
        self.paused = threading.Event()
        self.text = ""
        self.interval_ms = 1000
        self.thread = None
    
    def start(self, text: str, interval_ms: int):
        """
        启动输入循环
        
        Args:
            text: 要输入的字符串
            interval_ms: 时间间隔（毫秒）
        """
        if self.running.is_set():
            return
        
        self.text = text
        self.interval_ms = interval_ms
        self.running.set()
        self.paused.clear()
        
        self.thread = threading.Thread(target=self._input_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止输入循环（紧急停止）"""
        self.running.clear()
        self.paused.clear()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
    
    def pause(self):
        """暂停输入循环"""
        self.paused.set()
    
    def resume(self):
        """恢复输入循环"""
        self.paused.clear()
    
    def is_running(self) -> bool:
        """
        检查是否正在运行
        
        Returns:
            bool: 如果正在运行返回 True
        """
        return self.running.is_set()
    
    def is_paused(self) -> bool:
        """
        检查是否暂停
        
        Returns:
            bool: 如果暂停返回 True
        """
        return self.paused.is_set() and self.running.is_set()
    
    def _input_loop(self):
        """输入循环逻辑（在独立线程中运行）"""
        while self.running.is_set():
            # 如果暂停，等待恢复
            while self.paused.is_set() and self.running.is_set():
                time.sleep(0.1)
            
            if not self.running.is_set():
                break
            
            # 输入字符串
            try:
                self.controller.type(self.text)
            except Exception as e:
                print(f"输入错误: {e}")
                break
            
            # 等待指定时间间隔
            if self.running.is_set():
                time.sleep(self.interval_ms / 1000.0)

