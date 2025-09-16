#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import json
import base64
from deepseek_processor import DeepSeekProcessor
from tencent_ocr import TencentOCR
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.ocr.v20181119 import ocr_client, models
from config import AppConfig


class OCRPipeline:
    """OCR处理流程类"""
    
    def __init__(self, tencent_secret_id=None, tencent_secret_key=None):
        """
        初始化OCR处理流程
        :param tencent_secret_id: 腾讯云SecretId，如果为None则从配置文件读取
        :param tencent_secret_key: 腾讯云SecretKey，如果为None则从配置文件读取
        """
        # 如果没有提供API密钥，则从配置文件读取
        if tencent_secret_id is None or tencent_secret_key is None:
            config = AppConfig()
            config_path = config.get_config_path()
            if os.path.exists(config_path):
                config = AppConfig.from_file(config_path)
            
            tencent_secret_id = tencent_secret_id or config.tencent_secret_id
            tencent_secret_key = tencent_secret_key or config.tencent_secret_key
        
        # 保存API密钥作为实例属性
        self.tencent_secret_id = tencent_secret_id
        self.tencent_secret_key = tencent_secret_key
        
        self.tencent_ocr = TencentOCR(tencent_secret_id, tencent_secret_key)
        self.deepseek_processor = DeepSeekProcessor()
    
    def image_to_base64(self, image_path):
        """将图像文件转换为base64编码"""
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def parse_table_data(self, response_json):
        """解析表格OCR结果并转换为结构化数据"""
        data = json.loads(response_json)
        table_detections = data.get('TableDetections', [])
        
        if not table_detections:
            print("未检测到表格")
            return None
        
        # 获取第一个表格的数据
        table = table_detections[0]
        cells = table.get('Cells', [])
        
        if not cells:
            print("表格中没有检测到单元格")
            return None
        
        # 找出表格的最大行数和列数
        max_row = max(cell['RowBr'] for cell in cells)
        max_col = max(cell['ColBr'] for cell in cells)
        
        # 创建表格矩阵
        table_matrix = [['' for _ in range(max_col)] for _ in range(max_row)]
        
        # 填充表格数据
        for cell in cells:
            row_start = cell['RowTl']
            col_start = cell['ColTl']
            text = cell['Text']
            
            # 对于跨单元格，只在起始位置填充文本
            if row_start < len(table_matrix) and col_start < len(table_matrix[0]):
                table_matrix[row_start][col_start] = text
        
        # 删除所有列都为空的行
        filtered_matrix = []
        for row in table_matrix:
            # 检查当前行是否所有列都为空（空字符串或只包含空白字符）
            has_content = any(str(cell).strip() for cell in row)
            if has_content:
                filtered_matrix.append(row)
        
        return filtered_matrix

    def table_matrix_to_structured_data(self, table_matrix):
        """将二维数组转换为结构化的表格数据，适合DeepSeek处理"""
        if not table_matrix or len(table_matrix) == 0:
            return None
        
        # 构建结构化数据
        structured_data = {
            "table_type": "slate_record",
            "table_dimensions": {
                "rows": len(table_matrix),
                "columns": len(table_matrix[0]) if table_matrix else 0
            },
            "header_row": table_matrix[0] if table_matrix else [],
            "data_rows": table_matrix[1:] if len(table_matrix) > 1 else [],
            "raw_matrix": table_matrix,
            "column_mapping": {}
        }
        
        # 尝试识别列名映射（基于常见的场记单列名）
        if table_matrix and len(table_matrix[0]) > 0:
            header = table_matrix[0]
            column_names = ["场号", "镜号", "次数", "景别", "时码", "视效", "成绩"]
            
            for i, cell in enumerate(header):
                cell_text = str(cell).strip()
                # 尝试匹配标准列名
                for col_name in column_names:
                    if col_name in cell_text or cell_text in col_name:
                        structured_data["column_mapping"][i] = col_name
                        break
                
                # 如果没有匹配到，使用原始文本
                if i not in structured_data["column_mapping"]:
                    structured_data["column_mapping"][i] = cell_text if cell_text else f"列{i+1}"
        
        return structured_data

    def parse_deepseek_json_result(self, result_content):
        """
        解析DeepSeek返回的JSON结果
        :param result_content: DeepSeek API返回的内容
        :return: 解析后的JSON对象，如果解析失败返回None
        """
        try:
            # 尝试直接解析JSON
            json_result = json.loads(result_content)
            return json_result
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            try:
                # 查找JSON开始和结束标记
                start_idx = result_content.find('{')
                end_idx = result_content.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = result_content[start_idx:end_idx+1]
                    json_result = json.loads(json_str)
                    return json_result
            except json.JSONDecodeError:
                pass
        
        print("✗ 无法解析DeepSeek返回的JSON结果")
        print(f"原始内容: {result_content[:500]}...")
        return None

    def format_json_result_for_display(self, json_result):
        """
        将JSON结果格式化为易读的显示格式
        :param json_result: 解析后的JSON结果
        :return: 格式化的字符串
        """
        if not json_result or 'rows' not in json_result:
            return "无效的JSON结果"
        
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append("处理后的场记表数据 (JSON格式)")
        output_lines.append("=" * 80)
        
        # 显示表头
        if 'headers' in json_result:
            headers = json_result['headers']
            header_line = " | ".join(f"{header:^10}" for header in headers)
            output_lines.append(header_line)
            output_lines.append("-" * len(header_line))
        
        # 显示数据行
        rows = json_result['rows']
        for i, row in enumerate(rows):
            if isinstance(row, dict):
                # 新的JSON格式
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
                # 如果是数组格式
                row_data = row
            
            row_line = " | ".join(f"{str(cell):^10}" for cell in row_data)
            output_lines.append(f"{i+1:2d}: {row_line}")
        
        output_lines.append("=" * 80)
        output_lines.append(f"总计: {len(rows)} 行数据")
        
        return "\n".join(output_lines)

    def process(self, image_path, deepseek_api_key, scene_numbers=None):
        """
        完整的OCR处理流程
        1. 使用腾讯云表格OCR识别图像
        2. 将结果转换为二维数组
        3. 使用DeepSeek处理器处理结果
        
        :param image_path: 图像文件路径
        :param deepseek_api_key: DeepSeek API密钥
        :param scene_numbers: 允许的场号列表，如 ["212b", "275", "27b", "210c", "28"]
        :return: 最终处理结果
        """
        
        print("=" * 80)
        print("开始OCR处理流程 (使用腾讯云表格OCR)")
        print("=" * 80)
        
        # 步骤1: 检查图像文件是否存在
        if not os.path.exists(image_path):
            print(f"错误: 图像文件不存在: {image_path}")
            return None
        
        print(f"✓ 图像文件: {image_path}")
        
        # 显示场号配置
        if scene_numbers:
            print(f"✓ 场号配置: {', '.join(scene_numbers)}")
        else:
            print("✓ 场号配置: 使用默认场号")
        
        # 步骤2: 调用腾讯云表格OCR
        print("\n步骤1: 调用腾讯云表格OCR识别...")
        try:
            # 腾讯云认证
            cred = credential.Credential(self.tencent_secret_id, self.tencent_secret_key)
            
            # 实例化HTTP选项
            httpProfile = HttpProfile()
            httpProfile.endpoint = "ocr.tencentcloudapi.com"

            # 实例化client选项
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            
            # 实例化OCR客户端
            client = ocr_client.OcrClient(cred, "", clientProfile)
            
            # 将图像转换为base64编码
            image_base64 = self.image_to_base64(image_path)

            # 实例化请求对象
            req = models.RecognizeTableAccurateOCRRequest()
            params = {
                "ImageBase64": image_base64
            }
            req.from_json_string(json.dumps(params))

            print("正在调用腾讯云表格OCR API...")
            # 调用API
            resp = client.RecognizeTableAccurateOCR(req)
            
            # 获取响应的JSON字符串
            response_json = resp.to_json_string()
            
            print(f"✓ 腾讯云OCR API调用成功")
            print(f"📄 OCR原始响应内容:\n{response_json}")
            
            # 解析表格数据为二维数组
            table_matrix = self.parse_table_data(response_json)
            
            if table_matrix:
                print(f"✓ 表格OCR识别成功，识别到 {len(table_matrix)} 行 × {len(table_matrix[0]) if table_matrix else 0} 列的表格")
                
                # 打印完整表格
                print("\n完整表格:")
                for i, row in enumerate(table_matrix):  # 显示所有行
                    row_str = " | ".join(f"{str(cell):^10}" for cell in row)
                    print(f"  第{i+1}行: {row_str}")
            else:
                print("✗ 表格OCR识别失败，未能解析出表格数据")
                return None
                
        except TencentCloudSDKException as err:
            print(f"✗ 腾讯云OCR识别失败: {err}")
            print(f"🔍 错误类型: {type(err).__name__}")
            print(f"🔍 错误代码: {getattr(err, 'code', 'N/A')}")
            print(f"🔍 错误消息: {getattr(err, 'message', str(err))}")
            return None
        except Exception as e:
            print(f"✗ OCR识别过程出错: {e}")
            print(f"🔍 错误类型: {type(e).__name__}")
            import traceback
            print(f"🔍 完整错误堆栈:\n{traceback.format_exc()}")
            return None
        
        # 步骤3: 将二维数组转换为结构化数据
        print("\n步骤2: 转换表格数据为结构化格式...")
        try:
            structured_data = self.table_matrix_to_structured_data(table_matrix)
            
            if structured_data:
                print("✓ 表格数据结构化成功")
                print(f"  - 表格尺寸: {structured_data['table_dimensions']['rows']} 行 × {structured_data['table_dimensions']['columns']} 列")
                print(f"  - 列映射: {structured_data['column_mapping']}")
            else:
                print("✗ 表格数据结构化失败")
                return None
                
        except Exception as e:
            print(f"✗ 表格数据结构化过程出错: {e}")
            return None
        
        # 步骤4: 使用DeepSeek处理器处理结构化数据
        print("\n步骤3: 使用DeepSeek处理器处理表格数据...")
        try:
            # 将结构化数据转换为JSON字符串
            structured_json_str = json.dumps(structured_data, ensure_ascii=False, indent=2)
            print(f"结构化数据长度: {len(structured_json_str)} 字符")
            
            # 调用DeepSeek处理器
            processed_result = self.deepseek_processor.process_slate_data(structured_json_str, deepseek_api_key, scene_numbers)
            
            if processed_result:
                print("✓ DeepSeek处理成功")
                # 直接返回原始的DeepSeek JSON响应
                return {
                    "status": "success",
                    "raw_result": processed_result
                }
            else:
                print("✗ DeepSeek处理失败")
                return None
                
        except Exception as e:
            print(f"✗ DeepSeek处理过程出错: {e}")
            return None


