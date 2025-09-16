#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF转PNG图像工具
支持命令行参数传入PDF文件路径
"""

import os
import sys
import argparse
from pathlib import Path

# 初始化引擎标志
USE_PYMUPDF = False
USE_PDF2IMAGE = False

try:
    import fitz  # PyMuPDF
    print("✅ 使用 PyMuPDF 引擎")
    USE_PYMUPDF = True
except ImportError:
    pass

try:
    from pdf2image import convert_from_path
    print("✅ 使用 pdf2image 引擎")
    USE_PDF2IMAGE = True
except ImportError:
    pass


class PDFConverter:
    """PDF转换器类"""
    
    def __init__(self):
        """初始化PDF转换器"""
        self.use_pymupdf = USE_PYMUPDF
        self.use_pdf2image = USE_PDF2IMAGE
    
    def pdf_to_png_pymupdf(self, pdf_path, output_dir=None, dpi=300, page_range=None):
        """
        使用PyMuPDF将PDF转换为PNG
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录，默认为PDF文件同目录
            dpi: 输出图像DPI，默认300
            page_range: 页面范围，格式为(start, end)，默认转换所有页面
        """
        try:
            # 打开PDF文件
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            
            print(f"📄 PDF文件: {pdf_path}")
            print(f"📊 总页数: {total_pages}")
            print(f"🎯 DPI设置: {dpi}")
            
            # 设置输出目录
            if output_dir is None:
                output_dir = os.path.dirname(pdf_path) or '.'
            os.makedirs(output_dir, exist_ok=True)
            
            # 确定页面范围
            if page_range:
                start_page, end_page = page_range
                start_page = max(0, start_page - 1)  # 转换为0索引
                end_page = min(total_pages, end_page)
            else:
                start_page, end_page = 0, total_pages
            
            print(f"📖 转换页面范围: {start_page + 1} - {end_page}")
            
            # 计算缩放因子
            zoom = dpi / 72.0  # PDF默认72 DPI
            mat = fitz.Matrix(zoom, zoom)
            
            # 获取PDF基本文件名
            pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
            
            converted_files = []
            
            # 逐页转换
            for page_num in range(start_page, end_page):
                page = pdf_document.load_page(page_num)
                
                # 渲染页面为图像
                pix = page.get_pixmap(matrix=mat)
                
                # 生成输出文件名
                if total_pages == 1:
                    output_filename = f"{pdf_basename}.png"
                else:
                    output_filename = f"{pdf_basename}_page_{page_num + 1:03d}.png"
                
                output_path = os.path.join(output_dir, output_filename)
                
                # 保存PNG图像
                pix.save(output_path)
                converted_files.append(output_path)
                
                print(f"✅ 页面 {page_num + 1}/{total_pages} -> {output_path}")
            
            pdf_document.close()
            
            print(f"\n🎉 转换完成！共转换 {len(converted_files)} 个页面")
            print(f"📁 输出目录: {output_dir}")
            
            return converted_files
            
        except Exception as e:
            print(f"❌ PyMuPDF转换失败: {str(e)}")
            return None

    def pdf_to_png_pdf2image(self, pdf_path, output_dir=None, dpi=300, page_range=None):
        """
        使用pdf2image将PDF转换为PNG
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录，默认为PDF文件同目录
            dpi: 输出图像DPI，默认300
            page_range: 页面范围，格式为(start, end)，默认转换所有页面
        """
        try:
            print(f"📄 PDF文件: {pdf_path}")
            print(f"🎯 DPI设置: {dpi}")
            
            # 设置输出目录
            if output_dir is None:
                output_dir = os.path.dirname(pdf_path) or '.'
            os.makedirs(output_dir, exist_ok=True)
            
            # 转换参数
            convert_kwargs = {
                'dpi': dpi,
                'fmt': 'PNG'
            }
            
            # 设置页面范围
            if page_range:
                convert_kwargs['first_page'] = page_range[0]
                convert_kwargs['last_page'] = page_range[1]
                print(f"📖 转换页面范围: {page_range[0]} - {page_range[1]}")
            
            # 转换PDF为图像列表
            images = convert_from_path(pdf_path, **convert_kwargs)
            
            print(f"📊 总页数: {len(images)}")
            
            # 获取PDF基本文件名
            pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
            
            converted_files = []
            
            # 保存每一页
            for i, image in enumerate(images):
                if len(images) == 1:
                    output_filename = f"{pdf_basename}.png"
                else:
                    page_num = page_range[0] + i if page_range else i + 1
                    output_filename = f"{pdf_basename}_page_{page_num:03d}.png"
                
                output_path = os.path.join(output_dir, output_filename)
                image.save(output_path, 'PNG')
                converted_files.append(output_path)
                
                print(f"✅ 页面 {i + 1}/{len(images)} -> {output_path}")
            
            print(f"\n🎉 转换完成！共转换 {len(converted_files)} 个页面")
            print(f"📁 输出目录: {output_dir}")
            
            return converted_files
            
        except Exception as e:
            print(f"❌ pdf2image转换失败: {str(e)}")
            return None

    def convert(self, pdf_path, output_dir=None, dpi=300, page_range=None):
        """
        PDF转PNG主函数，自动选择可用的转换引擎
        """
        # 检查PDF文件是否存在
        if not os.path.exists(pdf_path):
            print(f"❌ PDF文件不存在: {pdf_path}")
            return None
        
        print("=" * 60)
        print("📄 PDF转PNG图像工具")
        print("=" * 60)
        
        # 优先使用PyMuPDF，因为它更快且依赖更少
        if self.use_pymupdf:
            return self.pdf_to_png_pymupdf(pdf_path, output_dir, dpi, page_range)
        elif self.use_pdf2image:
            return self.pdf_to_png_pdf2image(pdf_path, output_dir, dpi, page_range)
        else:
            print("❌ 未找到可用的PDF转换库！")
            print("请安装以下库之一：")
            print("  1. PyMuPDF: pip install PyMuPDF")
            print("  2. pdf2image: pip install pdf2image")
            print("     (pdf2image还需要安装poppler)")
            return None

    def parse_page_range(self, page_range_str):
        """
        解析页面范围字符串
        支持格式: "1", "1-5", "3-"
        """
        if not page_range_str:
            return None
        
        if '-' in page_range_str:
            parts = page_range_str.split('-')
            if len(parts) == 2:
                start = int(parts[0]) if parts[0] else 1
                end = int(parts[1]) if parts[1] else None
                return (start, end)
        else:
            page = int(page_range_str)
            return (page, page)
        
        return None


# ==================== 向后兼容的函数接口 ====================

def pdf_to_png_pymupdf(pdf_path, output_dir=None, dpi=300, page_range=None):
    """向后兼容的函数接口"""
    converter = PDFConverter()
    return converter.pdf_to_png_pymupdf(pdf_path, output_dir, dpi, page_range)

def pdf_to_png_pdf2image(pdf_path, output_dir=None, dpi=300, page_range=None):
    """向后兼容的函数接口"""
    converter = PDFConverter()
    return converter.pdf_to_png_pdf2image(pdf_path, output_dir, dpi, page_range)

def pdf_to_png(pdf_path, output_dir=None, dpi=300, page_range=None):
    """向后兼容的函数接口"""
    converter = PDFConverter()
    return converter.convert(pdf_path, output_dir, dpi, page_range)

def parse_page_range(page_range_str):
    """向后兼容的函数接口"""
    converter = PDFConverter()
    return converter.parse_page_range(page_range_str)


def main():
    parser = argparse.ArgumentParser(
        description='PDF转PNG图像工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  python pdf_to_png.py document.pdf
  python pdf_to_png.py document.pdf -o output_folder/
  python pdf_to_png.py document.pdf --dpi 600
  python pdf_to_png.py document.pdf --pages 1-5
  python pdf_to_png.py document.pdf --pages 3

页面范围格式:
  1      - 只转换第1页
  1-5    - 转换第1到5页
  3-     - 从第3页转换到最后
  
支持的PDF转换库:
  1. PyMuPDF (推荐) - pip install PyMuPDF
  2. pdf2image - pip install pdf2image (需要poppler)
        '''
    )
    
    parser.add_argument('pdf_path', 
                       help='输入PDF文件路径')
    
    parser.add_argument('-o', '--output', 
                       help='输出目录路径（可选，默认为PDF文件同目录）')
    
    parser.add_argument('--dpi', 
                       type=int, 
                       default=300,
                       help='输出图像DPI（默认300）')
    
    parser.add_argument('--pages', 
                       help='页面范围，如: 1-5, 3, 3- （可选，默认转换所有页面）')
    
    args = parser.parse_args()
    
    converter = PDFConverter()
    
    # 解析页面范围
    page_range = None
    if args.pages:
        try:
            page_range = converter.parse_page_range(args.pages)
        except ValueError:
            print(f"❌ 页面范围格式错误: {args.pages}")
            sys.exit(1)
    
    # 执行转换
    result = converter.convert(
        pdf_path=args.pdf_path,
        output_dir=args.output,
        dpi=args.dpi,
        page_range=page_range
    )
    
    if result:
        print(f"\n✅ 成功转换 {len(result)} 个文件！")
    else:
        print("\n❌ 转换失败！")
        sys.exit(1)

if __name__ == "__main__":
    main() 