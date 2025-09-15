#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
colour-science 3D LUT处理测试脚本
使用方法: 
  单文件: python test_colour_science_lut.py <输入图像路径>
  批量处理: python test_colour_science_lut.py --batch <输入文件夹路径>
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

try:
    import colour
    print(f"colour-science 版本: {colour.__version__}")
except ImportError:
    print("错误：未安装colour-science库")
    print("请运行: pip install colour-science")
    sys.exit(1)

# 支持的图像格式
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}

def get_optimal_workers():
    """
    根据系统资源自动确定最佳并行数
    """
    cpu_count = multiprocessing.cpu_count()
    available_memory = psutil.virtual_memory().available
    
    # 预估每张图片需要的内存（保守估计200MB）
    memory_per_image = 200 * 1024 * 1024  # 200MB
    
    # 基于CPU和内存计算最大并行数
    cpu_workers = max(1, cpu_count - 1)  # 保留1个CPU核心
    memory_workers = max(1, available_memory // memory_per_image)
    
    optimal_workers = min(cpu_workers, memory_workers, 8)  # 最多8个进程
    
    print(f"系统资源分析:")
    print(f"  CPU核心数: {cpu_count}")
    print(f"  可用内存: {available_memory / (1024**3):.1f}GB")
    print(f"  推荐并行数: {optimal_workers}")
    
    return optimal_workers

def scan_image_files(folder_path):
    """
    扫描文件夹中的所有图像文件
    """
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
    
    print(f"发现 {len(image_files)} 个图像文件")
    if len(image_files) > 0:
        print(f"示例文件: {Path(image_files[0]).name}")
    
    return image_files

def process_single_image(args):
    """
    处理单个图像的函数（用于多进程）
    """
    image_path, lut_path, output_dir = args
    
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
        
        # 转换为RGB并标准化
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
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
        
        # 保存结果
        base_name = Path(image_path).stem
        
        # 转换回uint8格式
        original_uint8 = (image_normalized * 255).astype(np.uint8)
        processed_uint8 = (processed_image * 255).astype(np.uint8)
        
        # 转换回BGR用于保存
        original_bgr = cv2.cvtColor(original_uint8, cv2.COLOR_RGB2BGR)
        processed_bgr = cv2.cvtColor(processed_uint8, cv2.COLOR_RGB2BGR)
        
        # 保存文件
        original_output = os.path.join(output_dir, f"{base_name}_original.jpg")
        processed_output = os.path.join(output_dir, f"{base_name}_lut_applied.jpg")
        comparison_output = os.path.join(output_dir, f"{base_name}_comparison.jpg")
        
        cv2.imwrite(original_output, original_bgr)
        cv2.imwrite(processed_output, processed_bgr)
        
        # 创建对比图
        comparison = np.hstack([original_bgr, processed_bgr])
        cv2.imwrite(comparison_output, comparison)
        
        return f"成功: {Path(image_path).name}"
        
    except Exception as e:
        return f"失败: {Path(image_path).name} - {str(e)}"

def batch_process_images(input_folder, lut_path):
    """
    批量处理图像文件夹
    """
    input_folder = Path(input_folder)
    
    # 创建输出文件夹
    output_folder = input_folder.parent / f"{input_folder.name}_lut_processed"
    output_folder.mkdir(exist_ok=True)
    
    print(f"输入文件夹: {input_folder}")
    print(f"输出文件夹: {output_folder}")
    
    # 扫描图像文件
    image_files = scan_image_files(input_folder)
    
    if not image_files:
        print("没有找到支持的图像文件")
        return
    
    # 确定并行数
    max_workers = get_optimal_workers()
    
    # 准备处理参数
    process_args = [(img_path, lut_path, str(output_folder)) for img_path in image_files]
    
    print(f"\n开始批量处理 {len(image_files)} 个文件...")
    print(f"使用 {max_workers} 个并行进程")
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

def load_and_apply_lut(image_path, lut_path):
    """
    加载图像和3D LUT，并应用LUT处理
    """
    print(f"正在处理图像: {image_path}")
    print(f"使用LUT文件: {lut_path}")
    
    # 检查文件是否存在
    if not os.path.exists(image_path):
        print(f"错误：找不到图像文件 {image_path}")
        return None
        
    if not os.path.exists(lut_path):
        print(f"错误：找不到LUT文件 {lut_path}")
        return None
    
    # 读取图像
    print("正在读取图像...")
    image = cv2.imread(image_path)
    if image is None:
        print(f"错误：无法读取图像文件 {image_path}")
        return None
    
    # OpenCV读取的图像是BGR格式，需要转换为RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # 将图像数据标准化到[0,1]范围
    image_normalized = image_rgb.astype(np.float32) / 255.0
    
    print(f"图像尺寸: {image_rgb.shape}")
    print(f"图像数据类型: {image_normalized.dtype}")
    print(f"图像数值范围: [{image_normalized.min():.3f}, {image_normalized.max():.3f}]")
    
    # 读取3D LUT文件
    print("正在读取3D LUT文件...")
    try:
        lut_3d = colour.io.read_LUT(lut_path)
        print(f"LUT信息:")
        print(f"  - 名称: {lut_3d.name}")
        print(f"  - 尺寸: {lut_3d.size}")
        print(f"  - 维度: {lut_3d.dimensions}")
        print(f"  - 域: {lut_3d.domain}")
        print(f"  - 数据类型: {lut_3d.table.dtype}")
        print(f"  - 数据范围: [{lut_3d.table.min():.3f}, {lut_3d.table.max():.3f}]")
        
    except Exception as e:
        print(f"错误：无法读取LUT文件 - {e}")
        return None
    
    # 应用3D LUT到图像
    print("正在应用3D LUT...")
    try:
        # 直接使用LUT对象的apply方法
        processed_image = lut_3d.apply(image_normalized)
        
        # 确保数值在有效范围内
        processed_image = np.clip(processed_image, 0.0, 1.0)
        
        print("LUT应用成功!")
        print(f"处理后图像数值范围: [{processed_image.min():.3f}, {processed_image.max():.3f}]")
        
        return processed_image, image_normalized
        
    except Exception as e:
        print(f"错误：应用LUT时出现问题 - {e}")
        # 尝试备用方法
        try:
            print("尝试使用备用插值方法...")
            # 将图像重塑为二维数组以便处理
            height, width, channels = image_normalized.shape
            image_reshaped = image_normalized.reshape(-1, channels)
            
            # 使用更简单的插值方法
            from colour.algebra import table_interpolation_trilinear
            processed_reshaped = table_interpolation_trilinear(image_reshaped, lut_3d.table)
            
            # 重塑回原始形状
            processed_image = processed_reshaped.reshape(height, width, channels)
            
            # 确保数值在有效范围内
            processed_image = np.clip(processed_image, 0.0, 1.0)
            
            print("备用方法应用成功!")
            print(f"处理后图像数值范围: [{processed_image.min():.3f}, {processed_image.max():.3f}]")
            
            return processed_image, image_normalized
            
        except Exception as e2:
            print(f"备用方法也失败了: {e2}")
            return None

def save_results(original_image, processed_image, output_dir, base_name):
    """
    保存处理结果
    """
    # 转换回0-255范围并转为uint8
    original_uint8 = (original_image * 255).astype(np.uint8)
    processed_uint8 = (processed_image * 255).astype(np.uint8)
    
    # 转换回BGR格式用于OpenCV保存
    original_bgr = cv2.cvtColor(original_uint8, cv2.COLOR_RGB2BGR)
    processed_bgr = cv2.cvtColor(processed_uint8, cv2.COLOR_RGB2BGR)
    
    # 生成输出文件名
    original_output = os.path.join(output_dir, f"{base_name}_original.jpg")
    processed_output = os.path.join(output_dir, f"{base_name}_lut_applied.jpg")
    
    # 保存图像
    cv2.imwrite(original_output, original_bgr)
    cv2.imwrite(processed_output, processed_bgr)
    
    print(f"原始图像已保存到: {original_output}")
    print(f"LUT处理后图像已保存到: {processed_output}")
    
    # 创建对比图像（左右并排）
    comparison = np.hstack([original_bgr, processed_bgr])
    comparison_output = os.path.join(output_dir, f"{base_name}_comparison.jpg")
    cv2.imwrite(comparison_output, comparison)
    print(f"对比图像已保存到: {comparison_output}")

def analyze_lut_properties(lut_path):
    """
    分析LUT文件的详细属性
    """
    print("\n" + "="*50)
    print("LUT文件详细分析")
    print("="*50)
    
    try:
        lut_3d = colour.io.read_LUT(lut_path)
        
        print(f"LUT基本信息:")
        print(f"  文件路径: {lut_path}")
        print(f"  LUT名称: {lut_3d.name}")
        print(f"  LUT尺寸: {lut_3d.size} (每个轴的采样点数)")
        print(f"  总采样点数: {lut_3d.size**3}")
        print(f"  维度: {lut_3d.dimensions}")
        print(f"  输入域: {lut_3d.domain}")
        print(f"  表格形状: {lut_3d.table.shape}")
        print(f"  数据类型: {lut_3d.table.dtype}")
        
        # 分析数值分布
        table = lut_3d.table
        print(f"\n数值分布分析:")
        print(f"  R通道: min={table[..., 0].min():.4f}, max={table[..., 0].max():.4f}, mean={table[..., 0].mean():.4f}")
        print(f"  G通道: min={table[..., 1].min():.4f}, max={table[..., 1].max():.4f}, mean={table[..., 1].mean():.4f}")
        print(f"  B通道: min={table[..., 2].min():.4f}, max={table[..., 2].max():.4f}, mean={table[..., 2].mean():.4f}")
        
        # 检查是否为身份LUT（无变化）
        try:
            # 创建身份LUT进行比较
            identity_lut = colour.LUT3D.linear_table(lut_3d.size, domain=lut_3d.domain)
            difference = np.abs(table - identity_lut.table).max()
            print(f"\n与身份LUT的最大差异: {difference:.6f}")
            if difference < 1e-6:
                print("  -> 这是一个身份LUT（不会改变图像）")
            else:
                print("  -> 这个LUT会对图像产生变化")
                
            # 分析变化特征
            print(f"\nLUT变化特征:")
            contrast_factor = (table.max() - table.min()) / (identity_lut.table.max() - identity_lut.table.min())
            print(f"  对比度系数: {contrast_factor:.3f}")
            
            if contrast_factor > 1.1:
                print("  -> 增强对比度")
            elif contrast_factor < 0.9:
                print("  -> 降低对比度")
            else:
                print("  -> 对比度变化较小")
                
        except Exception as e:
            print(f"无法创建身份LUT进行比较: {e}")
            
        # 分析颜色偏移
        print(f"\n颜色通道分析:")
        r_mean, g_mean, b_mean = table[..., 0].mean(), table[..., 1].mean(), table[..., 2].mean()
        overall_mean = (r_mean + g_mean + b_mean) / 3
        
        print(f"  整体平均值: {overall_mean:.4f}")
        if r_mean > overall_mean * 1.05:
            print("  -> 偏向红色")
        elif g_mean > overall_mean * 1.05:
            print("  -> 偏向绿色")
        elif b_mean > overall_mean * 1.05:
            print("  -> 偏向蓝色")
        else:
            print("  -> 颜色平衡相对均匀")
            
    except Exception as e:
        print(f"分析LUT时出错: {e}")

def main():
    # 设置LUT文件路径
    lut_path = "/Users/sbr/Desktop/OCR.cube"
    
    # 检查命令行参数
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', '-help', 'help']:
        print("使用方法:")
        print("  显示帮助: python test_colour_science_lut.py -h")
        print("  仅分析LUT: python test_colour_science_lut.py")
        print("  单文件: python test_colour_science_lut.py <输入图像路径>")
        print("  批量处理: python test_colour_science_lut.py --batch <输入文件夹路径>")
        print("\n示例:")
        print("  python test_colour_science_lut.py ./test_image.jpg")
        print("  python test_colour_science_lut.py --batch ./images_folder")
        print("\n功能说明:")
        print("  - 支持格式: jpg, jpeg, png, tiff, tif, bmp, webp")
        print("  - 批量处理会自动创建同级输出文件夹")
        print("  - 自动检测系统资源并优化并行处理数量")
        
        # 如果是帮助参数，只显示帮助信息，不分析LUT
        if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', '-help', 'help']:
            return
        
        # 只分析LUT属性
        print("\n" + "="*50)
        print("LUT文件分析（无参数时默认显示）")
        print("="*50)
        analyze_lut_properties(lut_path)
        return
    
    # 检查是否为批量处理模式
    if sys.argv[1] == "--batch":
        if len(sys.argv) != 3:
            print("批量处理使用方法: python test_colour_science_lut.py --batch <输入文件夹路径>")
            return
        
        input_folder = sys.argv[2]
        
        # 先分析LUT属性
        analyze_lut_properties(lut_path)
        
        print("\n" + "="*50)
        print("批量图像处理")
        print("="*50)
        
        # 批量处理
        batch_process_images(input_folder, lut_path)
        
    else:
        # 单文件处理模式
        image_path = sys.argv[1]
        
        # 分析LUT属性
        analyze_lut_properties(lut_path)
        
        print("\n" + "="*50)
        print("单文件图像处理")
        print("="*50)
        
        # 处理图像
        result = load_and_apply_lut(image_path, lut_path)
        
        if result is not None:
            processed_image, original_image = result
            
            # 准备输出目录和文件名
            output_dir = os.path.dirname(image_path) or "."
            base_name = Path(image_path).stem
            
            # 保存结果
            save_results(original_image, processed_image, output_dir, base_name)
            
            print(f"\n处理完成！")
            print(f"所有输出文件已保存到: {output_dir}")
            
            # 显示统计信息
            print(f"\n处理统计:")
            print(f"  原始图像平均亮度: {original_image.mean():.3f}")
            print(f"  处理后平均亮度: {processed_image.mean():.3f}")
            print(f"  亮度变化: {((processed_image.mean() - original_image.mean()) / original_image.mean() * 100):+.1f}%")
            
        else:
            print("图像处理失败")

if __name__ == "__main__":
    main() 