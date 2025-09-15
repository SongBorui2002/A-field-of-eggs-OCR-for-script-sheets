#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成图像处理脚本 - LUT处理 + 表格裁剪
使用方法: 
  单文件: python image_process.py <输入图像路径>
  批量处理: python image_process.py --batch <输入文件夹路径>
"""

import cv2
import numpy as np
import sys
import os
from pathlib import Path
import glob
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import psutil

# LUT处理相关导入
try:
    import colour
except ImportError:
    print("错误：未安装colour-science库")
    print("请运行: pip install colour-science")
    sys.exit(1)

# 支持的图像格式
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}

# LUT文件路径配置
LUT_PATH = "/Users/sbr/Desktop/OCR.cube"

# 裁剪配置
CROP_CONFIG = {
    'h_start': 2,    # 第3根水平线 (索引从0开始)
    'h_end': -1,     # 最后一根水平线
    'v_start': 0,    # 第1根垂直线
    'v_end': 7       # 第8根垂直线
}

def get_optimal_workers():
    """根据系统资源自动确定最佳并行数 - 针对Apple M3 Max优化"""
    cpu_count = multiprocessing.cpu_count()
    available_memory = psutil.virtual_memory().available
    total_memory = psutil.virtual_memory().total
    
    # 检测是否为Apple Silicon (M系列芯片)
    import platform
    is_apple_silicon = platform.machine() == 'arm64' and platform.system() == 'Darwin'
    
    if is_apple_silicon and cpu_count >= 10:  # M3 Max或更高
        # Apple M3 Max优化配置
        # 图像处理在M3 Max上内存使用更高效，但仍需保守估计
        memory_per_image = 250 * 1024 * 1024  # 250MB (M3 Max内存带宽更高)
        
        # 充分利用性能核心，但为系统保留2个核心
        cpu_workers = max(2, cpu_count - 2)
        
        # 内存计算：使用80%的可用内存，为系统预留空间
        safe_memory = int(available_memory * 0.8)
        memory_workers = max(2, safe_memory // memory_per_image)
        
        # Apple Silicon特殊优化：最大并行数可以更高
        max_concurrent = min(cpu_workers, memory_workers, 12)  # M3 Max可支持更多并行
        
        print(f"🚀 Apple M3 Max检测到 - CPU核心: {cpu_count}, 可用内存: {available_memory/(1024**3):.1f}GB")
        print(f"   CPU工作者: {cpu_workers}, 内存工作者: {memory_workers}, 最终: {max_concurrent}")
        
    elif cpu_count >= 8:  # 高性能CPU
        memory_per_image = 300 * 1024 * 1024  # 300MB
        cpu_workers = max(2, cpu_count - 2)
        memory_workers = max(2, available_memory // memory_per_image)
        max_concurrent = min(cpu_workers, memory_workers, 8)
        
    else:  # 普通配置
        memory_per_image = 350 * 1024 * 1024  # 350MB 保守估计
        cpu_workers = max(1, cpu_count - 1)
        memory_workers = max(1, available_memory // memory_per_image)
        max_concurrent = min(cpu_workers, memory_workers, 4)
    
    # 确保至少有1个工作者
    optimal_workers = max(1, max_concurrent)
    
    return optimal_workers

def scan_image_files(folder_path):
    """扫描文件夹中的所有图像文件"""
    image_files = []
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        print(f"错误：文件夹不存在 {folder_path}")
        return []
    
    # 扫描支持的图像格式
    for ext in SUPPORTED_FORMATS:
        pattern = str(folder_path / f"*{ext}")
        image_files.extend(glob.glob(pattern))
        # 也搜索大写扩展名
        pattern = str(folder_path / f"*{ext.upper()}")
        image_files.extend(glob.glob(pattern))
    
    image_files = sorted(list(set(image_files)))  # 去重并排序
    
    return image_files

# ==================== LUT处理算法 ====================

def apply_lut_processing(image_bgr, lut_path):
    """
    应用LUT处理到图像
    输入: BGR格式图像, LUT文件路径
    输出: 处理后的BGR格式图像
    """
    try:
        # 转换为RGB并标准化
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_normalized = image_rgb.astype(np.float32) / 255.0
        
        # 加载LUT
        lut_3d = colour.io.read_LUT(lut_path)
        
        # 应用LUT
        try:
            processed_image = lut_3d.apply(image_normalized)
        except:
            # 备用方法
            height, width, channels = image_normalized.shape
            image_reshaped = image_normalized.reshape(-1, channels)
            processed_reshaped = colour.algebra.table_interpolation_trilinear(
                image_reshaped, lut_3d.table
            )
            processed_image = processed_reshaped.reshape(height, width, channels)
        
        # 裁剪到有效范围
        processed_image = np.clip(processed_image, 0.0, 1.0)
        
        # 转换回uint8格式并转为BGR
        processed_uint8 = (processed_image * 255).astype(np.uint8)
        processed_bgr = cv2.cvtColor(processed_uint8, cv2.COLOR_RGB2BGR)
        
        return processed_bgr
        
    except Exception as e:
        raise Exception(f"LUT处理失败: {str(e)}")

# ==================== 表格检测和裁剪算法 ====================

def detect_lines_improved(binary_image):
    """使用改进的形态学操作检测水平和垂直线条"""
    rows, cols = binary_image.shape
    
    # 检测水平线条
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (cols//10, 1))
    horizontal_lines = cv2.erode(binary_image, horizontal_kernel, iterations=2)
    horizontal_lines = cv2.dilate(horizontal_lines, horizontal_kernel, iterations=2)
    
    # 检测垂直线条
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, rows//10))
    vertical_lines = cv2.erode(binary_image, vertical_kernel, iterations=2)
    vertical_lines = cv2.dilate(vertical_lines, vertical_kernel, iterations=2)
    
    return horizontal_lines, vertical_lines

def get_line_coordinates_improved(lines_image, is_horizontal=True, min_gap=25):
    """从线条图像中提取线条坐标，并去除噪声"""
    if is_horizontal:
        # 水平线：每行所有像素求和
        line_points = np.where(lines_image.sum(axis=1) > 0)[0]
    else:
        # 垂直线：每列所有像素求和
        line_points = np.where(lines_image.sum(axis=0) > 0)[0]
    
    if len(line_points) == 0:
        return []
    
    # 去重
    unique_points = np.unique(line_points)
    
    # 过滤噪声：只保留间隔大于min_gap像素的线条
    filtered_lines = [unique_points[0]]
    for point in unique_points[1:]:
        if point - filtered_lines[-1] > min_gap:
            filtered_lines.append(point)
    
    return filtered_lines

def detect_table_boundary(image_bgr):
    """检测整个表格的边界"""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    
    # 找到最大轮廓作为表格边界
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise Exception("未找到表格轮廓")
    
    table_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(table_contour)
    
    # 提取表格区域
    table_roi = binary[y:y+h, x:x+w]
    
    return table_roi, (x, y, w, h)

def crop_table_region(image_bgr, crop_config):
    """
    检测表格并根据配置裁剪指定区域
    输入: BGR格式图像, 裁剪配置
    输出: 裁剪后的BGR格式图像
    """
    try:
        # 检测表格边界
        table_roi, table_bbox = detect_table_boundary(image_bgr)
        table_x, table_y, table_w, table_h = table_bbox
        
        # 检测线条
        horizontal_lines, vertical_lines = detect_lines_improved(table_roi)
        
        # 获取线条坐标
        h_coords = get_line_coordinates_improved(horizontal_lines, is_horizontal=True)
        v_coords = get_line_coordinates_improved(vertical_lines, is_horizontal=False)
        
        # 检查线条数量
        h_start = crop_config['h_start']
        h_end = crop_config['h_end']
        v_start = crop_config['v_start']
        v_end = crop_config['v_end']
        
        if len(h_coords) <= max(h_start, h_end if h_end != -1 else 0):
            raise Exception(f"水平线数量不足 ({len(h_coords)} 条)")
        
        if len(v_coords) <= max(v_start, v_end):
            raise Exception(f"垂直线数量不足 ({len(v_coords)} 条)")
        
        # 确定裁剪边界（相对于表格区域的坐标）
        top_rel = h_coords[h_start]
        bottom_rel = h_coords[h_end] if h_end != -1 else h_coords[-1]
        left_rel = v_coords[v_start]
        right_rel = v_coords[v_end]
        
        # 转换为图像绝对坐标，添加边界
        top_abs = table_y + top_rel
        bottom_abs = table_y + bottom_rel + 15  # 下边多留15像素
        left_abs = table_x + left_rel - 5      # 左边多留5像素
        right_abs = table_x + right_rel
        
        # 边界检查，确保不超出图像范围
        img_height, img_width = image_bgr.shape[:2]
        left_abs = max(0, left_abs)
        top_abs = max(0, top_abs)
        right_abs = min(img_width, right_abs)
        bottom_abs = min(img_height, bottom_abs)
        
        # 裁剪图像
        cropped_image = image_bgr[top_abs:bottom_abs, left_abs:right_abs]
        
        return cropped_image
        
    except Exception as e:
        raise Exception(f"表格裁剪失败: {str(e)}")

# ==================== 集成处理函数 ====================

def process_single_image(args):
    """
    处理单个图像的函数（用于多进程）
    完整流程: 加载图像 → LUT处理 → 表格裁剪 → 保存结果
    """
    image_path, lut_path, output_dir, crop_config = args
    
    try:
        # 重新导入必要的库（多进程需要）
        import colour
        import cv2
        import numpy as np
        from pathlib import Path
        
        # 加载图像
        image = cv2.imread(image_path)
        if image is None:
            return f"失败: 无法读取图像 {Path(image_path).name}"
        
        # 步骤1: 应用LUT处理
        lut_processed_image = apply_lut_processing(image, lut_path)
        
        # 步骤2: 表格裁剪
        final_image = crop_table_region(lut_processed_image, crop_config)
        
        # 保存最终结果
        base_name = Path(image_path).stem
        final_output = os.path.join(output_dir, f"{base_name}_processed.jpg")
        cv2.imwrite(final_output, final_image)
        
        return f"成功: {Path(image_path).name}"
        
    except Exception as e:
        return f"失败: {Path(image_path).name} - {str(e)}"

def batch_process_images(input_folder, lut_path, crop_config):
    """批量处理图像文件夹"""
    input_folder = Path(input_folder)
    
    # 创建输出文件夹
    output_folder = input_folder.parent / f"{input_folder.name}_processed"
    output_folder.mkdir(exist_ok=True)
    
    print(f"输入文件夹: {input_folder}")
    print(f"输出文件夹: {output_folder}")
    
    # 扫描图像文件
    image_files = scan_image_files(input_folder)
    
    if not image_files:
        print("没有找到支持的图像文件")
        return
    
    print(f"发现 {len(image_files)} 个图像文件")
    
    # 确定并行数
    max_workers = get_optimal_workers()
    
    # 准备处理参数
    process_args = [(img_path, lut_path, str(output_folder), crop_config) 
                   for img_path in image_files]
    
    print(f"开始批量处理，使用 {max_workers} 个并行进程...")
    print("="*50)
    
    # 多进程处理
    successful = 0
    failed = 0
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_file = {executor.submit(process_single_image, args): args[0] 
                         for args in process_args}
        
        # 收集结果
        for future in as_completed(future_to_file):
            result = future.result()
            print(result)
            
            if result.startswith("成功"):
                successful += 1
            else:
                failed += 1
    
    # 处理完成报告
    print("="*50)
    print(f"批量处理完成!")
    print(f"成功处理: {successful} 个文件")
    print(f"处理失败: {failed} 个文件")
    print(f"输出目录: {output_folder}")

def process_single_file(image_path, lut_path, crop_config):
    """处理单个文件"""
    print(f"正在处理图像: {image_path}")
    
    # 检查文件是否存在
    if not os.path.exists(image_path):
        print(f"错误：找不到图像文件 {image_path}")
        return
        
    if not os.path.exists(lut_path):
        print(f"错误：找不到LUT文件 {lut_path}")
        return
    
    try:
        # 加载图像
        image = cv2.imread(image_path)
        if image is None:
            print(f"错误：无法读取图像文件 {image_path}")
            return
        
        print("正在应用LUT处理...")
        # 步骤1: 应用LUT处理
        lut_processed_image = apply_lut_processing(image, lut_path)
        
        print("正在进行表格裁剪...")
        # 步骤2: 表格裁剪
        final_image = crop_table_region(lut_processed_image, crop_config)
        
        # 保存结果
        output_dir = os.path.dirname(image_path) or "."
        base_name = Path(image_path).stem
        final_output = os.path.join(output_dir, f"{base_name}_processed.jpg")
        
        cv2.imwrite(final_output, final_image)
        
        print(f"处理完成！")
        print(f"输出文件: {final_output}")
        
    except Exception as e:
        print(f"处理失败: {str(e)}")

def main():
    # 检查命令行参数
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', '-help', 'help']:
        print("集成图像处理脚本 - LUT处理 + 表格裁剪")
        print("使用方法:")
        print("  显示帮助: python image_process.py -h")
        print("  单文件: python image_process.py <输入图像路径>")
        print("  批量处理: python image_process.py --batch <输入文件夹路径>")
        print("\n示例:")
        print("  python image_process.py ./test_image.jpg")
        print("  python image_process.py --batch ./images_folder")
        print("\n功能说明:")
        print("  - 支持格式: jpg, jpeg, png, tiff, tif, bmp, webp")
        print("  - 处理流程: LUT色彩处理 → 表格检测裁剪")
        print("  - 批量处理会自动创建输出文件夹")
        print("  - 自动检测系统资源并优化并行处理")
        return
    
    # 检查是否为批量处理模式
    if sys.argv[1] == "--batch":
        if len(sys.argv) != 3:
            print("批量处理使用方法: python image_process.py --batch <输入文件夹路径>")
            return
        
        input_folder = sys.argv[2]
        batch_process_images(input_folder, LUT_PATH, CROP_CONFIG)
        
    else:
        # 单文件处理模式
        image_path = sys.argv[1]
        process_single_file(image_path, LUT_PATH, CROP_CONFIG)

if __name__ == "__main__":
    main() 