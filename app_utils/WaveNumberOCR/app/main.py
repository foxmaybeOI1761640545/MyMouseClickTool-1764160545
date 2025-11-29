# -*- coding: utf-8 -*-
"""
main.py - WaveNumberOCR 程序入口

负责：
- 创建后端 ScreenTextRecognizer 实例
- 创建并启动前端 WaveNumberApp 界面
"""

from backend import ScreenTextRecognizer
from gui import WaveNumberApp


def main() -> None:
    """
    程序入口。
    """
    # 如果 Tesseract 没有加入系统 PATH，可在此手动指定路径，例如：
    # recognizer = ScreenTextRecognizer(
    #     tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    # )
    recognizer = ScreenTextRecognizer(debug=True)

    app = WaveNumberApp(recognizer)
    app.run()


if __name__ == "__main__":
    main()