def ocr_pipeline(image_path, deepseek_api_key, scene_numbers=None):
    """
    向后兼容的函数接口
    """
    pipeline = OCRPipeline()
    return pipeline.process(image_path, deepseek_api_key, scene_numbers)


def main():
    """
    主函数，处理命令行参数
    """
    parser = argparse.ArgumentParser(
        description="OCR场记表处理流程 - 将图像通过腾讯云表格OCR识别后用DeepSeek处理器生成规范表格",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python3 ocr_pipeline.py /path/to/image.jpg
  python3 ocr_pipeline.py /Users/sbr/Desktop/3.png
  python3 ocr_pipeline.py image.png --api-key your-deepseek-api-key
  python3 ocr_pipeline.py image.png --scene-numbers 218,R39,24a
        """
    )
    
    parser.add_argument(
        'image_path',
        help='要处理的图像文件路径'
    )
    
    parser.add_argument(
        '--api-key',
        help='DeepSeek API密钥 (如果不提供则从配置文件读取)'
    )
    
    parser.add_argument(
        '--scene-numbers',
        help='允许的场号列表，用逗号分隔 (如: 218,R39,24a,275,28)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细处理信息'
    )
    
    args = parser.parse_args()
    
    # 处理API密钥
    api_key = args.api_key
    if not api_key:
        config = AppConfig()
        config_path = config.get_config_path()
        if os.path.exists(config_path):
            config = AppConfig.from_file(config_path)
        api_key = config.deepseek_api_key
    
    # 处理场号参数
    scene_numbers = None
    if args.scene_numbers:
        scene_numbers = [s.strip() for s in args.scene_numbers.split(',')]
    
    # 显示参数信息
    if args.verbose:
        print(f"图像路径: {args.image_path}")
        print(f"API密钥: {api_key[:20] if api_key else 'None'}...")
        if scene_numbers:
            print(f"场号配置: {', '.join(scene_numbers)}")
        else:
            print("场号配置: 使用默认场号")
        print()
    
    # 执行处理流程
    pipeline = OCRPipeline()
    result = pipeline.process(args.image_path, api_key, scene_numbers)
    
    if result:
        print("\n" + "=" * 80)
        print("最终处理结果:")
        print("=" * 80)
        
        if isinstance(result, dict):
            if result.get("status") == "success":
                # 直接显示DeepSeek返回的原始JSON
                print(result["raw_result"])
            else:
                print("处理状态未知:")
                print(result)
        else:
            # 向后兼容旧格式
            print(result)
            
        print("\n" + "=" * 80)
        print("处理完成!")
    else:
        print("\n" + "=" * 80)
        print("处理失败，请检查错误信息")
        sys.exit(1)

if __name__ == "__main__":
    main() 