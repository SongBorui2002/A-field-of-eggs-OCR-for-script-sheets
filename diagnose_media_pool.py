#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DaVinci Resolve媒体池诊断脚本
用于检查媒体池状态、剪辑信息和SetMetadata方法的可用性
"""

import sys
import os

# 设置编码
if sys.version_info[0] == 3:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import DaVinciResolveScript as dvr_script
except ImportError:
    print("❌ 无法导入DaVinciResolveScript模块")
    print("请确保:")
    print("1. DaVinci Resolve正在运行")
    print("2. 已正确设置环境变量")
    print("3. 启用了外部脚本访问")
    sys.exit(1)


def diagnose_media_pool():
    """诊断媒体池状态"""
    
    print("🔍 DaVinci Resolve媒体池诊断")
    print("=" * 50)
    
    # 1. 连接到DaVinci Resolve
    print("\n1. 连接到DaVinci Resolve...")
    try:
        resolve = dvr_script.scriptapp("Resolve")
        if not resolve:
            print("❌ 无法连接到DaVinci Resolve")
            return False
        
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            print("❌ 没有打开的项目")
            return False
        
        media_pool = project.GetMediaPool()
        print(f"✓ 连接成功")
        print(f"✓ 项目名称: {project.GetName()}")
        
    except Exception as e:
        print(f"❌ 连接失败: {str(e)}")
        return False
    
    # 2. 检查媒体池结构
    print(f"\n2. 检查媒体池结构...")
    try:
        root_folder = media_pool.GetRootFolder()
        current_folder = media_pool.GetCurrentFolder()
        
        print(f"✓ 根文件夹: {root_folder.GetName()}")
        
        if current_folder is None:
            print("⚠️  当前文件夹为空，尝试设置为根文件夹...")
            media_pool.SetCurrentFolder(root_folder)
            current_folder = media_pool.GetCurrentFolder()
        
        if current_folder:
            print(f"✓ 当前文件夹: {current_folder.GetName()}")
            
            # 检查子文件夹
            subfolders = current_folder.GetSubFolderList()
            print(f"✓ 子文件夹数量: {len(subfolders)}")
            if subfolders:
                for i, folder in enumerate(subfolders[:3]):
                    print(f"  - 子文件夹{i+1}: {folder.GetName()}")
        else:
            print("❌ 无法获取当前文件夹")
            current_folder = root_folder  # 使用根文件夹作为备选
            print(f"✓ 使用根文件夹作为当前文件夹")
        
    except Exception as e:
        print(f"❌ 检查媒体池结构失败: {str(e)}")
        return False
    
    # 3. 检查剪辑
    print(f"\n3. 检查当前文件夹中的剪辑...")
    try:
        clips = current_folder.GetClipList()
        print(f"✓ 当前文件夹剪辑数量: {len(clips)}")
        
        if len(clips) == 0:
            print("⚠️  当前文件夹中没有剪辑!")
            print("📋 建议操作:")
            print("   1. 在DaVinci Resolve中导入一些媒体文件到媒体池")
            print("   2. 或者检查其他子文件夹是否有剪辑")
            
            # 检查所有子文件夹
            print("\n🔍 检查所有子文件夹...")
            all_clips_found = False
            
            def check_folder_recursive(folder, level=0):
                indent = "  " * level
                folder_clips = folder.GetClipList()
                subfolders = folder.GetSubFolderList()
                
                print(f"{indent}📁 {folder.GetName()}: {len(folder_clips)} 个剪辑")
                
                if folder_clips:
                    for i, clip in enumerate(folder_clips[:2]):  # 只显示前2个
                        print(f"{indent}  - 剪辑{i+1}: {clip.GetName()}")
                    if len(folder_clips) > 2:
                        print(f"{indent}  ... 还有 {len(folder_clips) - 2} 个剪辑")
                    return True
                
                # 递归检查子文件夹
                found_in_subfolders = False
                for subfolder in subfolders:
                    if check_folder_recursive(subfolder, level + 1):
                        found_in_subfolders = True
                
                return found_in_subfolders
            
            all_clips_found = check_folder_recursive(root_folder)
            
            if not all_clips_found:
                print("❌ 整个媒体池中都没有找到剪辑!")
                print("📋 请先在DaVinci Resolve中导入媒体文件")
                return False
        
        else:
            print(f"✓ 找到 {len(clips)} 个剪辑")
            
            # 4. 测试前几个剪辑的属性和SetMetadata方法
            print(f"\n4. 测试剪辑属性和SetMetadata方法...")
            
            for i, clip in enumerate(clips[:3]):  # 只测试前3个
                print(f"\n📹 剪辑 {i+1}: {clip.GetName()}")
                
                # 获取基本属性
                try:
                    reel_name = clip.GetProperty('Reel Name') or 'N/A'
                    file_path = clip.GetProperty('File Path') or 'N/A'
                    duration = clip.GetProperty('Duration') or 'N/A'
                    
                    print(f"  ✓ Reel Name: {reel_name}")
                    print(f"  ✓ 文件路径: {file_path}")
                    print(f"  ✓ 时长: {duration}")
                    
                except Exception as e:
                    print(f"  ❌ 获取属性失败: {str(e)}")
                
                # 获取当前元数据
                try:
                    current_scene = clip.GetMetadata('Scene') or '空'
                    current_shot = clip.GetMetadata('Shot') or '空'
                    current_take = clip.GetMetadata('Take') or '空'
                    
                    print(f"  ✓ 当前Scene: {current_scene}")
                    print(f"  ✓ 当前Shot: {current_shot}")
                    print(f"  ✓ 当前Take: {current_take}")
                    
                except Exception as e:
                    print(f"  ❌ 获取元数据失败: {str(e)}")
                
                # 测试SetMetadata方法
                try:
                    test_value = f"测试场景_{i+1}"
                    success = clip.SetMetadata('Scene', test_value)
                    
                    if success:
                        print(f"  ✅ SetMetadata测试成功: Scene = {test_value}")
                        
                        # 验证设置是否生效
                        verify_value = clip.GetMetadata('Scene')
                        if verify_value == test_value:
                            print(f"  ✅ 验证成功: 元数据已更新")
                        else:
                            print(f"  ⚠️  验证异常: 期望={test_value}, 实际={verify_value}")
                    else:
                        print(f"  ❌ SetMetadata测试失败")
                        
                except Exception as e:
                    print(f"  ❌ SetMetadata测试异常: {str(e)}")
    
    except Exception as e:
        print(f"❌ 检查剪辑失败: {str(e)}")
        return False
    
    # 5. 媒体存储检查
    print(f"\n5. 检查媒体存储...")
    try:
        media_storage = resolve.GetMediaStorage()
        mounted_volumes = media_storage.GetMountedVolumeList()
        
        print(f"✓ 挂载的卷数量: {len(mounted_volumes)}")
        for i, volume in enumerate(mounted_volumes[:3]):
            print(f"  - 卷{i+1}: {volume}")
        
    except Exception as e:
        print(f"❌ 检查媒体存储失败: {str(e)}")
    
    # 6. 总结和建议
    print(f"\n6. 诊断总结:")
    print("=" * 30)
    
    if len(clips) > 0:
        print("✅ 媒体池状态正常")
        print("✅ SetMetadata方法可用")
        print("📋 您可以正常使用元数据导入脚本")
    else:
        print("❌ 媒体池为空")
        print("📋 解决步骤:")
        print("   1. 在DaVinci Resolve中打开Media页面")
        print("   2. 从Media Storage拖拽视频文件到Media Pool")
        print("   3. 或使用 File > Import Media 导入媒体文件")
        print("   4. 确保媒体文件成功导入后再运行元数据导入脚本")
    
    return len(clips) > 0


def main():
    """主函数"""
    try:
        success = diagnose_media_pool()
        
        if success:
            print("\n🎉 诊断完成 - 系统状态正常!")
        else:
            print("\n⚠️  诊断完成 - 发现问题需要解决")
            
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 