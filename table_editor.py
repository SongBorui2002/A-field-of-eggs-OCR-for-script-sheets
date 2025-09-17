#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                              QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView,
                              QMenu, QMessageBox, QLabel, QLineEdit, QFrame)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QCursor

class TableEditor(QWidget):
    """表格编辑组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 拖拽相关状态
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_end_pos = None
        self.original_selection = []
        
        self.setup_ui()
        self.setup_advanced_features()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        
        # 卡号输入区域
        card_frame = QFrame()
        card_frame.setFrameStyle(QFrame.Box)
        card_layout = QHBoxLayout(card_frame)
        card_layout.setContentsMargins(8, 5, 8, 5)
        
        card_label = QLabel("卡号:")
        card_label.setMinimumWidth(50)
        self.card_input = QLineEdit()
        self.card_input.setPlaceholderText("请输入当前场记单的卡号")
        self.card_input.setMaximumWidth(200)
        
        card_layout.addWidget(card_label)
        card_layout.addWidget(self.card_input)
        card_layout.addStretch()
        
        layout.addWidget(card_frame)
        
        # 表格
        self.table = QTableWidget()
        self.table.setMinimumSize(700, 600)
        
        # 设置默认列
        self.setup_default_table()
        
        layout.addWidget(self.table)
        
        # 表格操作按钮
        table_buttons_layout = QHBoxLayout()
        table_buttons_layout.setContentsMargins(0, 5, 0, 0)
        
        self.add_row_button = QPushButton("添加行")
        self.delete_selected_button = QPushButton("删除选中")  # 改名以支持批量删除
        self.clear_table_button = QPushButton("清空表格")
        
        table_buttons_layout.addWidget(self.add_row_button)
        table_buttons_layout.addWidget(self.delete_selected_button)
        table_buttons_layout.addWidget(self.clear_table_button)
        table_buttons_layout.addStretch()
        
        layout.addLayout(table_buttons_layout)
        
        # 连接信号
        self.add_row_button.clicked.connect(self.add_row)
        self.delete_selected_button.clicked.connect(self.delete_selected)
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
        
    def setup_advanced_features(self):
        """设置高级功能：批量选择和拖拽填充"""
        # 启用多选
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        
        # 启用右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # 重写鼠标事件以支持拖拽填充
        self.table.mousePressEvent = self.table_mouse_press_event
        self.table.mouseMoveEvent = self.table_mouse_move_event
        self.table.mouseReleaseEvent = self.table_mouse_release_event
        
    def show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 删除选中项
        delete_action = QAction("删除选中行/列", self)
        delete_action.triggered.connect(self.delete_selected)
        menu.addAction(delete_action)
        
        menu.addSeparator()
        
        # 添加行
        add_row_action = QAction("插入行", self)
        add_row_action.triggered.connect(self.add_row)
        menu.addAction(add_row_action)
        
        # 清空选中
        clear_selection_action = QAction("清空选中内容", self)
        clear_selection_action.triggered.connect(self.clear_selection)
        menu.addAction(clear_selection_action)
        
        menu.exec(self.table.mapToGlobal(position))
        
    def table_mouse_press_event(self, event):
        """表格鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 获取点击位置的索引
            index = self.table.indexAt(event.pos())
            if index.isValid():
                # 保存拖拽起始位置和原始选择
                self.drag_start_pos = index
                self.original_selection = self.get_selected_items()
                
        # 调用原始的鼠标按下事件
        QTableWidget.mousePressEvent(self.table, event)
        
    def table_mouse_move_event(self, event):
        """表格鼠标移动事件"""
        if (event.buttons() & Qt.LeftButton and 
            self.drag_start_pos and 
            self.original_selection):
            
            current_index = self.table.indexAt(event.pos())
            if current_index.isValid() and current_index != self.drag_start_pos:
                # 检查是否是拖拽填充（从选中区域边界开始拖拽）
                if self.is_drag_fill_operation(current_index):
                    self.is_dragging = True
                    self.drag_end_pos = current_index
                    self.highlight_fill_area()
                    self.table.setCursor(QCursor(Qt.PointingHandCursor))
                    return
                    
        # 调用原始的鼠标移动事件
        QTableWidget.mouseMoveEvent(self.table, event)
        
    def table_mouse_release_event(self, event):
        """表格鼠标释放事件"""
        if self.is_dragging and self.drag_end_pos:
            # 执行拖拽填充
            self.perform_drag_fill()
            
        # 重置拖拽状态
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_end_pos = None
        self.original_selection = []
        self.table.setCursor(QCursor(Qt.ArrowCursor))
        
        # 调用原始的鼠标释放事件
        QTableWidget.mouseReleaseEvent(self.table, event)
        
    def is_drag_fill_operation(self, current_index):
        """判断是否是拖拽填充操作"""
        if not self.original_selection:
            return False
            
        # 获取原始选择的边界
        min_row = min(item.row() for item in self.original_selection)
        max_row = max(item.row() for item in self.original_selection)
        min_col = min(item.column() for item in self.original_selection)
        max_col = max(item.column() for item in self.original_selection)
        
        # 检查当前位置是否在选择区域的延伸方向上
        current_row = current_index.row()
        current_col = current_index.column()
        
        # 垂直拖拽填充
        if (min_col <= current_col <= max_col and 
            (current_row > max_row or current_row < min_row)):
            return True
            
        # 水平拖拽填充
        if (min_row <= current_row <= max_row and 
            (current_col > max_col or current_col < min_col)):
            return True
            
        return False
        
    def highlight_fill_area(self):
        """高亮显示填充区域"""
        if not self.original_selection or not self.drag_end_pos:
            return
            
        # 计算填充范围
        fill_range = self.calculate_fill_range()
        
        # 清除当前选择并高亮填充区域
        self.table.clearSelection()
        for row, col in fill_range:
            item = self.table.item(row, col)
            if not item:
                item = QTableWidgetItem("")
                self.table.setItem(row, col, item)
            item.setSelected(True)
            
    def calculate_fill_range(self):
        """计算填充范围"""
        if not self.original_selection or not self.drag_end_pos:
            return []
            
        # 获取原始选择的边界
        min_row = min(item.row() for item in self.original_selection)
        max_row = max(item.row() for item in self.original_selection)
        min_col = min(item.column() for item in self.original_selection)
        max_col = max(item.column() for item in self.original_selection)
        
        current_row = self.drag_end_pos.row()
        current_col = self.drag_end_pos.column()
        
        fill_range = []
        
        # 垂直填充
        if min_col <= current_col <= max_col:
            if current_row > max_row:
                # 向下填充
                for row in range(max_row + 1, current_row + 1):
                    for col in range(min_col, max_col + 1):
                        fill_range.append((row, col))
            elif current_row < min_row:
                # 向上填充
                for row in range(current_row, min_row):
                    for col in range(min_col, max_col + 1):
                        fill_range.append((row, col))
                        
        # 水平填充
        elif min_row <= current_row <= max_row:
            if current_col > max_col:
                # 向右填充
                for col in range(max_col + 1, current_col + 1):
                    for row in range(min_row, max_row + 1):
                        fill_range.append((row, col))
            elif current_col < min_col:
                # 向左填充
                for col in range(current_col, min_col):
                    for row in range(min_row, max_row + 1):
                        fill_range.append((row, col))
                        
        return fill_range
        
    def perform_drag_fill(self):
        """执行拖拽填充"""
        if not self.original_selection:
            return
            
        # 获取源数据
        source_data = self.get_source_data()
        
        # 检测数据模式
        pattern = self.detect_sequence_pattern(source_data)
        
        # 计算填充范围
        fill_range = self.calculate_fill_range()
        
        # 生成填充数据
        fill_data = self.generate_fill_data(source_data, pattern, len(fill_range))
        
        # 填充数据到表格
        for i, (row, col) in enumerate(fill_range):
            if i < len(fill_data):
                # 确保行存在
                while row >= self.table.rowCount():
                    self.table.insertRow(self.table.rowCount())
                    
                item = QTableWidgetItem(str(fill_data[i]))
                self.table.setItem(row, col, item)
                
    def get_source_data(self):
        """获取源数据"""
        if not self.original_selection:
            return []
            
        # 按行列顺序排序选中项
        sorted_selection = sorted(self.original_selection, 
                                key=lambda x: (x.row(), x.column()))
        
        source_data = []
        for item in sorted_selection:
            table_item = self.table.item(item.row(), item.column())
            value = table_item.text() if table_item else ""
            source_data.append(value)
            
        return source_data
        
    def detect_sequence_pattern(self, data):
        """检测序列模式"""
        if len(data) < 1:
            return {'type': 'repeat', 'value': ''}
            
        if len(data) == 1:
            return {'type': 'repeat', 'value': data[0]}
            
        # 尝试检测数字序列
        numeric_pattern = self.detect_numeric_pattern(data)
        if numeric_pattern:
            return numeric_pattern
            
        # 尝试检测日期序列
        date_pattern = self.detect_date_pattern(data)
        if date_pattern:
            return date_pattern
            
        # 尝试检测文本序列
        text_pattern = self.detect_text_pattern(data)
        if text_pattern:
            return text_pattern
            
        # 默认：循环重复
        return {'type': 'cycle', 'values': data}
        
    def detect_numeric_pattern(self, data):
        """检测数字序列模式"""
        try:
            # 过滤空值并转换为数字
            numbers = []
            for item in data:
                if item.strip():
                    numbers.append(float(item.strip()))
                    
            if len(numbers) < 2:
                return None
                
            # 检测等差数列
            diff = numbers[1] - numbers[0]
            is_arithmetic = all(
                abs((numbers[i] - numbers[i-1]) - diff) < 1e-10 
                for i in range(2, len(numbers))
            )
            
            if is_arithmetic:
                return {
                    'type': 'arithmetic',
                    'start': numbers[0],
                    'step': diff,
                    'current_index': len(numbers)
                }
                
            # 检测等比数列
            if numbers[0] != 0:
                ratio = numbers[1] / numbers[0]
                is_geometric = all(
                    abs(numbers[i] / numbers[i-1] - ratio) < 1e-10 
                    for i in range(2, len(numbers))
                    if numbers[i-1] != 0
                )
                
                if is_geometric:
                    return {
                        'type': 'geometric',
                        'start': numbers[0],
                        'ratio': ratio,
                        'current_index': len(numbers)
                    }
                    
        except (ValueError, ZeroDivisionError):
            pass
            
        return None
        
    def detect_date_pattern(self, data):
        """检测日期序列模式"""
        # 常见日期格式
        date_formats = [
            '%Y-%m-%d', '%Y/%m/%d', '%m-%d', '%m/%d',
            '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'
        ]
        
        dates = []
        date_format = None
        
        for item in data:
            if not item.strip():
                continue
                
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(item.strip(), fmt)
                    dates.append(date_obj)
                    if date_format is None:
                        date_format = fmt
                    break
                except ValueError:
                    continue
                    
        if len(dates) >= 2:
            # 计算日期间隔
            delta = dates[1] - dates[0]
            
            # 检查是否是规律的日期序列
            is_regular = all(
                (dates[i] - dates[i-1]) == delta 
                for i in range(2, len(dates))
            )
            
            if is_regular:
                return {
                    'type': 'date',
                    'start': dates[0],
                    'delta': delta,
                    'format': date_format,
                    'current_index': len(dates)
                }
                
        return None
        
    def detect_text_pattern(self, data):
        """检测文本序列模式"""
        # 检测字母序列 (A, B, C...)
        if len(data) >= 2:
            first = data[0].strip().upper()
            second = data[1].strip().upper()
            
            if len(first) == 1 and len(second) == 1 and first.isalpha() and second.isalpha():
                if ord(second) - ord(first) == 1:
                    return {
                        'type': 'alpha',
                        'start': first,
                        'current_index': len(data)
                    }
                    
        # 检测数字后缀模式 (项目1, 项目2, 项目3...)
        pattern = re.compile(r'^(.+?)(\d+)(.*)$')
        matches = []
        
        for item in data:
            match = pattern.match(item.strip())
            if match:
                prefix, number, suffix = match.groups()
                matches.append((prefix, int(number), suffix))
            else:
                matches = []
                break
                
        if len(matches) >= 2:
            prefix, start_num, suffix = matches[0]
            # 检查是否所有项都有相同的前缀和后缀，且数字递增
            if all(m[0] == prefix and m[2] == suffix for m in matches):
                numbers = [m[1] for m in matches]
                if all(numbers[i] - numbers[i-1] == 1 for i in range(1, len(numbers))):
                    return {
                        'type': 'numbered',
                        'prefix': prefix,
                        'suffix': suffix,
                        'start': start_num,
                        'current_index': len(matches)
                    }
                    
        return None
        
    def generate_fill_data(self, source_data, pattern, count):
        """根据模式生成填充数据"""
        if not pattern or count <= 0:
            return []
            
        fill_data = []
        
        if pattern['type'] == 'repeat':
            # 重复最后一个值
            fill_data = [pattern['value']] * count
            
        elif pattern['type'] == 'cycle':
            # 循环重复源数据
            for i in range(count):
                fill_data.append(pattern['values'][i % len(pattern['values'])])
                
        elif pattern['type'] == 'arithmetic':
            # 等差数列
            start_val = pattern['start'] + pattern['step'] * pattern['current_index']
            for i in range(count):
                value = start_val + pattern['step'] * i
                # 如果原数据是整数，保持整数格式
                if pattern['step'] == int(pattern['step']) and pattern['start'] == int(pattern['start']):
                    fill_data.append(str(int(value)))
                else:
                    fill_data.append(str(value))
                    
        elif pattern['type'] == 'geometric':
            # 等比数列
            start_val = pattern['start'] * (pattern['ratio'] ** pattern['current_index'])
            for i in range(count):
                value = start_val * (pattern['ratio'] ** i)
                fill_data.append(str(value))
                
        elif pattern['type'] == 'date':
            # 日期序列
            start_date = pattern['start'] + pattern['delta'] * pattern['current_index']
            for i in range(count):
                date_val = start_date + pattern['delta'] * i
                fill_data.append(date_val.strftime(pattern['format']))
                
        elif pattern['type'] == 'alpha':
            # 字母序列
            start_ord = ord(pattern['start']) + pattern['current_index']
            for i in range(count):
                char_ord = start_ord + i
                if char_ord <= ord('Z'):
                    fill_data.append(chr(char_ord))
                else:
                    fill_data.append(chr(ord('A') + (char_ord - ord('A')) % 26))
                    
        elif pattern['type'] == 'numbered':
            # 数字后缀序列
            start_num = pattern['start'] + pattern['current_index']
            for i in range(count):
                num = start_num + i
                fill_data.append(f"{pattern['prefix']}{num}{pattern['suffix']}")
                
        return fill_data
        
    def get_selected_items(self):
        """获取选中的项目"""
        return [self.table.model().index(item.row(), item.column()) 
                for item in self.table.selectedItems()]
        
    def add_row(self):
        """添加行"""
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        
    def delete_selected(self):
        """删除选中的行/列"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的行或列")
            return
            
        # 获取选中的行和列
        selected_rows = set(item.row() for item in selected_items)
        selected_cols = set(item.column() for item in selected_items)
        
        
        
            # 删除整行（从后往前删除避免索引变化）
        for row in sorted(selected_rows, reverse=True):
                self.table.removeRow(row)
                
    def clear_selection(self):
        """清空选中单元格的内容"""
        selected_items = self.table.selectedItems()
        for item in selected_items:
            item.setText("")
            
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
    
    def set_card_number(self, card_number):
        """设置卡号"""
        self.card_input.setText(card_number or "")
    
    def get_card_number(self):
        """获取卡号"""
        return self.card_input.text().strip()
    
    def clear_card_number(self):
        """清空卡号"""
        self.card_input.clear()