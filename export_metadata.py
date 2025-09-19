#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DaVinci Resolve元数据导出工具
面向对象的设计，支持自定义过滤器和配置
"""

import sys
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

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


class ExportConfig:
    """导出配置类"""
    
    def __init__(self):
        self.output_directory = os.path.expanduser("~/Desktop")
        self.filename_template = "metadata_export_{timestamp}.csv"
        self.include_subfolders = True
        self.verbose = True
    
    def get_output_path(self) -> str:
        """生成输出文件路径"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.filename_template.format(timestamp=timestamp)
        return os.path.join(self.output_directory, filename)
    
    def set_output_directory(self, directory: str) -> None:
        """设置输出目录"""
        self.output_directory = os.path.expanduser(directory)
    
    def set_filename_template(self, template: str) -> None:
        """设置文件名模板"""
        self.filename_template = template


class ClipFilter(ABC):
    """剪辑过滤器抽象基类"""
    
    @abstractmethod
    def should_include(self, clip) -> bool:
        """判断是否应该包含该剪辑"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取过滤器描述"""
        pass


class PathExcludeFilter(ClipFilter):
    """路径排除过滤器"""
    
    def __init__(self, exclude_keywords: List[str]):
        self.exclude_keywords = [keyword.lower() for keyword in exclude_keywords]
    
    def should_include(self, clip) -> bool:
        """检查剪辑是否应该被包含（不包含排除关键词）"""
        try:
            clip_properties = clip.GetClipProperty()
            file_path = clip_properties.get('File Path', '').lower()
            
            # 如果文件路径包含任何排除关键词，则排除
            for keyword in self.exclude_keywords:
                if keyword in file_path:
                    return False
            return True
            
        except Exception:
            # 如果无法获取属性，默认包含
            return True
    
    def get_description(self) -> str:
        return f"排除路径包含关键词的剪辑: {', '.join(self.exclude_keywords)}"


class NameExcludeFilter(ClipFilter):
    """名称排除过滤器"""
    
    def __init__(self, exclude_keywords: List[str]):
        self.exclude_keywords = [keyword.lower() for keyword in exclude_keywords]
    
    def should_include(self, clip) -> bool:
        """检查剪辑名称是否应该被包含"""
        try:
            clip_name = clip.GetName().lower()
            
            for keyword in self.exclude_keywords:
                if keyword in clip_name:
                    return False
            return True
            
        except Exception:
            return True
    
    def get_description(self) -> str:
        return f"排除名称包含关键词的剪辑: {', '.join(self.exclude_keywords)}"


class ClipFilterManager:
    """剪辑过滤器管理器"""
    
    def __init__(self):
        self.filters: List[ClipFilter] = []
    
    def add_filter(self, filter_obj: ClipFilter) -> None:
        """添加过滤器"""
        self.filters.append(filter_obj)
    
    def remove_all_filters(self) -> None:
        """移除所有过滤器"""
        self.filters.clear()
    
    def apply_filters(self, clips: List) -> tuple:
        """应用所有过滤器，返回(过滤后的剪辑列表, 排除的剪辑数量)"""
        if not self.filters:
            return clips, 0
        
        filtered_clips = []
        excluded_count = 0
        
        for clip in clips:
            should_include = True
            
            # 所有过滤器都必须通过
            for filter_obj in self.filters:
                if not filter_obj.should_include(clip):
                    should_include = False
                    break
            
            if should_include:
                filtered_clips.append(clip)
            else:
                excluded_count += 1
        
        return filtered_clips, excluded_count
    
    def get_filter_descriptions(self) -> List[str]:
        """获取所有过滤器的描述"""
        return [filter_obj.get_description() for filter_obj in self.filters]


class ResolveConnection:
    """DaVinci Resolve连接管理器"""
    
    def __init__(self):
        self.resolve = None
        self.project = None
        self.media_pool = None
        self._connected = False
    
    def connect(self) -> bool:
        """连接到DaVinci Resolve"""
        try:
            self.resolve = dvr_script.scriptapp("Resolve")
            if not self.resolve:
                raise Exception("无法连接到DaVinci Resolve")
            
            self.project = self.resolve.GetProjectManager().GetCurrentProject()
            if not self.project:
                raise Exception("没有打开的项目")
            
            self.media_pool = self.project.GetMediaPool()
            self._connected = True
            
            return True
            
        except Exception as e:
            print(f"❌ 连接DaVinci Resolve失败: {str(e)}")
            return False
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    def get_project_name(self) -> str:
        """获取当前项目名称"""
        if self.project:
            return self.project.GetName()
        return "未知项目"


