#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import tempfile
import json
import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QLabel, QPushButton, 
    QStatusBar, QMenuBar, QToolBar,
    QFileDialog, QMessageBox, QFrame, QLineEdit
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

# 导入PDF转换功能
from pdf_to_png import PDFConverter

# 导入重构后的组件
from batch_thread import BatchProcessThread
from image_viewer import ImageViewer
from table_editor import TableEditor
from config import AppConfig


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        # 加载配置
        self.config = AppConfig()
        config_path = self.config.get_config_path()
        if os.path.exists(config_path):
            self.config = AppConfig.from_file(config_path)
        
        self.current_images = []
        self.current_index = 0
        self.ocr_results = {}
        self.card_numbers = {}    # 存储每张图像对应的卡号 {index: card_number}
        self.table_data = {}      # 存储每张图像对应的表格数据 {index: table_data}
        self.temp_dir = None      # 临时目录路径
        self.process_thread = None  # 后台处理线程
        self.current_pdf_path = ""  # 当前打开的PDF文件路径
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
        # 使用配置中的窗口大小设置
        window_config = self.config.window_config
        self.setMinimumSize(window_config['min_width'], window_config['min_height'])
        self.resize(window_config['default_width'], window_config['default_height'])
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏
        self.create_tool_bar()
        
        # 创建中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板 - 图像显示
        self.image_viewer = ImageViewer()
        splitter.addWidget(self.image_viewer)
        
        # 右侧面板 - 表格编辑
        self.table_editor = TableEditor()
        splitter.addWidget(self.table_editor)
        
        # 设置分割比例
        splitter.setSizes(window_config['splitter_sizes'])
        splitter.setStretchFactor(0, 1)  # 左侧可拉伸
        splitter.setStretchFactor(1, 2)  # 右侧表格更重要，拉伸因子更大
        
        main_layout.addWidget(splitter, 1)
        
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
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_tool_bar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # 打开PDF
        open_action = QAction("打开PDF", self)
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        # PDF路径显示标签
        self.pdf_path_label = QLabel()
        self.pdf_path_label.setText("PDF文件: 未选择")
        self.pdf_path_label.setMaximumWidth(600)  # 设置最大宽度
        self.pdf_path_label.setStyleSheet("QLabel { padding: 2px 8px; }")  # 添加内边距
        toolbar.addWidget(self.pdf_path_label)
        
        toolbar.addSeparator()
        
        
    def create_bottom_panel(self, main_layout):
        """创建底部操作面板"""
        bottom_frame = QFrame()
        bottom_frame.setFrameStyle(QFrame.Box)
        bottom_frame.setMaximumHeight(150)  # 限制底部面板最大高度
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(10, 5, 10, 5)  # 减少垂直边距
        bottom_layout.setSpacing(5)  # 减少控件间距
        
        # 场号输入和OCR处理按钮放在同一行
        top_controls_layout = QHBoxLayout()
        
        # 场号输入
        scene_label = QLabel("指定场号:")
        scene_label.setMinimumWidth(70)
        self.scene_input = QLineEdit()
        self.scene_input.setPlaceholderText("例如: 23a,24b,25c")
        #self.scene_input.setMaximumWidth(1400)
        
        top_controls_layout.addWidget(scene_label)
        top_controls_layout.addWidget(self.scene_input, 1)
        top_controls_layout.addSpacing(20)  # 添加间距
        
        # OCR处理按钮
        self.start_button = QPushButton("开始批量处理")
        self.start_button.clicked.connect(self.start_batch_process)
        self.start_button.setEnabled(False)
        
        self.stop_button = QPushButton("停止处理")
        self.stop_button.clicked.connect(self.stop_batch_process)
        self.stop_button.setEnabled(False)
        
        top_controls_layout.addWidget(self.start_button)
        top_controls_layout.addWidget(self.stop_button)
        top_controls_layout.addStretch()
        
        bottom_layout.addLayout(top_controls_layout)
        
        # 元数据处理区域 - 简化为一行
        metadata_layout = QHBoxLayout()
        metadata_label = QLabel("元数据CSV:")
        metadata_label.setMinimumWidth(80)
        
        self.metadata_path_input = QLineEdit()
        self.metadata_path_input.setPlaceholderText("选择要更新的CSV文件...")
        self.metadata_path_input.setReadOnly(True)
        
        self.select_metadata_button = QPushButton("选择文件")
        self.select_metadata_button.clicked.connect(self.select_metadata_file)
        
        self.start_metadata_button = QPushButton("开始录入元数据")
        self.start_metadata_button.clicked.connect(self.start_metadata_update)
        self.start_metadata_button.setEnabled(False)
        
        metadata_layout.addWidget(metadata_label)
        metadata_layout.addWidget(self.metadata_path_input, 1)
        metadata_layout.addWidget(self.select_metadata_button)
        metadata_layout.addWidget(self.start_metadata_button)
        metadata_layout.addStretch()
        
        bottom_layout.addLayout(metadata_layout)
        
        main_layout.addWidget(bottom_frame)
        
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("准备就绪")
        
    def connect_signals(self):
        """连接信号"""
        # 连接图像查看器的导航按钮
        self.image_viewer.prev_button.clicked.connect(self.prev_image)
        self.image_viewer.next_button.clicked.connect(self.next_image)
        
        # 连接卡号输入框的信号
        self.table_editor.card_input.textChanged.connect(self.on_card_number_changed)
        
    def open_pdf(self):
        """打开PDF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF文件 (*.pdf)"
        )
        
        if file_path:
            self.current_pdf_path = file_path
            self.pdf_path_label.setText(f"PDF文件: {file_path}")
            self.pdf_path_label.setToolTip(f"完整路径: {file_path}")  # 设置工具提示显示完整路径
            self.convert_pdf_to_images(file_path)
            
    def convert_pdf_to_images(self, pdf_path):
        """将PDF转换为图像"""
        try:
            # 创建临时目录在项目目录下
            project_dir = os.path.dirname(os.path.abspath(__file__))
            temp_base_dir = os.path.join(project_dir, "temp")
            os.makedirs(temp_base_dir, exist_ok=True)
            
            # 清理旧的临时目录
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            
            self.temp_dir = tempfile.mkdtemp(prefix="ocr_", dir=temp_base_dir)
            
            # 转换PDF
            self.status_bar.showMessage("正在转换PDF...")
            converter = PDFConverter()
            image_paths = converter.convert(pdf_path, self.temp_dir)
            
            if image_paths:
                self.current_images = image_paths
                self.current_index = 0
                self.ocr_results = {}
                self.card_numbers = {}  # 清空卡号数据
                
                # 显示第一张图像
                self.show_current_image()
                
                # 启用处理按钮
                self.start_button.setEnabled(True)
                
                self.status_bar.showMessage(f"成功加载 {len(image_paths)} 张图像")
            else:
                QMessageBox.warning(self, "错误", "PDF转换失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"转换PDF时出错: {str(e)}")
            
    def save_current_table_data(self):
        """保存当前表格数据"""
        if hasattr(self, 'current_index') and self.current_index >= 0:
            # 保存卡号
            card_number = self.table_editor.get_card_number()
            self.card_numbers[self.current_index] = card_number
            
            # 保存表格数据
            table_records = self.table_editor.export_for_metadata_update(card_number)
            self.table_data[self.current_index] = table_records

    def show_current_image(self):
        """显示当前图像"""
        if self.current_images and 0 <= self.current_index < len(self.current_images):
            image_path = self.current_images[self.current_index]
            self.image_viewer.set_image(image_path)
        
        # 更新导航按钮状态
        self.image_viewer.prev_button.setEnabled(self.current_index > 0)
        self.image_viewer.next_button.setEnabled(self.current_index < len(self.current_images) - 1)
        
        # 加载当前图像的卡号
        card_number = self.card_numbers.get(self.current_index, "")
        self.table_editor.set_card_number(card_number)
        
        # 优先加载保存的表格数据，如果没有则加载OCR结果
        if self.current_index in self.table_data and self.table_data[self.current_index]:
            # 加载保存的表格数据
            self.load_table_data_from_records(self.table_data[self.current_index])
        elif self.current_index in self.ocr_results:
            # 加载OCR结果
            result = self.ocr_results[self.current_index]
            if result.get('status') == 'success':
                self.table_editor.load_data(result.get('result', {}))
                
    def load_table_data_from_records(self, records):
        """从记录列表加载表格数据"""
        if not records:
            return
            
        self.table_editor.clear_table()
        self.table_editor.table.setRowCount(len(records))
        
        for i, record in enumerate(records):
            values = [
                record.get('scene', ''),
                record.get('shot', ''),
                record.get('take', ''),
                record.get('framing', ''),
                record.get('timecode', ''),
                record.get('vfx', ''),
                record.get('result', '')
            ]
            
            for j, value in enumerate(values):
                if j < self.table_editor.table.columnCount():
                    from PySide6.QtWidgets import QTableWidgetItem
                    item = QTableWidgetItem(str(value))
                    self.table_editor.table.setItem(i, j, item)
            
    def prev_image(self):
        """显示上一张图像"""
        if self.current_index > 0:
            # 保存当前表格数据
            self.save_current_table_data()
            self.current_index -= 1
            self.show_current_image()
            
    def next_image(self):
        """显示下一张图像"""
        if self.current_index < len(self.current_images) - 1:
            # 保存当前表格数据
            self.save_current_table_data()
            self.current_index += 1
            self.show_current_image()
        
    def start_batch_process(self):
        """开始批量处理"""
        if not self.current_images:
            QMessageBox.warning(self, "警告", "请先选择PDF文件")
            return
            
        # 解析场号
        scene_input = self.scene_input.text().strip()
        scene_numbers = self.parse_scene_numbers(scene_input) if scene_input else None
        
        # 创建处理线程
        self.process_thread = BatchProcessThread(
            self.current_images,
            self.temp_dir,
            scene_numbers,
            self.config.deepseek_api_key
        )
        
        # 连接信号
        self.process_thread.progress_updated.connect(self.update_progress)
        self.process_thread.image_processed.connect(self.handle_image_processed)
        self.process_thread.process_finished.connect(self.handle_process_finished)
        
        # 更新UI状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 开始处理
        self.process_thread.start()
    
    def stop_batch_process(self):
        """停止批量处理"""
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.status_bar.showMessage("正在停止处理...")
            
    def update_progress(self, value, message):
        """更新进度"""
        self.status_bar.showMessage(message)
        
    def handle_image_processed(self, index, result):
        """处理单个图像的结果"""
        self.ocr_results[index] = result
        
        # 如果是当前显示的图像，更新表格
        if index == self.current_index and result.get('status') == 'success':
            self.table_editor.load_data(result.get('result', {}))
            
    def handle_process_finished(self, success, message):
        """处理完成"""
        # 更新UI状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # 显示结果
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "处理失败", message)
            
        self.status_bar.showMessage("处理完成")
    
    def on_card_number_changed(self):
        """卡号输入变化时的处理"""
        if self.current_images and 0 <= self.current_index < len(self.current_images):
            card_number = self.table_editor.get_card_number()
            self.card_numbers[self.current_index] = card_number
        
    def save_current_table(self):
        """保存当前表格"""
        # TODO: 实现保存表格功能，需要包含卡号信息
        current_card = self.table_editor.get_card_number()
        QMessageBox.information(self, "提示", f"保存功能待实现\n当前卡号: {current_card}")
            
    def export_all_results(self):
        """导出所有结果"""
        # TODO: 实现导出功能，需要包含所有卡号信息
        card_count = len([card for card in self.card_numbers.values() if card])
        QMessageBox.information(self, "提示", f"导出功能待实现\n已设置卡号的图像数: {card_count}/{len(self.current_images)}")
            
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", 
                         "场记单OCR处理系统 v1.0\n\n"
                         "基于深度学习的场记单自动识别系统")
    
    def collect_all_table_data_for_metadata(self):
        """收集所有表格数据用于元数据更新"""
        from metadata_processor import MetadataProcessor
        
        all_records = []
        processor = MetadataProcessor()
        
        # 先保存当前表格数据
        self.save_current_table_data()
        
        # 遍历所有图像，收集表格数据
        for index in range(len(self.current_images)):
            card_number = self.card_numbers.get(index, "")
            
            # 优先使用保存的表格数据
            if index in self.table_data and self.table_data[index]:
                all_records.extend(self.table_data[index])
            # 如果没有保存的表格数据，尝试从OCR结果提取
            elif index in self.ocr_results and self.ocr_results[index].get('status') == 'success':
                records = processor.extract_records_from_ocr(self.ocr_results[index], card_number)
                all_records.extend(records)
        
        print(f"收集到的总记录数: {len(all_records)}")
        return all_records
    
    def select_metadata_file(self):
        """选择元数据CSV文件"""
        csv_path, _ = QFileDialog.getOpenFileName(
            self, "选择元数据CSV文件", "", "CSV files (*.csv)"
        )
        
        if csv_path:
            self.metadata_path_input.setText(csv_path)
            self.start_metadata_button.setEnabled(True)
    
    def start_metadata_update(self):
        """开始元数据更新（新增功能）"""
        from metadata_processor import MetadataProcessor
        
        # 获取选择的CSV文件路径
        csv_path = self.metadata_path_input.text().strip()
        
        if not csv_path:
            QMessageBox.warning(self, "警告", "请先选择元数据CSV文件")
            return
        
        if not os.path.exists(csv_path):
            QMessageBox.warning(self, "警告", "选择的CSV文件不存在")
            return
        
        # 收集场记单数据
        all_records = self.collect_all_table_data_for_metadata()
        
        if not all_records:
            QMessageBox.warning(self, "警告", "没有可用的场记单数据\n请先进行OCR处理或在表格中输入数据")
            return
        
        # 显示将要处理的记录数
        reply = QMessageBox.question(
            self, "确认", 
            f"找到 {len(all_records)} 条场记单记录\n选择的文件: {os.path.basename(csv_path)}\n\n是否继续进行元数据更新？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 处理元数据更新
        try:
            self.status_bar.showMessage("正在处理元数据更新...")
            self.start_metadata_button.setEnabled(False)
            
            processor = MetadataProcessor()
            result = processor.process_metadata_update(csv_path, all_records)
            
            # 显示结果
            if result.get('status') != 'error':
                message = f"元数据更新完成!\n\n"
                message += f"✓ 成功更新: {result['matched_count']} 条记录\n"
                message += f"⚠ 未找到匹配: {result['unmatched_count']} 条记录\n"
                message += f"❌ 处理错误: {result['error_count']} 条记录\n\n"
                message += f"输出文件: {result.get('output_path', 'N/A')}"
                QMessageBox.information(self, "完成", message)
                self.status_bar.showMessage("元数据更新完成")
            else:
                QMessageBox.critical(self, "错误", f"处理失败: {result['message']}")
                self.status_bar.showMessage("元数据更新失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"元数据更新过程中发生错误:\n{str(e)}")
            self.status_bar.showMessage("元数据更新出错")
        finally:
            self.start_metadata_button.setEnabled(True)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 保存当前表格数据
        self.save_current_table_data()
        
        # 停止处理线程
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.process_thread.wait()
        
        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        
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