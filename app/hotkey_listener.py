from pynput import keyboard
from pynput.keyboard import Key


class HotkeyListener:
    """全局快捷键监听器"""
    
    def __init__(self, callback: callable):
        """
        初始化快捷键监听器
        
        Args:
            callback: 当按下F1时调用的回调函数
        """
        self.callback = callback
        self.listener = None
        self.is_listening = False
    
    def start(self):
        """开始监听全局快捷键"""
        if self.is_listening:
            return
        
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()
        self.is_listening = True
    
    def stop(self):
        """停止监听全局快捷键"""
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.is_listening = False
    
    def _on_press(self, key):
        """
        处理按键事件
        
        Args:
            key: 按下的键
        """
        try:
            if key == Key.f1:
                if self.callback:
                    self.callback()
        except AttributeError:
            # 处理特殊键
            pass

