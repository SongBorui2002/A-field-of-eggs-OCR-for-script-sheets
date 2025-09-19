#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DaVinci Resolve元数据导入脚本
将CSV文件中的Scene、Shot、Take信息批量导入到媒体池中的剪辑
"""

import sys
import os
import csv
import pandas as pd
from datetime import datetime

# 设置编码 - 仅在直接运行时设置，不在导入时设置
def setup_encoding():
    """设置标准输出编码"""
    if sys.version_info[0] == 3:
        import io
        try:
            if hasattr(sys.stdout, 'buffer') and not hasattr(sys.stdout, '_wrapped'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
                sys.stdout._wrapped = True
            if hasattr(sys.stderr, 'buffer') and not hasattr(sys.stderr, '_wrapped'):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)
                sys.stderr._wrapped = True
        except (AttributeError, ValueError):
            # 如果重新包装失败，保持原始流不变
            pass

try:
    import DaVinciResolveScript as dvr_script
except ImportError:
    print("错误: 无法导入DaVinciResolveScript模块")
    print("请确保:")
    print("1. DaVinci Resolve正在运行")
    print("2. 已正确设置环境变量")
    print("3. 启用了外部脚本访问")
    sys.exit(1)


class ResolveMetadataImporter:
    """DaVinci Resolve元数据导入器"""
    
    def __init__(self):
        self.resolve = None
        self.project = None
        self.media_pool = None
        self.clips = []
    
    def _clean_numeric_string(self, value):
        """
        清理数字字符串，去除不必要的小数点
        例如：233.0 -> "233", "ABC" -> "ABC", 123 -> "123"
        """
        try:
            # 先转为字符串并去除空白
            str_value = str(value).strip()
            
            # 尝试转换为浮点数
            float_value = float(str_value)
            
            # 如果是整数（没有小数部分），则返回整数字符串
            if float_value.is_integer():
                return str(int(float_value))
            else:
                # 有小数部分，保留原始格式
                return str_value
                
        except (ValueError, TypeError):
            # 如果无法转换为数字，返回原始字符串
            return str(value).strip()
        
    def get_all_clips_recursive(self, folder):
        """递归获取文件夹及其子文件夹中的所有剪辑"""
        clips = []
        
        # 获取当前文件夹中的剪辑
        folder_clips = folder.GetClipList()
        clips.extend(folder_clips)
        
        # 递归获取子文件夹中的剪辑
        subfolders = folder.GetSubFolderList()
        for subfolder in subfolders:
            clips.extend(self.get_all_clips_recursive(subfolder))
        
        return clips
    
    def connect_to_resolve(self):
        """连接到DaVinci Resolve"""
        try:
            self.resolve = dvr_script.scriptapp("Resolve")
            if not self.resolve:
                raise Exception("无法连接到DaVinci Resolve")
            
            self.project = self.resolve.GetProjectManager().GetCurrentProject()
            if not self.project:
                raise Exception("没有打开的项目")
            
            self.media_pool = self.project.GetMediaPool()
            root_folder = self.media_pool.GetRootFolder()
            
            # 递归获取所有文件夹中的剪辑
            self.clips = self.get_all_clips_recursive(root_folder)
            
            print(f"✓ 成功连接到DaVinci Resolve")
            print(f"✓ 当前项目: {self.project.GetName()}")
            print(f"✓ 在所有文件夹中找到 {len(self.clips)} 个剪辑")
            
            return True
            
        except Exception as e:
            print(f"❌ 连接DaVinci Resolve失败: {str(e)}")
            return False
    
    def detect_csv_encoding(self, csv_path: str) -> str:
        """检测CSV文件编码"""
        try:
            import chardet
        except ImportError:
            print("警告: 未安装chardet库，将尝试常见编码")
            return None
        
        try:
            with open(csv_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result.get('encoding', 'utf-8')
                confidence = result.get('confidence', 0)
                
                print(f"✓ 检测到编码: {encoding} (置信度: {confidence:.2f})")
                
            # 常见编码映射
            encoding_map = {
                'GB2312': 'gbk',
                'GBK': 'gbk', 
                'UTF-16': 'utf-16',
                'UTF-8': 'utf-8',
                'UTF-8-SIG': 'utf-8-sig'  # 带BOM的UTF-8
            }
            
            return encoding_map.get(encoding, encoding)
        except Exception as e:
            print(f"编码检测失败: {e}")
            return None
    
    def read_csv_metadata(self, csv_file_path):
        """读取CSV文件中的元数据"""
        try:
            if not os.path.exists(csv_file_path):
                raise Exception(f"CSV文件不存在: {csv_file_path}")
            
            # 首先尝试检测编码
            detected_encoding = self.detect_csv_encoding(csv_file_path)
            
            # 要尝试的编码列表
            encodings_to_try = []
            if detected_encoding:
                encodings_to_try.append(detected_encoding)
            
            # 添加常见编码作为备选
            common_encodings = ['utf-8-sig', 'utf-8', 'utf-16', 'gbk', 'cp1252', 'iso-8859-1']
            for enc in common_encodings:
                if enc not in encodings_to_try:
                    encodings_to_try.append(enc)
            
            # 逐个尝试编码
            df = None
            successful_encoding = None
            
            for encoding in encodings_to_try:
                try:
                    print(f"尝试使用编码: {encoding}")
                    df = pd.read_csv(csv_file_path, encoding=encoding)
                    successful_encoding = encoding
                    break
                except Exception as e:
                    print(f"编码 {encoding} 失败: {str(e)}")
                    continue
            
            if df is None:
                raise Exception("所有编码尝试都失败了")
            
            print(f"✓ 成功读取CSV文件: {csv_file_path}")
            print(f"✓ 使用编码: {successful_encoding}")
            print(f"✓ 找到 {len(df)} 条元数据记录")
            print(f"✓ 列名: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            print(f"❌ 读取CSV文件失败: {str(e)}")
            return None
    

    def match_clip_by_filename(self, filename_pattern):
        """根据文件名模式匹配剪辑"""
        for clip in self.clips:
            clip_name = clip.GetName() or ""
            
            if (filename_pattern in clip_name or 
                clip_name in filename_pattern or
                filename_pattern.replace('.', '') in clip_name):
                return clip
        return None
    
    def import_metadata(self, csv_file_path):
        """从CSV文件导入元数据到剪辑"""
        
        # 读取CSV数据
        df = self.read_csv_metadata(csv_file_path)
        if df is None:
            return False
        
        # 统计信息
        matched_count = 0
        updated_count = 0
        error_count = 0
        unmatched_records = []
        
        print(f"\n开始导入元数据...")
        print("-" * 50)
        
        # 遍历CSV中的每一行
        for index, row in df.iterrows():
            try:
                print(f"\n处理记录 {index + 1}/{len(df)}:")
                
                # 提取匹配键 - 只使用文件名匹配
                if 'File Name' in row and pd.notna(row['File Name']):
                    match_key = str(row['File Name']).strip()
                    matched_clip = self.match_clip_by_filename(match_key)
                else:
                    print(f"  ⚠ 跳过: 缺少File Name字段")
                    continue
                
                print(f"  匹配键: {match_key}")
                
                if matched_clip:
                    matched_count += 1
                    print(f"  ✓ 找到匹配剪辑: {matched_clip.GetName()}")
                    
                    # 更新元数据
                    metadata_updated = False
                    
                    # 设置Scene
                    if 'Scene' in row and pd.notna(row['Scene']) and str(row['Scene']).strip():
                        scene_value = self._clean_numeric_string(row['Scene'])
                        if matched_clip.SetMetadata('Scene', scene_value):
                            print(f"    ✓ Scene: {scene_value}")
                            metadata_updated = True
                        else:
                            print(f"    ❌ Scene设置失败: {scene_value}")
                    
                    # 设置Shot
                    if 'Shot' in row and pd.notna(row['Shot']) and str(row['Shot']).strip():
                        shot_value = self._clean_numeric_string(row['Shot'])
                        if matched_clip.SetMetadata('Shot', shot_value):
                            print(f"    ✓ Shot: {shot_value}")
                            metadata_updated = True
                        else:
                            print(f"    ❌ Shot设置失败: {shot_value}")
                    
                    # 设置Take
                    if 'Take' in row and pd.notna(row['Take']) and str(row['Take']).strip():
                        take_value = self._clean_numeric_string(row['Take'])
                        if matched_clip.SetMetadata('Take', take_value):
                            print(f"    ✓ Take: {take_value}")
                            metadata_updated = True
                        else:
                            print(f"    ❌ Take设置失败: {take_value}")
                    
                    # 设置Camera #
                    if 'Camera #' in row and pd.notna(row['Camera #']) and str(row['Camera #']).strip():
                        camera_value = str(row['Camera #']).strip()
                        if matched_clip.SetMetadata('Camera #', camera_value):
                            print(f"    ✓ Camera #: {camera_value}")
                            metadata_updated = True
                        else:
                            print(f"    ❌ Camera #设置失败: {camera_value}")
                    
                    if metadata_updated:
                        updated_count += 1
                        print(f"  ✓ 元数据更新成功")
                    else:
                        print(f"  ⚠ 没有有效的元数据可更新")
                        
                else:
                    print(f"  ❌ 未找到匹配的剪辑")
                    unmatched_records.append({
                        'index': index + 1,
                        'match_key': match_key,
                        'scene': row.get('Scene', ''),
                        'shot': row.get('Shot', ''),
                        'take': row.get('Take', ''),
                        'camera': row.get('Camera #', '')
                    })
                    
            except Exception as e:
                error_count += 1
                print(f"  ❌ 处理记录时出错: {str(e)}")
        
        # 输出结果统计
        print("\n" + "=" * 50)
        print("导入完成统计:")
        print(f"  总记录数: {len(df)}")
        print(f"  成功匹配: {matched_count}")
        print(f"  成功更新: {updated_count}")
        print(f"  处理错误: {error_count}")
        print(f"  未匹配数: {len(unmatched_records)}")
        
        # 显示未匹配的记录
        if unmatched_records:
            print(f"\n未匹配的记录:")
            for record in unmatched_records[:5]:  # 只显示前5个
                print(f"  #{record['index']}: {record['match_key']} (Scene:{record['scene']}, Shot:{record['shot']}, Take:{record['take']}, Camera #:{record['camera']})")
            if len(unmatched_records) > 5:
                print(f"  ... 还有 {len(unmatched_records) - 5} 条未匹配记录")
        
        return updated_count > 0
    
def main():
    """主函数"""
    
    # 只在直接运行时设置编码
    setup_encoding()
    
    print("DaVinci Resolve元数据导入工具")
    print("=" * 50)
    
    # 创建导入器实例
    importer = ResolveMetadataImporter()
    
    # 连接到DaVinci Resolve
    if not importer.connect_to_resolve():
        return
    
    # 获取CSV文件路径
    print("\n请输入CSV文件路径: ", end="")
    csv_file_path = input().strip().strip('"\'')
    
    if not csv_file_path:
        print("❌ 未提供CSV文件路径")
        return
    
    # 执行导入
    print("\n开始导入元数据...")
    success = importer.import_metadata(csv_file_path)
    
    if success:
        print("\n🎉 元数据导入完成！")
    else:
        print("\n❌ 元数据导入失败！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {str(e)}")
        import traceback
        traceback.print_exc() 