class ClipCollector:
    """剪辑收集器"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def get_all_clips(self, include_subfolders: bool = True) -> List:
        """获取所有剪辑"""
        root_folder = self.media_pool.GetRootFolder()
        
        if include_subfolders:
            return self._get_clips_recursive(root_folder)
        else:
            return root_folder.GetClipList()
    
    def _get_clips_recursive(self, folder) -> List:
        """递归获取文件夹及其子文件夹中的所有剪辑"""
        clips = []
        
        # 获取当前文件夹中的剪辑
        folder_clips = folder.GetClipList()
        clips.extend(folder_clips)
        
        # 递归获取子文件夹中的剪辑
        subfolders = folder.GetSubFolderList()
        for subfolder in subfolders:
            clips.extend(self._get_clips_recursive(subfolder))
        
        return clips


class MetadataExporter:
    """元数据导出器主类"""
    
    def __init__(self, config: Optional[ExportConfig] = None):
        self.config = config or ExportConfig()
        self.connection = ResolveConnection()
        self.filter_manager = ClipFilterManager()
        self.clip_collector = None
        
        # 默认添加音频文件过滤器
        self.filter_manager.add_filter(PathExcludeFilter(['audio', 'sound']))
    
    def connect_to_resolve(self) -> bool:
        """连接到DaVinci Resolve"""
        success = self.connection.connect()
        if success:
            self.clip_collector = ClipCollector(self.connection.media_pool)
            
            if self.config.verbose:
                print(f"✓ 成功连接到DaVinci Resolve")
                print(f"✓ 当前项目: {self.connection.get_project_name()}")
        
        return success
    
    def add_filter(self, filter_obj: ClipFilter) -> None:
        """添加过滤器"""
        self.filter_manager.add_filter(filter_obj)
    
    def remove_all_filters(self) -> None:
        """移除所有过滤器"""
        self.filter_manager.remove_all_filters()
    
    def export_metadata(self, output_file: Optional[str] = None) -> bool:
        """导出元数据"""
        if not self.connection.is_connected():
            print("❌ 未连接到DaVinci Resolve")
            return False
        
        try:
            # 收集所有剪辑
            all_clips = self.clip_collector.get_all_clips(self.config.include_subfolders)
            
            if not all_clips:
                print("❌ 没有找到任何剪辑")
                return False
            
            # 应用过滤器
            filtered_clips, excluded_count = self.filter_manager.apply_filters(all_clips)
            
            # 显示统计信息
            if self.config.verbose:
                print(f"✓ 原始剪辑数量: {len(all_clips)}")
                print(f"✓ 过滤后剪辑数量: {len(filtered_clips)}")
                print(f"✓ 排除的剪辑数量: {excluded_count}")
                
                # 显示过滤器信息
                filter_descriptions = self.filter_manager.get_filter_descriptions()
                if filter_descriptions:
                    print("\n应用的过滤器:")
                    for desc in filter_descriptions:
                        print(f"  - {desc}")
            
            if not filtered_clips:
                print("❌ 过滤后没有剩余剪辑")
                return False
            
            # 确定输出文件路径
            if not output_file:
                output_file = self.config.get_output_path()
            
            if not os.path.isabs(output_file):
                output_file = os.path.abspath(output_file)
            
            if self.config.verbose:
                print(f"\n开始导出元数据...")
                print(f"目标路径: {output_file}")
                print("-" * 50)
            
            # 执行导出
            result = self.connection.media_pool.ExportMetadata(output_file, filtered_clips)
            
            if result:
                if self.config.verbose:
                    print(f"✓ 元数据导出成功！")
                    print(f"✓ 导出了 {len(filtered_clips)} 个剪辑的元数据")
                
                # 检查文件是否存在
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    if self.config.verbose:
                        print(f"✓ 文件已保存: {output_file}")
                        print(f"✓ 文件大小: {file_size} 字节")
                else:
                    if self.config.verbose:
                        print(f"⚠ 文件可能保存在其他位置")
                        # 检查DaVinci Resolve默认位置
                        filename = os.path.basename(output_file)
                        resolve_path = f"/System/Volumes/Data/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Resources/{filename}"
                        if os.path.exists(resolve_path):
                            print(f"✓ 找到文件: {resolve_path}")
                
                return True
            else:
                print(f"❌ 元数据导出失败")
                return False
                
        except Exception as e:
            print(f"❌ 导出元数据时出错: {str(e)}")
            return False


def main():
    """主函数"""
    
    # 只在直接运行时设置编码
    setup_encoding()
    
    print("DaVinci Resolve元数据导出工具")
    print("=" * 50)
    
    # 创建配置
    config = ExportConfig()
    config.verbose = True
    
    # 创建导出器
    exporter = MetadataExporter(config)
    
    # 连接到DaVinci Resolve
    if not exporter.connect_to_resolve():
        return
    
    # 执行导出
    success = exporter.export_metadata()
    
    if success:
        print("\n🎉 元数据导出完成！")
    else:
        print("\n❌ 元数据导出失败！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {str(e)}") 