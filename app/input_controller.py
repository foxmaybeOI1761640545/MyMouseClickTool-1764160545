import threading
import time
import ctypes
from ctypes import wintypes
from pynput.keyboard import Controller, Key

# Windows API 常量
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0

# Windows API 虚拟键码
VK_SPACE = 0x20
VK_RETURN = 0x0D
VK_TAB = 0x09

# 数字键盘虚拟键码 (Numpad)
VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_NUMPAD3 = 0x63
VK_NUMPAD4 = 0x64
VK_NUMPAD5 = 0x65
VK_NUMPAD6 = 0x66
VK_NUMPAD7 = 0x67
VK_NUMPAD8 = 0x68
VK_NUMPAD9 = 0x69

# 定义 Windows API 结构
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]

# 定义 SendInput 函数
user32 = ctypes.windll.user32
SendInput = user32.SendInput
SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
SendInput.restype = wintypes.UINT

# 定义 MapVirtualKey 函数，用于将虚拟键码转换为扫描码
MapVirtualKey = user32.MapVirtualKeyW
MapVirtualKey.argtypes = [wintypes.UINT, wintypes.UINT]
MapVirtualKey.restype = wintypes.UINT


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
        # 按键保持时间（毫秒），模拟真实按键按下时间
        self.key_hold_time_ms = 25
    
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
    
    def _get_vk_code(self, char: str) -> int:
        """
        将字符转换为Windows虚拟键码
        
        Args:
            char: 单个字符
            
        Returns:
            int: Windows虚拟键码
        """
        char_upper = char.upper()
        
        # 字母键 A-Z (0x41-0x5A)
        if 'A' <= char_upper <= 'Z':
            return ord(char_upper)
        
        # 数字键 0-9 - 使用数字键盘虚拟键码 (0x60-0x69)
        # 这样某些应用程序才能正确识别数字键盘输入
        numpad_map = {
            '0': VK_NUMPAD0,
            '1': VK_NUMPAD1,
            '2': VK_NUMPAD2,
            '3': VK_NUMPAD3,
            '4': VK_NUMPAD4,
            '5': VK_NUMPAD5,
            '6': VK_NUMPAD6,
            '7': VK_NUMPAD7,
            '8': VK_NUMPAD8,
            '9': VK_NUMPAD9,
        }
        if '0' <= char <= '9':
            return numpad_map[char]
        
        # 特殊字符映射
        special_chars = {
            ' ': VK_SPACE,
            '\n': VK_RETURN,
            '\t': VK_TAB,
        }
        
        if char in special_chars:
            return special_chars[char]
        
        # 如果无法映射，返回字符的ASCII码（可能不准确，但作为后备）
        return ord(char_upper)
    
    def _parse_key(self, char: str):
        """
        将字符解析为对应的按键对象（保留用于兼容性）
        
        Args:
            char: 单个字符
            
        Returns:
            字符本身（现在使用虚拟键码）
        """
        return char
    
    def _is_numpad_key(self, vk_code: int) -> bool:
        """
        判断是否是数字键盘按键
        
        Args:
            vk_code: Windows虚拟键码
            
        Returns:
            bool: 如果是数字键盘按键返回 True
        """
        return VK_NUMPAD0 <= vk_code <= VK_NUMPAD9
    
    def _send_key_input(self, vk_code: int, key_down: bool):
        """
        使用Windows API SendInput发送按键事件
        
        Args:
            vk_code: Windows虚拟键码
            key_down: True表示按下，False表示释放
        """
        # 判断是否是数字键盘按键
        is_numpad = self._is_numpad_key(vk_code)
        
        if is_numpad:
            # 对于数字键盘按键，使用扫描码模式以确保游戏能正确识别
            # 获取扫描码
            scan_code = MapVirtualKey(vk_code, MAPVK_VK_TO_VSC)
            flags = KEYEVENTF_SCANCODE
            if not key_down:
                flags |= KEYEVENTF_KEYUP
            
            # 创建输入结构（使用扫描码模式时，wVk 应设为 0）
            extra = ctypes.c_ulong(0)
            ki = KEYBDINPUT(
                wVk=wintypes.WORD(0),
                wScan=wintypes.WORD(scan_code),
                dwFlags=wintypes.DWORD(flags),
                time=wintypes.DWORD(0),
                dwExtraInfo=ctypes.pointer(extra),
            )
        else:
            # 对于其他按键，使用虚拟键码模式
            flags = 0 if key_down else KEYEVENTF_KEYUP
            
            # 创建输入结构
            extra = ctypes.c_ulong(0)
            ki = KEYBDINPUT(
                wVk=wintypes.WORD(vk_code),
                wScan=wintypes.WORD(0),
                dwFlags=wintypes.DWORD(flags),
                time=wintypes.DWORD(0),
                dwExtraInfo=ctypes.pointer(extra),
            )
        
        union = INPUT_UNION(ki=ki)
        x = INPUT(
            type=INPUT_KEYBOARD,
            union=union,
        )
        
        # 发送输入
        result = SendInput(1, ctypes.pointer(x), ctypes.sizeof(INPUT))
        return result
    
    def _press_key(self, key):
        """
        模拟按键按下和释放（使用Windows API）
        
        Args:
            key: 按键对象或字符
        """
        try:
            # 如果是字符，转换为虚拟键码
            if isinstance(key, str):
                vk_code = self._get_vk_code(key)
            else:
                # 如果是Key对象，尝试转换为虚拟键码（简化处理）
                # 这里可以扩展支持更多特殊键
                if key == Key.space:
                    vk_code = VK_SPACE
                elif key == Key.enter:
                    vk_code = VK_RETURN
                elif key == Key.tab:
                    vk_code = VK_TAB
                else:
                    # 如果无法识别，使用pynput作为后备
                    self.controller.press(key)
                    time.sleep(self.key_hold_time_ms / 1000.0)
                    self.controller.release(key)
                    return
            
            # 使用Windows API发送按键
            # 按下按键
            self._send_key_input(vk_code, True)
            # 保持按键一段时间（模拟真实按键）
            time.sleep(self.key_hold_time_ms / 1000.0)
            # 释放按键
            self._send_key_input(vk_code, False)
        except Exception as e:
            print(f"按键错误: {e}")
            # 如果Windows API失败，尝试使用pynput作为后备
            try:
                if isinstance(key, str):
                    self.controller.type(key)
                else:
                    self.controller.press(key)
                    time.sleep(self.key_hold_time_ms / 1000.0)
                    self.controller.release(key)
            except Exception as e2:
                print(f"后备按键方法也失败: {e2}")
    
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
                            # 使用按键输入而非文本输入
                            parsed_key = self._parse_key(char)
                            self._press_key(parsed_key)
                            # 字符间隔（最后一个字符后不需要间隔）
                            if char != text[-1] and self.running.is_set():
                                time.sleep(self.char_interval_ms / 1000.0)
                    except Exception as e:
                        print(f"输入错误: {e}")
                        break
                
                # 字符串输入完成后，等待该字符串的间隔时间
                if self.running.is_set() and string_item != self.strings[-1]:
                    interval_ms = string_item.get("interval_ms", 100)
                    time.sleep(interval_ms / 1000.0)
            
            # 所有字符串输入完成后，如果还在运行，继续循环
            if not self.running.is_set():
                break

