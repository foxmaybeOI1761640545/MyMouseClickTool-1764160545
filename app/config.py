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
            "strings": [],
            "char_interval_ms": 100
        }
    
    def _migrate_old_config(self, config: dict) -> dict:
        """
        将旧配置格式迁移为新格式
        
        Args:
            config: 旧配置字典
            
        Returns:
            dict: 新格式配置字典
        """
        # 如果配置中有旧的text和interval_ms，说明是旧格式
        if "text" in config and "strings" not in config:
            new_config = {
                "strings": [
                    {
                        "text": config.get("text", ""),
                        "interval_ms": config.get("interval_ms", 100)
                    }
                ],
                "char_interval_ms": config.get("char_interval_ms", 1)
            }
            return new_config
        # 如果是新格式但缺少某些字段，补充默认值
        if "strings" not in config:
            config["strings"] = []
        if "char_interval_ms" not in config:
            config["char_interval_ms"] = 1
        return config
    
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
                    # 迁移旧配置格式
                    config = self._migrate_old_config(config)
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
    
    def save_config(self, strings: list, char_interval_ms: int):
        """
        保存配置到文件
        
        Args:
            strings: 字符串列表，每个元素为 {"text": str, "interval_ms": int}
            char_interval_ms: 字符间隔（毫秒）
        """
        config = {
            "strings": strings,
            "char_interval_ms": char_interval_ms
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"保存配置失败: {e}")

