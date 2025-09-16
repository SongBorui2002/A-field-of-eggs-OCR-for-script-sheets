#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView


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