# -*- coding: utf-8 -*-
"""
backend.py - WaveNumberOCR 后端逻辑（EasyOCR 版）

负责：
- 根据屏幕坐标截取指定区域图像
- 调用 EasyOCR 识别文字
- 从识别结果中解析出 “第…波” 中间的阿拉伯数字
"""

from typing import Optional, Tuple, List
import re

import mss
from PIL import Image
import numpy as np
import easyocr


class ScreenCaptureError(Exception):
    """自定义异常：截屏相关错误."""
    pass


class ScreenTextRecognizer:
    """
    屏幕文字识别器：
    - 截取屏幕指定区域
    - OCR 识别
    - 解析 “第X波” 中的 X（阿拉伯数字）

    使用 EasyOCR，不再依赖外部 Tesseract 可执行程序。
    """

    def __init__(self, languages: Optional[List[str]] = None, gpu: bool = False):
        """
        :param languages: OCR 语言列表，默认 ['ch_sim', 'en']（简体中文 + 英文）
        :param gpu: 是否使用 GPU，默认 False（纯 CPU 即可）
        """
        if languages is None:
            languages = ["ch_sim", "en"]

        # 初始化 EasyOCR 的 Reader（比较耗时，建议整个程序只初始化一次）
        self.reader = easyocr.Reader(languages, gpu=gpu)

    @staticmethod
    def normalize_box(x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int, int]:
        """
        将任意两个对角坐标标准化为 (left, top, right, bottom).
        """
        left = int(min(x1, x2))
        top = int(min(y1, y2))
        right = int(max(x1, x2))
        bottom = int(max(y1, y2))
        return left, top, right, bottom

    def capture_region(self, x1: int, y1: int, x2: int, y2: int) -> Image.Image:
        """
        截取屏幕指定区域并返回为 PIL Image 对象。

        :raises ScreenCaptureError: 坐标不合法或截屏失败时抛出。
        """
        left, top, right, bottom = self.normalize_box(x1, y1, x2, y2)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            raise ScreenCaptureError(f"截屏区域宽高必须为正数，目前 width={width}, height={height}")

        try:
            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                sct_img = sct.grab(monitor)
        except Exception as exc:  # pylint: disable=broad-except
            raise ScreenCaptureError(f"执行截屏时出现错误: {exc}") from exc

        # mss 返回的是原始 RGB bytes，这里转成 PIL Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        return img

    def ocr_text(self, image: Image.Image) -> str:
        """
        对图像执行 OCR，返回识别出的文本（用换行拼成一个字符串）。
        使用 EasyOCR 的 reader.readtext。
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        # EasyOCR 接受 numpy 数组
        np_img = np.array(image)

        # detail=0 只返回文字列表，如 ["第3波", "其它字..."]
        results = self.reader.readtext(np_img, detail=0)

        # 将所有识别结果拼成一个长文本，方便后面用正则匹配
        text = "\n".join(results)
        return text

    @staticmethod
    def parse_wave_number(text: str) -> Optional[str]:
        """
        从文本中解析 “第X波” 模式，并返回 X（阿拉伯数字）字符串。
        若未找到则返回 None。

        支持：
        - “第3波”
        - “第 3 波”
        - “第\n12\n波” 等含空白/换行情况
        """
        # 使用 DOTALL 允许跨行匹配；\s* 匹配空格/换行等
        pattern = re.compile(r"第\s*([0-9]+)\s*波", re.DOTALL)
        match = pattern.search(text)
        if match:
            return match.group(1)
        return None

    def capture_and_recognize(self, x1: int, y1: int, x2: int, y2: int) -> Optional[str]:
        """
        综合方法：截屏并识别 “第X波”，返回 X 或 None。
        """
        img = self.capture_region(x1, y1, x2, y2)
        text = self.ocr_text(img)
        number = self.parse_wave_number(text)
        return number
