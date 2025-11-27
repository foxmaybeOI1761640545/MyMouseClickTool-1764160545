# backend.py
"""
ScreenRegionMarker 后端模块

负责：
- 定义区域数据结构 Region
- 加载 / 保存区域到 JSON 文件
- 一些小工具函数
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Optional

# 默认保存的文件名（在程序当前目录）
DEFAULT_STORAGE_FILE = "regions.json"


@dataclass
class Region:
    """表示一块屏幕区域"""
    name: str
    left: int
    top: int
    width: int
    height: int
    # 软删除标记：True 表示在 GUI 中隐藏，但仍保留在文件中
    deleted: bool = False

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


def create_region_from_points(
    name: str,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> Region:
    """
    根据两点坐标创建一个 Region，自动计算左上角 + 宽高
    """
    left = min(x1, x2)
    top = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    return Region(name=name, left=left, top=top, width=width, height=height)


def load_regions(path: str = DEFAULT_STORAGE_FILE) -> Dict[str, Region]:
    """
    从 JSON 文件中加载所有区域，返回 dict[name, Region]

    文件结构示例：
    {
        "示例范围": {
            "left": 100,
            "top": 200,
            "width": 300,
            "height": 400,
            "deleted": false
        }
    }
    """
    regions: Dict[str, Region] = {}

    if not os.path.exists(path):
        return regions

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # 解析失败就当没有
        return regions

    if not isinstance(data, dict):
        return regions

    for name, info in data.items():
        if not isinstance(info, dict):
            continue

        try:
            left = int(info["left"])
            top = int(info["top"])
            width = int(info["width"])
            height = int(info["height"])
            deleted = bool(info.get("deleted", False))
        except (KeyError, TypeError, ValueError):
            continue

        regions[name] = Region(
            name=name,
            left=left,
            top=top,
            width=width,
            height=height,
            deleted=deleted,
        )

    return regions


def save_regions(regions: Dict[str, Region], path: str = DEFAULT_STORAGE_FILE) -> None:
    """
    将所有 Region 写入 JSON 文件。

    注意：包括已软删除的区域（deleted=True），便于之后从文件恢复。
    """
    data = {}
    for name, region in regions.items():
        item = {
            "left": region.left,
            "top": region.top,
            "width": region.width,
            "height": region.height,
        }
        if region.deleted:
            item["deleted"] = True
        data[name] = item

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def format_region(region: Region) -> str:
    """
    将 Region 格式化为中文描述字符串
    """
    return (
        f"left={region.left}, top={region.top}, "
        f"width={region.width}, height={region.height} "
        f"(right={region.right}, bottom={region.bottom})"
    )


def get_region_by_name(
    regions: Dict[str, Region],
    name: str,
) -> Optional[Region]:
    """
    安全地从字典中获取 Region
    """
    return regions.get(name)
