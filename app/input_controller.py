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
        self.strings = []
        self.char_interval_ms = 1
        self.thread = None
    
    def start(self, strings: list, char_interval_ms: int):
        """
        启动输入循环
        
        Args:
            strings: 字符串列表，每个元素为 {"text": str, "interval_ms": int}
            char_interval_ms: 字符间隔（毫秒）
        """
        if self.running.is_set():
            return
        
        self.strings = strings
        self.char_interval_ms = char_interval_ms
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
            # 遍历所有字符串
            for string_item in self.strings:
                # 如果暂停，等待恢复
                while self.paused.is_set() and self.running.is_set():
                    time.sleep(0.1)
                
                if not self.running.is_set():
                    break
                
                text = string_item.get("text", "")
                if text:
                    # 逐字符输入，使用字符间隔
                    try:
                        for char in text:
                            if not self.running.is_set():
                                break
                            # 如果暂停，等待恢复
                            while self.paused.is_set() and self.running.is_set():
                                time.sleep(0.1)
                            if not self.running.is_set():
                                break
                            self.controller.type(char)
                            # 字符间隔（最后一个字符后不需要间隔）
                            if char != text[-1] and self.running.is_set():
                                time.sleep(self.char_interval_ms / 100.0)
                    except Exception as e:
                        print(f"输入错误: {e}")
                        break
                
                # 字符串输入完成后，等待该字符串的间隔时间
                if self.running.is_set() and string_item != self.strings[-1]:
                    interval_ms = string_item.get("interval_ms", 100)
                    time.sleep(interval_ms / 100.0)
            
            # 所有字符串输入完成后，如果还在运行，继续循环
            if not self.running.is_set():
                break

