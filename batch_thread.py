#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import json
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal
from config import AppConfig


class BatchProcessThread(QThread):
    """后台批量处理线程"""
    
    # 信号定义
    progress_updated = Signal(int, str)  # 进度百分比, 状态消息
    image_processed = Signal(int, dict)  # 图像索引, OCR结果
    process_finished = Signal(bool, str)  # 是否成功, 消息
    
    def __init__(self, image_paths, temp_dir, scene_numbers=None, deepseek_api_key=None):
        super().__init__()
        self.image_paths = image_paths
        self.temp_dir = temp_dir
        self.scene_numbers = scene_numbers
        
        # 如果没有提供API密钥，则从配置文件读取
        if deepseek_api_key is None:
            config = AppConfig()
            config_path = config.get_config_path()
            if os.path.exists(config_path):
                config = AppConfig.from_file(config_path)
            self.deepseek_api_key = config.deepseek_api_key
        else:
            self.deepseek_api_key = deepseek_api_key
        
        self.should_stop = False
        
    def run(self):
        """执行批量处理 - 先图像处理，再分批OCR"""
        try:
            total_images = len(self.image_paths)
            
            # 步骤0: 复制原始图像到临时目录
            self.progress_updated.emit(5, "准备图像文件...")
            if not self.prepare_images():
                self.process_finished.emit(False, "图像文件准备失败")
                return
            
            # 步骤1: 使用image_process.py批量处理图像
            self.progress_updated.emit(10, "正在进行图像预处理...")
            processed_dir = self.run_image_processing()
            
            if not processed_dir or self.should_stop:
                self.process_finished.emit(False, "图像预处理失败或被中断")
                return
            
            # 步骤2: 获取处理后的图像文件
            processed_images = self.get_processed_images(processed_dir)
            if not processed_images:
                self.process_finished.emit(False, "未找到处理后的图像文件")
                return
                
            self.progress_updated.emit(30, f"找到{len(processed_images)}个处理后的图像，开始OCR识别...")
            
            # 步骤3: 并发进行OCR处理
            self.progress_updated.emit(30, f"开始并发OCR处理 {len(processed_images)} 张图像...")
            successful_count = self.run_concurrent_ocr(processed_images)
            
            # 完成处理
            if not self.should_stop:
                self.progress_updated.emit(100, f"批量处理完成，成功处理{successful_count}/{len(processed_images)}张图像")
                self.process_finished.emit(True, f"批量处理完成，成功: {successful_count}, 失败: {len(processed_images) - successful_count}")
            else:
                self.process_finished.emit(False, "处理被用户中断")
                
        except Exception as e:
            self.process_finished.emit(False, f"处理过程中出错: {str(e)}")
    
    def prepare_images(self):
        """复制原始图像到临时目录"""
        try:
            original_images_dir = os.path.join(self.temp_dir, "original_images")
            os.makedirs(original_images_dir, exist_ok=True)
            
            for i, image_path in enumerate(self.image_paths):
                if self.should_stop:
                    return False
                    
                filename = os.path.basename(image_path)
                dest_path = os.path.join(original_images_dir, filename)
                shutil.copy2(image_path, dest_path)
                print(f"复制图像: {image_path} -> {dest_path}")
            
            print(f"✓ 成功复制 {len(self.image_paths)} 张图像到 {original_images_dir}")
            return True
            
        except Exception as e:
            print(f"✗ 复制图像文件时出错: {str(e)}")
            return False
    
    def run_image_processing(self):
        """运行image_process.py进行批量图像处理"""
        try:
            # 构建命令 - 传入包含图像文件的目录
            script_path = os.path.join(os.path.dirname(__file__), "image_process.py")
            # 图像文件在 temp_dir/original_images 目录中
            input_dir = os.path.join(self.temp_dir, "original_images")
            cmd = [sys.executable, script_path, "--batch", input_dir]
            
            print(f"执行命令: {' '.join(cmd)}")
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(__file__)
            )
            
            print(f"命令返回码: {result.returncode}")
            print(f"标准输出: {result.stdout}")
            if result.stderr:
                print(f"标准错误: {result.stderr}")
            
            if result.returncode == 0:
                # image_process.py会创建 {input_dir}_processed 目录
                expected_output_dir = f"{input_dir}_processed"
                if os.path.exists(expected_output_dir):
                    print(f"找到处理后的目录: {expected_output_dir}")
                    return expected_output_dir
                else:
                    print(f"警告: 预期的输出目录不存在: {expected_output_dir}")
                    # 检查是否有其他可能的输出目录
                    parent_dir = os.path.dirname(input_dir)
                    for item in os.listdir(parent_dir):
                        item_path = os.path.join(parent_dir, item)
                        if os.path.isdir(item_path) and "processed" in item:
                            print(f"找到备用处理目录: {item_path}")
                            return item_path
                    return None
            else:
                print(f"图像处理失败，返回码: {result.returncode}")
                print(f"错误信息: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"运行图像处理时出错: {str(e)}")
            return None
    
    def get_processed_images(self, processed_dir):
        """获取处理后的图像文件列表"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        processed_images = []
        
        for file_path in Path(processed_dir).iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                processed_images.append(str(file_path))
        
        return sorted(processed_images)
    
    def run_concurrent_ocr(self, processed_images):
        """按腾讯云API频率限制处理多个图像的OCR - 每2秒发送2张图片"""
        import time
        import threading
        from queue import Queue
        
        successful_count = 0
        completed_count = 0
        total_images = len(processed_images)
        
        # 按每批2张图片分组
        batch_size = 2
        batches = [processed_images[i:i + batch_size] for i in range(0, total_images, batch_size)]
        
        # 用于收集所有任务结果的队列和字典
        result_queue = Queue()
        all_futures = {}
        
        # 创建一个持久的线程池
        executor = ThreadPoolExecutor(max_workers=10)  # 足够大的线程池
        
        try:
            # 按时间间隔发送批次
            for batch_index, batch in enumerate(batches):
                if self.should_stop:
                    break
                
                # 发送当前批次
                batch_start_time = time.time()
                for i, image_path in enumerate(batch):
                    global_index = batch_index * batch_size + i
                    future = executor.submit(self.run_ocr_pipeline, image_path)
                    all_futures[future] = {
                        'image_path': image_path,
                        'global_index': global_index,
                        'batch_index': batch_index
                    }
                
                # 更新发送进度
                sent_count = min((batch_index + 1) * batch_size, total_images)
                self.progress_updated.emit(
                    20 + int((sent_count / total_images) * 10),
                    f"已发送请求 ({sent_count}/{total_images})..."
                )
                
                # 如果不是最后一批，等待到2秒间隔
                if batch_index < len(batches) - 1 and not self.should_stop:
                    elapsed = time.time() - batch_start_time
                    wait_time = max(0, 2.0 - elapsed)
                    if wait_time > 0:
                        time.sleep(wait_time)
            
            # 收集所有结果
            for future in as_completed(all_futures):
                if self.should_stop:
                    # 如果需要停止，取消所有未完成的任务
                    for f in all_futures:
                        f.cancel()
                    break
                
                info = all_futures[future]
                image_path = info['image_path']
                global_index = info['global_index']
                completed_count += 1
                
                try:
                    ocr_result = future.result()
                    filename = os.path.basename(image_path)
                    
                    # 更新进度
                    progress = 30 + int((completed_count / total_images) * 60)
                    self.progress_updated.emit(
                        progress, 
                        f"OCR处理 ({completed_count}/{total_images}): {filename}"
                    )
                    
                    if ocr_result and ocr_result.get("status") == "success":
                        # 解析JSON结果
                        raw_result = ocr_result.get("raw_output", "")
                        parsed_result = self.parse_ocr_result(raw_result)
                        
                        if parsed_result:
                            # 进行数据二次处理
                            processed_result = self.post_process_result(parsed_result)
                            self.image_processed.emit(global_index, {
                                "image_path": image_path,
                                "result": processed_result,
                                "status": "success"
                            })
                            successful_count += 1
                        else:
                            self.image_processed.emit(global_index, {
                                "image_path": image_path,
                                "error": "OCR结果解析失败",
                                "status": "error"
                            })
                    else:
                        error_msg = ocr_result.get("error", "OCR处理失败") if ocr_result else "OCR处理失败"
                        self.image_processed.emit(global_index, {
                            "image_path": image_path,
                            "error": error_msg,
                            "status": "error"
                        })
                        
                except Exception as e:
                    self.image_processed.emit(global_index, {
                        "image_path": image_path,
                        "error": f"并发处理异常: {str(e)}",
                        "status": "error"
                    })
        
        finally:
            executor.shutdown(wait=True)
        
        return successful_count

    def run_ocr_pipeline(self, image_path):
        """对单个处理后的图像运行OCR流程"""
        try:
            # 构建命令
            script_path = os.path.join(os.path.dirname(__file__), "ocr_pipeline.py")
            cmd = [sys.executable, script_path, image_path, "--api-key", self.deepseek_api_key]
            
            # 如果指定了场号，添加场号参数
            if self.scene_numbers:
                scene_numbers_str = ','.join(map(str, self.scene_numbers))
                cmd.extend(["--scene-numbers", scene_numbers_str])
            
            print(f"执行OCR命令: {' '.join(cmd)}")
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(__file__)
            )
            
            print(f"OCR返回码: {result.returncode}")
            if result.stdout:
                print(f"OCR输出: {result.stdout}")  # 显示完整输出
            if result.stderr:
                print(f"OCR错误: {result.stderr}")
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "image_path": image_path,
                    "raw_output": result.stdout.strip()
                }
            else:
                return {
                    "status": "error",
                    "image_path": image_path,
                    "error": result.stderr,
                    "raw_output": result.stdout
                }
                
        except Exception as e:
            print(f"OCR流程异常: {str(e)}")
            return {
                "status": "error",
                "image_path": image_path,
                "error": str(e)
            }
    
    def parse_ocr_result(self, raw_result):
        """解析OCR处理结果"""
        try:
            if isinstance(raw_result, str):
                # 方法1: 尝试找到完整的JSON对象
                lines = raw_result.strip().split('\n')
                
                # 寻找可能的JSON行
                for line in lines:
                    line = line.strip()
                    if line.startswith('{') and line.endswith('}'):
                        try:
                            parsed = json.loads(line)
                            if isinstance(parsed, dict) and ('headers' in parsed or 'rows' in parsed):
                                return parsed
                        except:
                            continue
                
                # 方法2: 寻找多行JSON
                json_lines = []
                in_json = False
                brace_count = 0
                
                for line in lines:
                    line = line.strip()
                    if not in_json and line.startswith('{'):
                        in_json = True
                        brace_count = 0
                    
                    if in_json:
                        json_lines.append(line)
                        brace_count += line.count('{') - line.count('}')
                        
                        if brace_count == 0 and line.endswith('}'):
                            # 完整的JSON对象
                            json_str = '\n'.join(json_lines)
                            try:
                                parsed = json.loads(json_str)
                                if isinstance(parsed, dict) and ('headers' in parsed or 'rows' in parsed):
                                    return parsed
                            except:
                                pass
                            # 重置状态继续寻找
                            json_lines = []
                            in_json = False
                            brace_count = 0
                
                # 方法3: 使用原来的方法作为后备
                start_idx = raw_result.find('{')
                end_idx = raw_result.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = raw_result[start_idx:end_idx+1]
                    try:
                        return json.loads(json_str)
                    except:
                        pass
                        
            elif isinstance(raw_result, dict):
                return raw_result
                
            return None
            
        except Exception as e:
            print(f"解析OCR结果时出错: {str(e)}")
            print(f"原始结果前500字符: {str(raw_result)[:500]}")
            return None
    
    def post_process_result(self, ocr_result):
        """
        对OCR结果进行二次处理
        - 视效字段：将所有有值的改为"VFX"
        - 成绩字段：√、v、V等改为OK，o、0等改为NG，x、X等改为NG
        """
        if not ocr_result or 'rows' not in ocr_result:
            return ocr_result
        
        processed_result = ocr_result.copy()
        processed_rows = []
        
        for row in processed_result['rows']:
            if isinstance(row, dict):
                processed_row = row.copy()
                
                # 处理视效字段 (vfx)
                vfx_value = processed_row.get('vfx', '').strip()
                if vfx_value:  # 如果有值且不为空
                    processed_row['vfx'] = 'VFX'
                
                # 处理成绩字段 (result)
                result_value = processed_row.get('result', '').strip().lower()
                if result_value:
                    if result_value in ['√', 'v', '✓', '对', 'ok','OK', 'good']:
                        processed_row['result'] = 'OK'
                    elif result_value in ['o', '0', '○', '圆']:
                        processed_row['result'] = 'NG'
                    elif result_value in ['x', '×', '✗', '错', 'error', 'fail', 'NG', 'ng']:
                        processed_row['result'] = 'NG'
                    # 如果不匹配任何规则，保持原值
                
                processed_rows.append(processed_row)
            else:
                # 如果是数组格式，保持原样
                processed_rows.append(row)
        
        processed_result['rows'] = processed_rows
        return processed_result
    
    def stop(self):
        """停止处理"""
        self.should_stop = True 