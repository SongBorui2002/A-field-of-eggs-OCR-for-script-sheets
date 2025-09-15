#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Otsu算法图像二值化处理
使用方法: python otsu_threshold.py <图像路径>
"""

import cv2
import sys
import os

def otsu_threshold_process(image_path):
    """
    使用Otsu算法进行图像二值化
    """
    # 检查文件是否存在
    if not os.path.exists(image_path):
        print(f"错误：找不到图像文件 {image_path}")
        return
    
    # 读取图像
    img = cv2.imread(image_path)
    if img is None:
        print(f"错误：无法读取图像文件 {image_path}")
        return
    
    # 转换为灰度图像
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 应用Otsu算法
    # cv2.threshold会返回(阈值, 二值化图像)
    otsu_threshold, otsu_binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    
    # 也可以尝试反向二值化（白底黑字变黑底白字）
    _, otsu_binary_inv = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    
    # 生成输出文件名
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_dir = os.path.dirname(image_path)
    
    otsu_output = os.path.join(output_dir, f"{base_name}_otsu.jpg")
    otsu_inv_output = os.path.join(output_dir, f"{base_name}_otsu_inv.jpg")
    
    # 保存结果
    cv2.imwrite(otsu_output, otsu_binary)
    cv2.imwrite(otsu_inv_output, otsu_binary_inv)
    
    print(f"原图像尺寸: {img.shape}")
    print(f"Otsu自动计算的最优阈值: {otsu_threshold:.2f}")
    print(f"Otsu二值化结果已保存到: {otsu_output}")
    print(f"Otsu反向二值化结果已保存到: {otsu_inv_output}")

def main():
    if len(sys.argv) != 2:
        print("使用方法: python otsu_threshold.py <图像路径>")
        print("示例: python otsu_threshold.py ./test_image.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    otsu_threshold_process(image_path)

if __name__ == "__main__":
    main() 