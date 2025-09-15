#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
场记单OCR处理系统 - 主程序入口
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_window import main

if __name__ == "__main__":
    main() 