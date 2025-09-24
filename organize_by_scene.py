#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据Scene元数据自动组织视频剪辑到不同文件夹
只处理Video和Video+Audio类型的剪辑
跳过Scene为空的剪辑
"""

import DaVinciResolveScript as dvr_script
import sys

def organize_clips_by_scene():
    """根据Scene元数据组织剪辑"""
    
    # 连接到DaVinci Resolve
    try:
        resolve = dvr_script.scriptapp("Resolve")
        if not resolve:
            print("❌ 无法连接到DaVinci Resolve，请确保软件已启动")
            return False
            
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            print("❌ 没有打开的项目")
            return False
            
        media_pool = project.GetMediaPool()
        root_folder = media_pool.GetRootFolder()
        
        print(f"📁 开始处理项目: {project.GetName()}")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ 初始化错误: {str(e)}")
        return False
    
    # 统计变量
    processed_count = 0
    skipped_non_video = 0
    skipped_empty_scene = 0
    error_count = 0
    scene_folders = {}  # 存储已创建的Scene文件夹
    
    def process_folder(folder, level=0):
        """递归处理文件夹中的剪辑"""
        nonlocal processed_count, skipped_non_video, skipped_empty_scene, error_count
        
        indent = "  " * level
        print(f"{indent}📂 处理文件夹: {folder.GetName()}")
        
        # 获取当前文件夹中的所有剪辑
        clips = folder.GetClipList()
        
        for clip in clips:
            try:
                clip_name = clip.GetName()
                print(f"{indent}  🎬 检查剪辑: {clip_name}")
                
                # 检查剪辑类型
                clip_properties = clip.GetClipProperty()
                clip_type = clip_properties.get("Type", "Unknown")
                
                if clip_type not in ["Video", "Video+Audio"]:
                    print(f"{indent}    ⚠ 跳过非视频剪辑 (类型: {clip_type})")
                    skipped_non_video += 1
                    continue
                
                # 获取Scene元数据
                scene = clip.GetMetadata("Scene")
                if not scene or scene.strip() == "":
                    print(f"{indent}    ⚠ 跳过Scene为空的剪辑")
                    skipped_empty_scene += 1
                    continue
                
                scene = scene.strip()
                print(f"{indent}    📍 Scene: {scene}")
                
                # 检查是否已经创建了对应的Scene文件夹
                if scene not in scene_folders:
                    # 创建Scene文件夹（不带Scene_前缀）
                    scene_folder = media_pool.AddSubFolder(root_folder, scene)
                    if scene_folder:
                        scene_folders[scene] = scene_folder
                        print(f"{indent}    ✅ 创建文件夹: {scene}")
                    else:
                        print(f"{indent}    ❌ 创建文件夹失败: {scene}")
                        error_count += 1
                        continue
                else:
                    scene_folder = scene_folders[scene]
                
                # 移动剪辑到对应的Scene文件夹
                success = media_pool.MoveClips([clip], scene_folder)
                if success:
                    print(f"{indent}    ✅ 移动剪辑到: {scene}")
                    processed_count += 1
                else:
                    print(f"{indent}    ❌ 移动剪辑失败")
                    error_count += 1
                    
            except Exception as e:
                print(f"{indent}    ❌ 处理剪辑时出错: {str(e)}")
                error_count += 1
                continue
        
        # 递归处理子文件夹
        subfolders = folder.GetSubFolderList()
        for subfolder in subfolders:
            # 跳过我们刚创建的Scene文件夹，避免重复处理
            subfolder_name = subfolder.GetName()
            # 检查是否是我们刚创建的场景文件夹（在scene_folders中存在）
            if subfolder_name not in scene_folders:
                process_folder(subfolder, level + 1)
    
    try:
        # 开始处理
        process_folder(root_folder)
        
        # 输出结果统计
        print("\n" + "=" * 50)
        print("📊 处理完成统计:")
        print(f"  成功移动剪辑: {processed_count}")
        print(f"  跳过非视频剪辑: {skipped_non_video}")
        print(f"  跳过Scene为空: {skipped_empty_scene}")
        print(f"  处理错误: {error_count}")
        print(f"  创建Scene文件夹数: {len(scene_folders)}")
        
        if scene_folders:
            print(f"\n📁 创建的Scene文件夹:")
            for scene in sorted(scene_folders.keys()):
                print(f"  - {scene}")
        
        print("\n🎉 处理完成！")
        return True
        
    except Exception as e:
        print(f"❌ 处理过程中发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    print("🎬 DaVinci Resolve - 根据Scene组织剪辑")
    print("=" * 50)
    
    success = organize_clips_by_scene()
    
    if success:
        print("\n✅ 脚本执行成功")
        sys.exit(0)
    else:
        print("\n❌ 脚本执行失败")
        sys.exit(1) 