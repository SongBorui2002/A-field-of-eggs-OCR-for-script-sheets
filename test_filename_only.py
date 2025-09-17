#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试只使用文件名匹配的元数据导入功能
"""

import pandas as pd
import os

# 模拟测试数据
test_data = {
    'File Name': ['A_001C001_230101_R01G.mov', 'A_002C001_230101_R01G.mov', 'A_003C001_230101_R01G.mov'],
    'Scene': [1, 1, 2], 
    'Shot': [1, 2, 1],
    'Take': [1, 1, 1]
}

# 创建测试CSV文件
df = pd.DataFrame(test_data)
test_csv_path = 'test_filename_only.csv'
df.to_csv(test_csv_path, index=False)

print("创建了测试CSV文件:")
print(df)
print(f"\n文件保存为: {test_csv_path}")

# 显示CSV内容
print("\nCSV文件内容:")
with open(test_csv_path, 'r', encoding='utf-8') as f:
    print(f.read())

print("\n✓ 测试数据已准备好，可以用于测试只使用文件名匹配的元数据导入功能")
print("  - 移除了Reel Name列")
print("  - 只保留File Name、Scene、Shot、Take列")
print("  - 可以使用修改后的import_metadata_to_resolve.py脚本进行测试") 