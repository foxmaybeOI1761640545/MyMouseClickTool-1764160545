# -*- coding: utf-8 -*-
"""
backend.py - WaveNumberOCR 后端逻辑（EasyOCR 加强版）

负责：
- 根据屏幕坐标截取指定区域图像
- 调用 EasyOCR 识别文字（带简单图像预处理）
- 从识别结果中解析出 “第…波” 中间的波次数字（支持阿拉伯数字 + 中文数字）
"""

from typing import Optional, Tuple, List
import re

import mss
from PIL import Image, ImageEnhance, ImageOps
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
    """

    def __init__(
        self,
        languages: Optional[List[str]] = None,
        gpu: bool = False,
        debug: bool = False,
    ):
        """
        :param languages: OCR 语言列表，默认 ['ch_sim', 'en']（简体中文 + 英文）
        :param gpu: 是否使用 GPU，默认 False（纯 CPU 即可）
        :param debug: 是否输出调试信息（打印 EasyOCR 原始结果等）
        """
        if languages is None:
            languages = ["ch_sim", "en"]

        self.reader = easyocr.Reader(languages, gpu=gpu)
        self.debug = debug

    # ------------ 截屏相关 ------------

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

        img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        return img

    # ------------ 图像预处理 + OCR ------------

    @staticmethod
    def _preprocess_for_ocr(image: Image.Image) -> Image.Image:
        """
        针对游戏 UI 做一些简单预处理，提升 OCR 成功率：
        - 放大 2~3 倍
        - 自动对比度
        - 略微增强对比度和亮度
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        w, h = image.size
        # 选区本身不算太大，可以适当放大
        if w < 400:
            scale = 3
        else:
            scale = 2
        image = image.resize((w * scale, h * scale), Image.BICUBIC)

        # 自动对比度 + 提升对比度 / 亮度
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.6)
        image = ImageEnhance.Brightness(image).enhance(1.1)

        return image

    def ocr_text(self, image: Image.Image) -> str:
        """
        对图像执行 OCR，返回识别出的长文本。
        """
        image = self._preprocess_for_ocr(image)
        np_img = np.array(image)

        # detail=0 只返回文字列表；paragraph=True 尝试合并成段落
        results = self.reader.readtext(np_img, detail=0, paragraph=True)

        if self.debug:
            print("=== [DEBUG] EasyOCR 识别结果列表 ===")
            for idx, txt in enumerate(results):
                print(f"  [{idx}] {repr(txt)}")
            print("=== [DEBUG] =======================")

        text = "\n".join(results)
        if self.debug:
            print("=== [DEBUG] 拼接后的文本 ===")
            print(text)
            print("=== [DEBUG END] ===")

        return text

    # ------------ 文本解析：从 OCR 文本中提取波次 ------------

    @staticmethod
    def _normalize_common_misread(text: str) -> str:
        """
        处理一些 OCR 常见误识别：
        - 把 I / l / | 视作数字 1
        """
        replacements = {
            "I": "1",
            "l": "1",
            "|": "1",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    @staticmethod
    def _chinese_numeral_to_int(s: str) -> Optional[int]:
        """
        将简单的中文数字（零一二三四五六七八九十两）转换成整数。
        只覆盖波次数常见范围（1~99）即可。
        """
        s = s.replace("两", "二")  # “两”按 2 处理

        digits = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
                  "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

        if not s:
            return None

        # 纯数字型，如 “二三” -> 23
        if all(ch in digits for ch in s):
            return int("".join(str(digits[ch]) for ch in s))

        # 含“十”的情况
        if "十" in s:
            parts = s.split("十")
            # “十” -> 10
            if len(parts) == 2 and parts[0] == "" and parts[1] == "":
                return 10

            # “十X” -> 10 + X
            if parts[0] == "":
                tens = 1
            else:
                if parts[0] not in digits:
                    return None
                tens = digits[parts[0]]

            ones = 0
            if len(parts) > 1 and parts[1]:
                if parts[1] not in digits:
                    return None
                ones = digits[parts[1]]

            return tens * 10 + ones

        return None

    @classmethod
    def parse_wave_number(cls, text: str) -> Optional[str]:
        """
        从文本中解析 “第X波”，返回 X（阿拉伯数字字符串）。
        若未找到则返回 None。
        """
        # 先做一次常见误识别归一化
        normalized = cls._normalize_common_misread(text)

        # 1. 优先匹配阿拉伯数字形式：第 1 波
        pattern_digit = re.compile(r"第\s*([0-9]{1,4})\s*波", re.DOTALL)
        match = pattern_digit.search(normalized)
        if match:
            return match.group(1)

        # 2. 兼容中文数字形式：第一波、第十二波 等
        pattern_cn = re.compile(r"第\s*([零一二三四五六七八九十两]+)\s*波", re.DOTALL)
        match = pattern_cn.search(text)
        if match:
            num = cls._chinese_numeral_to_int(match.group(1))
            if num is not None:
                return str(num)

        # 3. 宽松一点的回退规则：
        #    例如 OCR 把 “波” 识别成 “坡”等
        pattern_loose = re.compile(r"[第弟]\s*([0-9]{1,4})\s*[波坡]", re.DOTALL)
        match = pattern_loose.search(normalized)
        if match:
            return match.group(1)

        return None

    # ------------ 封装的一键调用 ------------

    def capture_and_recognize(self, x1: int, y1: int, x2: int, y2: int) -> Optional[str]:
        """
        综合方法：截屏并识别 “第X波”，返回 X 或 None。
        """
        img = self.capture_region(x1, y1, x2, y2)
        text = self.ocr_text(img)
        number = self.parse_wave_number(text)
        return number
