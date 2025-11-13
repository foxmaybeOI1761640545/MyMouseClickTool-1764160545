import json
import os


class ConfigManager:
    """配置管理器，负责保存和加载配置"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认为 config.json
        """
        self.config_file = config_file
        self.default_config = {
            "text": "",
            "interval_ms": 1000
        }
    
    def load_config(self) -> dict:
        """
        加载配置文件
        
        Returns:
            dict: 配置字典，如果文件不存在则返回默认配置
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保配置包含所有必需的键
                    for key in self.default_config:
                        if key not in config:
                            config[key] = self.default_config[key]
                    return config
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载配置失败: {e}，使用默认配置")
                return self.default_config.copy()
        else:
            return self.default_config.copy()
    
    def save_config(self, text: str, interval_ms: int):
        """
        保存配置到文件
        
        Args:
            text: 要保存的字符串内容
            interval_ms: 时间间隔（毫秒）
        """
        config = {
            "text": text,
            "interval_ms": interval_ms
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"保存配置失败: {e}")

