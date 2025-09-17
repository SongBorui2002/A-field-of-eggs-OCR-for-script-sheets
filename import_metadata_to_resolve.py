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

# 设置编码
if sys.version_info[0] == 3:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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
    
    def read_csv_metadata(self, csv_file_path):
        """读取CSV文件中的元数据"""
        try:
            if not os.path.exists(csv_file_path):
                raise Exception(f"CSV文件不存在: {csv_file_path}")
            
            # 使用pandas读取CSV
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            
            print(f"✓ 成功读取CSV文件: {csv_file_path}")
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
    
    def import_metadata_from_csv(self, csv_file_path):
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
                        'take': row.get('Take', '')
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
                print(f"  #{record['index']}: {record['match_key']} (Scene:{record['scene']}, Shot:{record['shot']}, Take:{record['take']})")
            if len(unmatched_records) > 5:
                print(f"  ... 还有 {len(unmatched_records) - 5} 条未匹配记录")
        
        return updated_count > 0
    
    def test_clip_properties(self):
        """测试剪辑属性 - 用于调试"""
        print("\n当前媒体池中的剪辑信息:")
        print("-" * 50)
        
        for i, clip in enumerate(self.clips[:5]):  # 只显示前5个
            print(f"\n剪辑 {i+1}:")
            try:
                print(f"  名称: {clip.GetName()}")
                
                # 安全地获取属性
                reel_name = clip.GetProperty('Reel Name') if clip.GetProperty else 'N/A'
                file_path = clip.GetProperty('File Path') if clip.GetProperty else 'N/A'
                
                print(f"  Reel Name: {reel_name}")
                print(f"  文件路径: {file_path}")
                
                # 显示当前元数据
                current_scene = clip.GetMetadata('Scene') if clip.GetMetadata else 'N/A'
                current_shot = clip.GetMetadata('Shot') if clip.GetMetadata else 'N/A'
                current_take = clip.GetMetadata('Take') if clip.GetMetadata else 'N/A'
                
                print(f"  当前Scene: {current_scene}")
                print(f"  当前Shot: {current_shot}")
                print(f"  当前Take: {current_take}")
                
            except Exception as e:
                print(f"  ❌ 获取剪辑信息失败: {str(e)}")
                continue
        
        if len(self.clips) > 5:
            print(f"\n... 还有 {len(self.clips) - 5} 个剪辑")


def main():
    """主函数 - 测试功能"""
    
    print("DaVinci Resolve元数据导入工具")
    print("=" * 50)
    
    # 创建导入器实例
    importer = ResolveMetadataImporter()
    
    # 连接到DaVinci Resolve
    if not importer.connect_to_resolve():
        return
    
    # 测试剪辑属性（可选）
    print("\n是否查看当前剪辑信息？(y/n): ", end="")
    if input().lower() == 'y':
        importer.test_clip_properties()
    
    # 获取CSV文件路径
    print("\n请输入CSV文件路径: ", end="")
    csv_file_path = input().strip().strip('"\'')
    
    if not csv_file_path:
        print("❌ 未提供CSV文件路径")
        return
    
    # 执行导入（只使用文件名匹配）
    print("\n使用文件名匹配方式导入元数据...")
    success = importer.import_metadata_from_csv(csv_file_path)
    
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