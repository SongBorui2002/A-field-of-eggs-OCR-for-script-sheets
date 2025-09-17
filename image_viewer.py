#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QPushButton
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap


class ImageViewer(QWidget):
    """图像显示组件"""
    
    # 添加信号
    process_current_requested = Signal()
    
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
        
        # 添加处理当前场记单按钮
        self.process_current_button = QPushButton("处理当前场记单")
        self.process_current_button.setEnabled(False)
        self.process_current_button.clicked.connect(self.process_current_requested.emit)
        # self.process_current_button.setStyleSheet("""
        #     QPushButton {
        #         background-color: #4CAF50;
        #         color: white;
        #         font-weight: bold;
        #         padding: 5px 10px;
        #     }
        #     QPushButton:hover {
        #         background-color: #45a049;
        #     }
        #     QPushButton:disabled {
        #         background-color: #cccccc;
        #         color: #666666;
        #     }
        # """)
        
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.process_current_button)
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
            
    def set_process_button_enabled(self, enabled):
        """设置处理按钮的启用状态"""
        self.process_current_button.setEnabled(enabled)
        
    def set_process_button_text(self, text):
        """设置处理按钮的文本"""
        self.process_current_button.setText(text) 