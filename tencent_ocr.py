# -*- coding: utf-8 -*-

import os
import json
import base64
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.ocr.v20181119 import ocr_client, models

def image_to_base64(image_path):
    """将图像文件转换为base64编码"""
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def parse_table_data(response_json):
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
        row_end = cell['RowBr']
        col_end = cell['ColBr']
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

def print_table(table_matrix):
    """打印格式化的表格"""
    if not table_matrix:
        return
    
    print("\n识别到的场记单表格内容:")
    print("=" * 120)
    
    for i, row in enumerate(table_matrix):
        # 动态调整列宽，确保中文字符正确显示
        row_str = " | ".join(f"{str(cell):^15}" for cell in row)
        print(f"第{i+1:2d}行: {row_str}")
        if i == 0:  # 在表头后添加分隔线
            print("-" * 120)
    
    print("=" * 120)
    print(f"表格尺寸: {len(table_matrix)} 行 × {len(table_matrix[0]) if table_matrix else 0} 列")

try:
    # 实例化一个认证对象，入参需要传入腾讯云账户 SecretId 和 SecretKey，此处还需注意密钥对的保密
    # 代码泄露可能会导致 SecretId 和 SecretKey 泄露，并威胁账号下所有资源的安全性
    # 以下代码示例仅供参考，建议采用更安全的方式来使用密钥
    # 请参见：https://cloud.tencent.com/document/product/1278/85305
    # 密钥可前往官网控制台 https://console.cloud.tencent.com/cam/capi 进行获取
    cred = credential.Credential("AKIDWs21iNq7A1g7Vpy8B2iBXktvpkX8bv2w", "qVxCE3f4GH6h5GdwFlN1a2LWWJtGPL3a")
    # 使用临时密钥示例
    # cred = credential.Credential("SecretId", "SecretKey", "Token")
    
    # 实例化一个http选项，可选的，没有特殊需求可以跳过
    httpProfile = HttpProfile()
    httpProfile.endpoint = "ocr.tencentcloudapi.com"

    # 实例化一个client选项，可选的，没有特殊需求可以跳过
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    
    # 实例化要请求产品的client对象,clientProfile是可选的
    client = ocr_client.OcrClient(cred, "", clientProfile)

    # 指定要处理的图像路径
    image_path = '/Volumes/1/场记单/WS3 SSR-D10场记单 20240501_processed/WS3 SSR-D10场记单 20240501_page_001_processed.jpg'
    
    # 将图像转换为base64编码
    image_base64 = image_to_base64(image_path)

    # 实例化一个请求对象,每个接口都会对应一个request对象
    req = models.RecognizeTableAccurateOCRRequest()
    params = {
        "ImageBase64": image_base64
    }
    req.from_json_string(json.dumps(params))

    # 返回的resp是一个RecognizeTableAccurateOCRResponse的实例，与请求对象对应
    resp = client.RecognizeTableAccurateOCR(req)
    
    # 获取响应的JSON字符串
    response_json = resp.to_json_string()
    
    # 解析表格数据
    table_matrix = parse_table_data(response_json)
    
    # 打印格式化的表格
    print_table(table_matrix)
    
    # 打印二维数组结构
    if table_matrix:
        print("\n二维数组结构:")
        print("table_matrix = [")
        for i, row in enumerate(table_matrix):
            print(f"    {row}{',' if i < len(table_matrix)-1 else ''}")
        print("]")
    
    # 如果需要查看原始JSON数据，取消下面的注释
    # print("\n原始JSON响应:")
    # print(response_json)

except TencentCloudSDKException as err:
    print(err)
except FileNotFoundError:
    print(f"图像文件未找到: {image_path}")
except Exception as err:
    print(f"发生错误: {err}") 