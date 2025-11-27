from pynput import keyboard
from pynput.keyboard import Key


class HotkeyListener:
    """全局快捷键监听器"""
    
    def __init__(self, callback: callable, hotkey: str = "f1"):
        """
        初始化快捷键监听器
        
        Args:
            callback: 当按下快捷键时调用的回调函数
            hotkey: 快捷键字符串，如 "f1", "f2" 等
        """
        self.callback = callback
        self.hotkey = hotkey.lower()
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
            # 获取按键名称
            key_name = None
            if hasattr(key, 'name'):
                key_name = key.name.lower()
            elif hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
            
            # 比较按键与设置的快捷键
            if key_name and key_name == self.hotkey:
                if self.callback:
                    self.callback()
        except AttributeError:
            # 处理特殊键
            pass
