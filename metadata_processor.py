#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import os
import re
import json
from typing import List, Dict, Any

class MetadataProcessor:
    """元数据处理器 - 专门处理CSV元数据更新"""
    
    def __init__(self):
        self.csv_encoding = 'utf-8'  # 默认编码
    
    def detect_csv_encoding(self, csv_path: str) -> str:
        """检测CSV文件编码"""
        try:
            import chardet
        except ImportError:
            print("警告: 未安装chardet库，使用默认编码utf-8")
            return 'utf-8'
        
        try:
            with open(csv_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result.get('encoding', 'utf-8')
                
            # 常见编码映射
            encoding_map = {
                'GB2312': 'gbk',
                'GBK': 'gbk', 
                'UTF-16': 'utf-16',
                'UTF-8': 'utf-8'
            }
            
            return encoding_map.get(encoding, encoding)
        except:
            return 'utf-8'
    
    def format_card_number(self, card_number: str) -> str:
        """格式化卡号：A025 -> A_0025"""
        if not card_number:
            return ""
        
        # 在首个字符后添加_0
        formatted = card_number.upper()
        if len(formatted) > 0:
            formatted = formatted[0] + '_0' + formatted[1:]
        
        return formatted
    
    def build_reel_key(self, card_number: str, timecode: str) -> str:
        """构建Reel Name匹配键：A_0025C003（前10个字符）"""
        formatted_card = self.format_card_number(card_number)
        # 确保时码格式正确（如C003）
        clean_timecode = timecode.strip().upper()
        reel_key = f"{formatted_card}{clean_timecode}"
        
        # 只返回前10个字符用于匹配
        return reel_key[:10]
    
    def load_metadata_csv(self, csv_path: str) -> pd.DataFrame:
        """加载元数据CSV文件"""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV文件不存在: {csv_path}")
        
        # 检测编码
        encoding = self.detect_csv_encoding(csv_path)
        self.csv_encoding = encoding
        
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"✓ 成功加载CSV文件，编码: {encoding}")
            print(f"✓ CSV尺寸: {df.shape[0]} 行 × {df.shape[1]} 列")
            
            # 自动填充Camera #列
            self.populate_camera_numbers(df)
            
            return df
        except Exception as e:
            # 尝试其他编码
            for fallback_encoding in ['utf-8', 'gbk', 'utf-16']:
                if fallback_encoding != encoding:
                    try:
                        df = pd.read_csv(csv_path, encoding=fallback_encoding)
                        self.csv_encoding = fallback_encoding
                        print(f"✓ 使用备用编码加载CSV: {fallback_encoding}")
                        
                        # 自动填充Camera #列
                        self.populate_camera_numbers(df)
                        
                        return df
                    except:
                        continue
            
            raise Exception(f"无法读取CSV文件: {e}")
    
    def populate_camera_numbers(self, df: pd.DataFrame):
        """从File Name列提取Camera #信息填充到所有行"""
        print("开始处理Camera #信息...")
        
        if 'File Name' not in df.columns:
            print("警告: CSV中没有'File Name'列，无法提取Camera #")
            return
        
        if 'Camera #' not in df.columns:
            df['Camera #'] = ''
            print("✓ 创建了'Camera #'列")
        
        # 遍历所有行，为每一行填充Camera #
        camera_count = 0
        empty_filename_count = 0
        
        print(f"正在处理 {len(df)} 行数据...")
        
        for idx in df.index:
            file_name = df.loc[idx, 'File Name']
            
            if pd.notna(file_name) and str(file_name).strip():
                # 提取文件名的第一个字符作为Camera #
                camera_letter = str(file_name).strip()[0].upper()
                df.loc[idx, 'Camera #'] = camera_letter
                camera_count += 1
                
                # 每100行显示一次进度
                if camera_count % 100 == 0:
                    print(f"已处理 {camera_count} 行...")
            else:
                # 文件名为空的情况
                df.loc[idx, 'Camera #'] = ''
                empty_filename_count += 1
        
        print(f"✓ Camera #处理完成:")
        print(f"  - 成功填充: {camera_count} 行")
        print(f"  - 文件名为空: {empty_filename_count} 行")
        print(f"  - 总计: {len(df)} 行")
        
        # 显示Camera #统计
        if camera_count > 0:
            camera_stats = df['Camera #'].value_counts()
            print(f"✓ Camera #统计分布: {dict(camera_stats)}")
        
        print("Camera #信息处理完成！\n")
    
    def extract_records_from_ocr(self, ocr_result: Dict[str, Any], card_number: str = "") -> List[Dict[str, str]]:
        """从OCR结果中提取记录"""
        records = []
        
        if not ocr_result or ocr_result.get('status') != 'success':
            return records
        
        # 支持两种键名：'result' 和 'raw_result'
        raw_result = ocr_result.get('result') or ocr_result.get('raw_result', '{}')
        try:
            # 解析DeepSeek返回的JSON
            if isinstance(raw_result, str):
                data = json.loads(raw_result)
            else:
                data = raw_result
            
            # 提取rows数据
            rows = data.get('rows', [])
            for row in rows:
                if isinstance(row, dict):
                    # 新格式：字典形式
                    scene = row.get('scene', '').strip()
                    shot = row.get('shot', '').strip()
                    take = row.get('take', '').strip()
                    
                    if scene and shot and take:  # 只处理有效记录
                        records.append({
                            'scene': scene,
                            'shot': shot,
                            'take': take,
                            'framing': row.get('framing', ''),
                            'timecode': row.get('timecode', ''),
                            'vfx': row.get('vfx', ''),
                            'result': row.get('result', ''),
                            'card_number': card_number
                        })
                elif isinstance(row, list) and len(row) >= 7:
                    # 旧格式：数组形式
                    scene = str(row[0]).strip() if len(row) > 0 else ''
                    shot = str(row[1]).strip() if len(row) > 1 else ''
                    take = str(row[2]).strip() if len(row) > 2 else ''
                    
                    if scene and shot and take:  # 只处理有效记录
                        records.append({
                            'scene': scene,
                            'shot': shot,
                            'take': take,
                            'framing': str(row[3]) if len(row) > 3 else '',
                            'timecode': str(row[4]) if len(row) > 4 else '',
                            'vfx': str(row[5]) if len(row) > 5 else '',
                            'result': str(row[6]) if len(row) > 6 else '',
                            'card_number': card_number
                        })
        
        except (json.JSONDecodeError, KeyError) as e:
            print(f"解析OCR结果失败: {e}")
        
        return records
    
    def match_and_update(self, df: pd.DataFrame, all_records: List[Dict[str, str]]) -> Dict[str, Any]:
        """匹配並更新元数据"""
        # 检查必要的列是否存在
        required_columns = ['Reel Name', 'Scene', 'Shot', 'Take']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise Exception(f"CSV缺少必要列: {missing_columns}")
        
        # 确保Scene、Shot、Take列为字符串类型，避免pandas类型不兼容警告
        for col in ['Scene', 'Shot', 'Take']:
            if col in df.columns:
                df[col] = df[col].astype('object')
        
        # 确保Comments列存在
        if 'Comments' not in df.columns:
            df['Comments'] = ''
            print("✓ 创建了'Comments'列")
        
        # 确保Good Take列存在
        if 'Good Take' not in df.columns:
            df['Good Take'] = ''
            print("✓ 创建了'Good Take'列")
        
        # 统计信息
        matched_count = 0
        unmatched_records = []
        error_records = []
        
        print(f"开始匹配 {len(all_records)} 条场记记录到CSV中...")
        
        # 遍历所有场记单数据
        for i, record in enumerate(all_records):
            try:
                # print(f"\n处理记录 {i+1}: {record}")
                
                # 检查记录中的必要字段
                if 'card_number' not in record or 'timecode' not in record:
                    raise KeyError(f"记录缺少必要字段: {list(record.keys())}")
                
                # 构建匹配键
                card_number = record['card_number']
                timecode = record['timecode']
                reel_key = self.build_reel_key(card_number, timecode)
                
                # print(f"卡号: {card_number}, 时码: {timecode}")
                # print(f"构建的Reel Key: {reel_key} (长度: {len(reel_key)})")
                
                if len(reel_key) < 10:
                    error_msg = f"匹配键长度不足: {reel_key} (需要10个字符)"
                    print(f"✗ {error_msg}")
                    error_records.append({
                        'record': record,
                        'error': error_msg
                    })
                    continue
                
                # 在CSV中查找匹配的Reel Name（前10个字符）
                mask = df['Reel Name'].str[:10] == reel_key
                matching_rows = df[mask]
                
                # print(f"匹配结果: 找到 {len(matching_rows)} 行")
                
                if len(matching_rows) > 0:
                    # 显示匹配的Reel Name
                    matched_reel_names = matching_rows['Reel Name'].tolist()
                    # print(f"匹配的Reel Names: {matched_reel_names}")
                    
                    # 找到匹配，更新场记信息字段
                    scene = record.get('scene', '')
                    shot = record.get('shot', '')
                    take = record.get('take', '')
                    
                    # 處理視效和成績
                    vfx = record.get('vfx', '').strip()
                    result = record.get('result', '').strip()
                    
                    # 构建Comments内容：视效_成绩
                    comments_parts = []
                    if vfx:
                        comments_parts.append(vfx)
                    if result:
                        comments_parts.append(result)
                    
                    comments_content = '_'.join(comments_parts) if comments_parts else ''
                    
                    # 處理Good Take欄位：如果成績為OK，則設為1
                    good_take_value = ''
                    if result.upper() == 'OK':
                        good_take_value = '1'
                    
                    df.loc[mask, 'Scene'] = scene
                    df.loc[mask, 'Shot'] = shot  
                    df.loc[mask, 'Take'] = take
                    df.loc[mask, 'Comments'] = comments_content
                    df.loc[mask, 'Good Take'] = good_take_value
                    matched_count += len(matching_rows)
                    
                    # 获取第一个匹配行的Camera #用于日志显示（Camera #已在加载时填充）
                    # first_camera_letter = df.loc[matching_rows.index[0], 'Camera #'] if 'Camera #' in df.columns else ''
                    # print(f"✓ 场记匹配成功: {reel_key} -> Scene:{scene}, Shot:{shot}, Take:{take}, Comments:{comments_content} (Camera #:{first_camera_letter})")
                else:
                    print(f"✗ 未找到匹配: {reel_key}")
                    
                    # 显示CSV中前10个字符的样例用于调试
                    sample_reel_names = df['Reel Name'].str[:10].head(5).tolist()
                    print(f"CSV中Reel Name前10字符样例: {sample_reel_names}")
                    
                    unmatched_records.append({
                        'reel_key': reel_key,
                        'record': record
                    })
                    
            except Exception as e:
                error_msg = f"处理记录时出错: {str(e)}"
                print(f"✗ {error_msg}")
                error_records.append({
                    'record': record,
                    'error': error_msg
                })
        
        print(f"\n场记匹配统计: 成功={matched_count}, 未匹配={len(unmatched_records)}, 错误={len(error_records)}")
        
        return {
            'matched_count': matched_count,
            'unmatched_count': len(unmatched_records),
            'error_count': len(error_records),
            'unmatched_records': unmatched_records,
            'error_records': error_records,
            'updated_df': df
        }
    
    def save_updated_csv(self, df: pd.DataFrame, original_path: str) -> str:
        """保存更新后的CSV文件"""
        # 生成输出文件名
        base_path = os.path.splitext(original_path)[0]
        output_path = f"{base_path}_updated.csv"
        
        try:
            # 使用原始编码保存
            df.to_csv(output_path, index=False, encoding=self.csv_encoding)
            print(f"✓ 保存更新后的CSV: {output_path}")
            return output_path
        except Exception as e:
            raise Exception(f"保存CSV文件失败: {e}")
    
    def process_metadata_update(self, csv_path: str, all_records: List[Dict[str, str]]) -> Dict[str, Any]:
        """完整的元数据更新流程"""
        try:
            print("=" * 60)
            print("开始元数据更新流程")
            print("=" * 60)
            print(f"CSV文件路径: {csv_path}")
            print(f"输入记录数: {len(all_records)}")
            
            # 调试：打印输入记录
            if all_records:
                print(f"第一条记录示例: {all_records[0]}")
            else:
                print("警告: 没有输入记录!")
                return {
                    'status': 'error',
                    'message': '没有可处理的记录',
                    'matched_count': 0,
                    'unmatched_count': 0,
                    'error_count': 1
                }
            
            # 步骤1: 加载CSV并处理Camera #
            print("步骤1: 加载元数据CSV并处理Camera #信息...")
            df = self.load_metadata_csv(csv_path)
            
            # 调试：打印CSV列名
            print(f"CSV列名: {list(df.columns)}")
            if 'Reel Name' in df.columns:
                print(f"Reel Name列前5个值: {df['Reel Name'].head().tolist()}")
            else:
                print("错误: CSV文件中没有'Reel Name'列!")
                return {
                    'status': 'error',
                    'message': "CSV文件中没有'Reel Name'列",
                    'matched_count': 0,
                    'unmatched_count': 0,
                    'error_count': 1
                }
            
            # 验证Camera #是否已正确填充
            if 'Camera #' in df.columns:
                filled_camera_count = df['Camera #'].notna().sum()
                print(f"✓ Camera #列状态: {filled_camera_count}/{len(df)} 行已填充")
            
            # 步骤2: 匹配场记信息并更新
            print("步骤2: 匹配场记信息并更新相关字段...")
            result = self.match_and_update(df, all_records)
            
            # # 3. 显示统计信息和详细错误
            # print(f"\n处理结果:")
            # print(f"✓ 成功匹配更新: {result['matched_count']} 条记录")
            # print(f"⚠ 未找到匹配: {result['unmatched_count']} 条记录") 
            # print(f"❌ 处理错误: {result['error_count']} 条记录")
            
            # # 显示详细错误信息
            # if result.get('error_records'):
            #     print("\n错误详情:")
            #     for i, error_rec in enumerate(result['error_records'][:3]):  # 只显示前3个错误
            #         print(f"  错误{i+1}: {error_rec['error']}")
            #         print(f"  记录: {error_rec['record']}")
            
            # # 显示未匹配记录
            # if result.get('unmatched_records'):
            #     print("\n未匹配记录:")
            #     for i, unmatched in enumerate(result['unmatched_records'][:3]):  # 只显示前3个
            #         print(f"  未匹配{i+1}: Reel Key={unmatched['reel_key']}")
            #         print(f"  记录: {unmatched['record']}")
            
            # 4. 保存文件
            if result['matched_count'] > 0:
                print("\n步骤3: 保存更新后的文件...")
                output_path = self.save_updated_csv(result['updated_df'], csv_path)
                result['output_path'] = output_path
            else:
                print("\n跳过保存: 没有匹配的记录")
                
            result['status'] = 'success'
            
            print("=" * 60)
            print("元数据更新完成!")
            print("=" * 60)
            
            return result
            
        except Exception as e:
            import traceback
            error_msg = f"处理过程中发生错误: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {
                'status': 'error',
                'message': str(e),
                'matched_count': 0,
                'unmatched_count': 0,
                'error_count': 1
            } 