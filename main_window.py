#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import tempfile
import subprocess
import json
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QLabel, QTableWidget, QTableWidgetItem, QPushButton, 
    QScrollArea, QStatusBar, QMenuBar, QToolBar, QProgressBar,
    QFileDialog, QMessageBox, QHeaderView, QFrame, QLineEdit
)
from PySide6.QtCore import Qt, QSize, Signal, QThread
from PySide6.QtGui import QPixmap, QAction

# 导入PDF转换功能
from pdf_to_png import pdf_to_png

class BatchProcessThread(QThread):
    """后台批量处理线程"""
    
    # 信号定义
    progress_updated = Signal(int, str)  # 进度百分比, 状态消息
    image_processed = Signal(int, dict)  # 图像索引, OCR结果
    process_finished = Signal(bool, str)  # 是否成功, 消息
    
    def __init__(self, image_paths, temp_dir, scene_numbers=None, deepseek_api_key="sk-f71759d6e28b4985818ea73abcc4eebb"):
        super().__init__()
        self.image_paths = image_paths
        self.temp_dir = temp_dir
        self.scene_numbers = scene_numbers
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
                            self.image_processed.emit(global_index, {
                                "image_path": image_path,
                                "result": parsed_result,
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
    
    def stop(self):
        """停止处理"""
        self.should_stop = True

class ImageViewer(QWidget):
    """图像显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.current_pixmap = None
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        
        # 图像显示区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setMinimumSize(500, 600)  # 增大最小尺寸
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setText("请选择PDF文件")
        self.scroll_area.setWidget(self.image_label)
        
        layout.addWidget(self.scroll_area)
        
        # 导航按钮
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 5, 0, 0)
        
        self.prev_button = QPushButton("上一张")
        self.next_button = QPushButton("下一张")
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        
        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_button)
        
        layout.addLayout(nav_layout)
        
    def set_image(self, image_path):
        """设置显示图像"""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.current_pixmap = pixmap
            # 适应显示区域大小
            scaled_pixmap = pixmap.scaled(
                self.scroll_area.size() - QSize(20, 20), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("无法加载图像")

class TableEditor(QWidget):
    """表格编辑组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        
        # 表格
        self.table = QTableWidget()
        self.table.setMinimumSize(700, 600)  # 增大最小尺寸
        
        # 设置默认列
        self.setup_default_table()
        
        layout.addWidget(self.table)
        
        # 表格操作按钮
        table_buttons_layout = QHBoxLayout()
        table_buttons_layout.setContentsMargins(0, 5, 0, 0)
        
        self.add_row_button = QPushButton("添加行")
        self.delete_row_button = QPushButton("删除行")
        self.clear_table_button = QPushButton("清空表格")
        
        table_buttons_layout.addWidget(self.add_row_button)
        table_buttons_layout.addWidget(self.delete_row_button)
        table_buttons_layout.addWidget(self.clear_table_button)
        table_buttons_layout.addStretch()
        
        layout.addLayout(table_buttons_layout)
        
        # 连接信号
        self.add_row_button.clicked.connect(self.add_row)
        self.delete_row_button.clicked.connect(self.delete_row)
        self.clear_table_button.clicked.connect(self.clear_table)
        
    def setup_default_table(self):
        """设置默认表格结构"""
        headers = ["场号", "镜号", "次数", "景别", "时码", "视效", "成绩"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        # 添加一些默认行
        self.table.setRowCount(5)
        
    def add_row(self):
        """添加行"""
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        
    def delete_row(self):
        """删除选中行"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            
    def clear_table(self):
        """清空表格"""
        self.table.clearContents()
        self.table.setRowCount(0)
        
    def load_data(self, data):
        """加载数据到表格"""
        if not data or 'rows' not in data:
            return
            
        rows = data['rows']
        self.table.setRowCount(len(rows))
        
        for i, row in enumerate(rows):
            if isinstance(row, dict):
                # 新的JSON格式
                values = [
                    row.get('scene', ''),
                    row.get('shot', ''),
                    row.get('take', ''),
                    row.get('framing', ''),
                    row.get('timecode', ''),
                    row.get('vfx', ''),
                    row.get('result', '')
                ]
            else:
                # 数组格式
                values = row
                
            for j, value in enumerate(values):
                if j < self.table.columnCount():
                    item = QTableWidgetItem(str(value))
                    self.table.setItem(i, j, item)

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.current_images = []
        self.current_index = 0
        self.ocr_results = {}
        self.temp_dir = None      # 临时目录路径
        self.process_thread = None  # 后台处理线程
        self.setup_ui()
        self.connect_signals()
        
    def parse_scene_numbers(self, scene_input):
        """解析场号输入字符串
        
        Args:
            scene_input (str): 用户输入的场号字符串，例如 "23a,24b,25c"
            
        Returns:
            list: 解析后的场号列表，例如 ["23a", "24b", "25c"]
            None: 如果输入为空或无效
        """
        if not scene_input or not scene_input.strip():
            return None
            
        scene_numbers = []
        try:
            # 按逗号分割
            parts = scene_input.strip().split(',')
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                
                # 直接添加场号字符串（可以是数字、字母或混合）
                scene_numbers.append(part)
            
            # 去重但保持输入顺序
            seen = set()
            result = []
            for scene in scene_numbers:
                if scene not in seen:
                    seen.add(scene)
                    result.append(scene)
            
            return result
            
        except Exception as e:
            # 如果解析失败，显示错误信息
            QMessageBox.warning(self, "场号格式错误", 
                              f"场号格式不正确: {scene_input}\n"
                              f"请使用正确格式，例如: 23a,24b,25c")
            return None
        
    def setup_ui(self):
        self.setWindowTitle("场记单OCR处理系统")
        self.setMinimumSize(1400, 900)  # 增大最小尺寸
        self.resize(1600, 1000)  # 设置默认窗口大小
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏
        self.create_tool_bar()
        
        # 创建中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)  # 减小边距给内容更多空间
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板 - 图像显示
        self.image_viewer = ImageViewer()
        splitter.addWidget(self.image_viewer)
        
        # 右侧面板 - 表格编辑
        self.table_editor = TableEditor()
        splitter.addWidget(self.table_editor)
        
        # 设置分割比例 - 让表格和图像占据更多空间
        splitter.setSizes([600, 900])  # 增大比例
        splitter.setStretchFactor(0, 1)  # 左侧可拉伸
        splitter.setStretchFactor(1, 2)  # 右侧表格更重要，拉伸因子更大
        
        main_layout.addWidget(splitter, 1)  # 设置拉伸因子为1，占据大部分空间
        
        # 底部操作区域
        self.create_bottom_panel(main_layout)
        
        # 创建状态栏
        self.create_status_bar()
        
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        open_action = QAction("打开PDF", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_pdf)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("保存表格", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_table)
        file_menu.addAction(save_action)
        
        export_action = QAction("导出全部", self)
        export_action.triggered.connect(self.export_all_results)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        
        undo_action = QAction("撤销", self)
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("重做", self)
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图")
        
        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcut("Ctrl++")
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("缩小", self)
        zoom_out_action.setShortcut("Ctrl+-")
        view_menu.addAction(zoom_out_action)
        
        fit_window_action = QAction("适应窗口", self)
        fit_window_action.setShortcut("Ctrl+0")
        view_menu.addAction(fit_window_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_tool_bar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)
        
        # 选择PDF按钮
        open_pdf_action = QAction("选择PDF", self)
        open_pdf_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_pdf_action)
        
        toolbar.addSeparator()
        
        # 添加场号输入控件到工具栏
        scene_widget = QWidget()
        scene_layout = QHBoxLayout(scene_widget)
        scene_layout.setContentsMargins(5, 0, 5, 0)
        
        scene_label = QLabel("指定场号:")
        self.scene_numbers_input = QLineEdit()
        self.scene_numbers_input.setPlaceholderText("例如: 1,2,23a,12 (留空则处理所有场号)")
        self.scene_numbers_input.setMinimumWidth(300)
        self.scene_numbers_input.setMaximumWidth(400)
        
        scene_layout.addWidget(scene_label)
        scene_layout.addWidget(self.scene_numbers_input)
        
        toolbar.addWidget(scene_widget)
        toolbar.addSeparator()
        
        # 开始批量处理按钮
        self.start_process_action = QAction("开始批量处理", self)
        self.start_process_action.triggered.connect(self.start_batch_process)
        self.start_process_action.setEnabled(False)  # 初始状态禁用
        toolbar.addAction(self.start_process_action)
        
        # 停止处理按钮
        self.stop_process_action = QAction("停止处理", self)
        self.stop_process_action.triggered.connect(self.stop_batch_process)
        self.stop_process_action.setEnabled(False)  # 初始状态禁用
        toolbar.addAction(self.stop_process_action)
        
        toolbar.addSeparator()
        
        # 保存按钮
        save_action = QAction("保存", self)
        save_action.triggered.connect(self.save_current_table)
        toolbar.addAction(save_action)
        
        # 导出按钮
        export_action = QAction("导出", self)
        export_action.triggered.connect(self.export_all_results)
        toolbar.addAction(export_action)
        
    def create_bottom_panel(self, main_layout):
        """创建底部操作面板"""
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        
        # 底部按钮布局 - 只保留保存和导出按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 10, 0, 10)
        
        self.save_table_button = QPushButton("保存当前表格")
        self.save_table_button.setMinimumHeight(35)
        
        self.export_all_button = QPushButton("导出全部结果")
        self.export_all_button.setMinimumHeight(35)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_table_button)
        bottom_layout.addWidget(self.export_all_button)
        
        main_layout.addLayout(bottom_layout)
        
    def create_status_bar(self):
        """创建状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # 当前页面信息
        self.page_info_label = QLabel("当前: 0/0")
        self.statusbar.addWidget(self.page_info_label)
        
        self.statusbar.addPermanentWidget(QLabel(" | "))
        
        # 状态信息
        self.status_label = QLabel("状态: 就绪")
        self.statusbar.addWidget(self.status_label)
        
        self.statusbar.addPermanentWidget(QLabel(" | "))
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.statusbar.addPermanentWidget(self.progress_bar)
        
    def connect_signals(self):
        """连接信号槽"""
        # 图像导航
        self.image_viewer.prev_button.clicked.connect(self.prev_image)
        self.image_viewer.next_button.clicked.connect(self.next_image)
        
        # 底部按钮
        self.save_table_button.clicked.connect(self.save_current_table)
        self.export_all_button.clicked.connect(self.export_all_results)
        
    def open_pdf(self):
        """打开PDF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择PDF文件", 
            "", 
            "PDF文件 (*.pdf)"
        )
        
        if file_path:
            self.load_pdf(file_path)
            
    def load_pdf(self, pdf_path):
        """加载PDF文件"""
        try:
            self.status_label.setText("状态: 正在转换PDF为图像...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 不确定进度
            
            # 创建临时目录在项目目录下
            project_dir = os.path.dirname(os.path.abspath(__file__))
            temp_base_dir = os.path.join(project_dir, "temp")
            os.makedirs(temp_base_dir, exist_ok=True)
            self.temp_dir = tempfile.mkdtemp(prefix="yyhg_ocr_", dir=temp_base_dir)
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_dir = os.path.join(self.temp_dir, "original_images")
            
            # 转换PDF为PNG图像
            converted_files = pdf_to_png(pdf_path, output_dir, dpi=300)
            
            if converted_files:
                self.current_images = converted_files
                self.current_index = 0
                self.ocr_results = {}  # 清空之前的OCR结果
                
                self.update_image_display()
                self.status_label.setText(f"状态: PDF转换完成，共{len(converted_files)}页")
                
                # 启用开始处理按钮
                self.start_process_action.setEnabled(True)
                
                # 显示成功消息
                QMessageBox.information(
                    self, 
                    "转换成功", 
                    f"PDF已成功转换为{len(converted_files)}张图像\n"
                    f"临时目录: {self.temp_dir}\n\n"
                    f"请输入要处理的场号，然后点击'开始批量处理'按钮"
                )
            else:
                self.current_images = []
                self.current_index = 0
                self.start_process_action.setEnabled(False)  # 禁用开始按钮
                self.status_label.setText("状态: PDF转换失败")
                
                QMessageBox.warning(
                    self, 
                    "转换失败", 
                    "PDF转换失败，请检查文件是否有效\n"
                    "或者确保已安装PDF转换库:\n"
                    "pip install PyMuPDF"
                )
                
        except Exception as e:
            self.current_images = []
            self.current_index = 0
            self.start_process_action.setEnabled(False)  # 禁用开始按钮
            self.status_label.setText("状态: PDF加载出错")
            
            QMessageBox.critical(
                self, 
                "加载错误", 
                f"PDF加载时发生错误:\n{str(e)}"
            )
        finally:
            self.progress_bar.setVisible(False)
            
    def update_image_display(self):
        """更新图像显示"""
        if not self.current_images:
            return
            
        # 更新图像
        current_image = self.current_images[self.current_index]
        self.image_viewer.set_image(current_image)
        
        # 更新导航按钮状态
        self.image_viewer.prev_button.setEnabled(self.current_index > 0)
        self.image_viewer.next_button.setEnabled(self.current_index < len(self.current_images) - 1)
        
        # 更新页面信息
        self.page_info_label.setText(f"当前: {self.current_index + 1}/{len(self.current_images)}")
        
        # 加载对应的OCR结果
        if self.current_index in self.ocr_results:
            self.update_table_display(self.ocr_results[self.current_index])
        else:
            # 清空表格显示
            self.table_editor.table.setRowCount(0)
            self.table_editor.table.setColumnCount(0)
            
    def prev_image(self):
        """上一张图像"""
        if self.current_index > 0:
            self.save_current_table_data()
            self.current_index -= 1
            self.update_image_display()
            
    def next_image(self):
        """下一张图像"""
        if self.current_index < len(self.current_images) - 1:
            self.save_current_table_data()
            self.current_index += 1
            self.update_image_display()
            
    def save_current_table_data(self):
        """保存当前表格数据到内存"""
        # TODO: 从表格获取数据并保存到self.ocr_results[self.current_index]
        pass
        
    def start_batch_process(self):
        """开始批量处理"""
        if not self.current_images:
            QMessageBox.warning(self, "警告", "请先选择PDF文件")
            return
            
        if not self.temp_dir:
            QMessageBox.warning(self, "警告", "临时目录未创建，请重新选择PDF文件")
            return
            
        # 检查是否已有处理线程在运行
        if self.process_thread and self.process_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "确认", 
                "已有处理任务在运行，是否停止当前任务？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.stop_batch_process()
            return
        
        # 启动后台处理线程
        self.status_label.setText("状态: 正在启动批量处理...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 更新按钮状态
        self.start_process_action.setEnabled(False)
        self.stop_process_action.setEnabled(True)
        
        # 解析场号输入
        scene_numbers = self.parse_scene_numbers(self.scene_numbers_input.text())
        
        # 创建并启动处理线程
        original_images_dir = os.path.join(self.temp_dir, "original_images")
        self.process_thread = BatchProcessThread(self.current_images, original_images_dir, scene_numbers)
        
        # 连接信号
        self.process_thread.progress_updated.connect(self.on_progress_updated)
        self.process_thread.image_processed.connect(self.on_image_processed)
        self.process_thread.process_finished.connect(self.on_process_finished)
        
        # 启动线程
        self.process_thread.start()
    
    def stop_batch_process(self):
        """停止批量处理"""
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.process_thread.wait(3000)  # 等待3秒
            
        # 更新按钮状态
        self.start_process_action.setEnabled(True)
        self.stop_process_action.setEnabled(False)
            
        self.status_label.setText("状态: 处理已停止")
        self.progress_bar.setVisible(False)
    
    def on_progress_updated(self, progress, message):
        """处理进度更新"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(f"状态: {message}")
    
    def on_image_processed(self, index, result):
        """处理单个图像完成"""
        # 存储结果
        self.ocr_results[index] = result
        
        # 如果是当前显示的图像，更新表格显示
        if index == self.current_index:
            self.update_table_display(result)
    
    def on_process_finished(self, success, message):
        """处理完成"""
        # 更新按钮状态
        self.start_process_action.setEnabled(True)
        self.stop_process_action.setEnabled(False)
        
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText(f"状态: {message}")
            QMessageBox.information(self, "处理完成", message)
            
            # 更新当前显示
            if self.current_index in self.ocr_results:
                self.update_table_display(self.ocr_results[self.current_index])
        else:
            self.status_label.setText(f"状态: 处理失败 - {message}")
            QMessageBox.warning(self, "处理失败", message)
    
    def update_table_display(self, result):
        """更新表格显示"""
        if not result or result.get("status") == "error":
            # 显示错误信息
            self.table_editor.table.setRowCount(1)
            self.table_editor.table.setColumnCount(1)
            error_msg = result.get("error", "未知错误") if result else "无结果"
            self.table_editor.table.setItem(0, 0, QTableWidgetItem(f"错误: {error_msg}"))
            return
            
        # 获取实际的表格数据
        table_data = result
        if "result" in result:
            # 如果result是嵌套结构，提取内层的result
            table_data = result["result"]
        
        # 显示正常结果
        if table_data and "rows" in table_data:
            rows = table_data["rows"]
            headers = table_data.get("headers", ["场号", "镜号", "次数", "景别", "时码", "视效", "成绩"])
            
            self.table_editor.table.setRowCount(len(rows))
            self.table_editor.table.setColumnCount(len(headers))
            self.table_editor.table.setHorizontalHeaderLabels(headers)
            
            for i, row in enumerate(rows):
                if isinstance(row, dict):
                    # 新格式
                    row_data = [
                        row.get('scene', ''),
                        row.get('shot', ''),
                        row.get('take', ''),
                        row.get('framing', ''),
                        row.get('timecode', ''),
                        row.get('vfx', ''),
                        row.get('result', '')
                    ]
                else:
                    # 数组格式
                    row_data = row
                
                for j, cell_value in enumerate(row_data):
                    if j < len(headers):
                        item = QTableWidgetItem(str(cell_value))
                        self.table_editor.table.setItem(i, j, item)
        else:
            # 如果没有找到有效的表格数据，显示提示
            self.table_editor.table.setRowCount(1)
            self.table_editor.table.setColumnCount(1)
            self.table_editor.table.setItem(0, 0, QTableWidgetItem("未找到表格数据"))
        
    def save_current_table(self):
        """保存当前表格"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存表格", 
            "", 
            "Excel文件 (*.xlsx);;CSV文件 (*.csv)"
        )
        
        if file_path:
            # TODO: 实现保存功能
            QMessageBox.information(self, "提示", f"表格已保存到: {file_path}")
            
    def export_all_results(self):
        """导出全部结果"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        
        if folder_path:
            # TODO: 实现导出功能
            QMessageBox.information(self, "提示", f"全部结果已导出到: {folder_path}")
            
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, 
            "关于", 
            "场记单OCR处理系统\n\n"
            "版本: 1.0.0\n"
            "功能: PDF场记单批量OCR识别和表格编辑"
        )
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止处理线程
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.process_thread.wait(3000)
        
        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"已清理临时目录: {self.temp_dir}")
            except Exception as e:
                print(f"清理临时目录失败: {e}")
        
        event.accept()

def main():
    """主函数"""
    try:
        app = QApplication(sys.argv)
        
        # 设置应用信息
        app.setApplicationName("场记单OCR处理系统")
        app.setApplicationVersion("1.0.0")
        
        # 创建主窗口
        window = MainWindow()
        window.show()
        
        print("界面启动成功！")
        print("提示：macOS系统警告信息可以忽略，不影响程序运行。")
        
        # 运行应用
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"导入错误：{e}")
        print("请确保已安装PySide6：pip install PySide6")
        sys.exit(1)
    except Exception as e:
        print(f"程序启动失败：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 