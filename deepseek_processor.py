import os
import sys
import locale

# 设置环境变量确保UTF-8编码
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LANG'] = 'zh_CN.UTF-8'
os.environ['LC_ALL'] = 'zh_CN.UTF-8'

# 设置默认编码
if sys.version_info[0] == 3:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from openai import OpenAI
import json
import logging
from datetime import datetime


class DeepSeekProcessor:
    """DeepSeek API处理器类"""
    
    def __init__(self, base_url="https://api.deepseek.com"):
        """
        初始化DeepSeek处理器
        :param base_url: DeepSeek API基础URL
        """
        self.base_url = base_url
    
    def process_slate_data(self, json_data, api_key, scene_numbers=None):
        """
        使用 DeepSeek API 处理场记表数据
        :param json_data: OCR识别出的JSON数据
        :param api_key: DeepSeek API密钥
        :param scene_numbers: 允许的场号列表，如 ["212b", "275", "27b", "210c", "28"]
        :return: 处理后的结果
        """
        
        # 默认场号列表
        if scene_numbers is None:
            scene_numbers = []
        
        # 将场号列表转换为字符串，用于提示词
        scene_numbers_str = "、".join(scene_numbers)
        
        # 设置日志
        # 清除现有的处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('deepseek_api.log', encoding='utf-8', mode='a'),
                logging.StreamHandler()
            ],
            force=True
        )
        
        client = OpenAI(api_key=api_key, base_url=self.base_url)
        
        # 构建提示词
        system_prompt = f"""你是一个影视后期数据管理专家。你将收到一个结构化的表格数据，这是通过腾讯云表格OCR识别场记单后生成的。请根据这个结构化数据，修复并生成一个规范的JSON结果。

输入数据格式说明：
- table_type: 表格类型（通常是"slate_record"）
- table_dimensions: 表格尺寸信息
- header_row: 表头行数据（数组格式）
- data_rows: 数据行列表（二维数组格式）
- raw_matrix: 完整的二维数组
- column_mapping: 列索引到列名的映射

请严格遵循以下规则处理数据：

一、 数据继承规则 (用于修复空白字段)

场号 (Scene): 场号只会从{scene_numbers_str}中出现,若出现了其他字符，请判断数据与应出现的场号的相似度，并给出最可能的场号，如果相似度都很低，则删除该场号并置为空白；若某行的场号识别为空白，则其值继承自上方最近一个非空场号；若上方没有任何场号，则不做继承。

镜号 (Shot): 镜号一定为数字,请判断数据与数字的相似度，得出一个数字镜号；若某行的镜号识别为空白，则其值继承自上方最近一个非空镜号。

次数 (Take): 次数是独立计数器。每个新镜号的出现，都意味着次数从1开始重新递增。在同一镜号内，次数数字应逐行+1。

二、 时码/卷号 (Timecode/Reel) 修复规则 (最关键部分)
时码列通常为字母C + 三位数字的格式（如 C001）。请按顺序应用以下规则进行清洗和修正：

格式标准化： 将所有字符转换为大写，并移除任何空格、换行符等无效字符。

字母修正：
- 将容易混淆的字母 O, o 修正为数字 0。
- 将容易混淆的字母 I, i, L, l 修正为数字 1。
- 将常见的错误字母 G 修正为 C。
- 将 X（通常代表无法识别）视为缺失，需要根据上下文推算。

数字提取与补全：
- 从字符串中提取所有连续的数字。
- 如果数字位数不足三位，则在数字前用0补全（如提取出 "7" -> "007"； "28" -> "028"）。
- 如果数字位数超过三位，则优先保留最后三位数字（如 "1007" -> "007"； "1234" -> "234"）。这是一种常见OCR错误，可能误读了字体或笔画。

前缀确认： 将处理后的数字与字母 C 组合，形成最终的 C001 格式。

连续性检查 (辅助判断)： 处理后的时码在表中应大致保持自上而下递增的趋势，如果有空则顺延上一个非空时码。如果某行时码突然远小于上一行（如从 C020 跳到 C005），这很可能意味着第3步中的数字提取有误，应回到原始识别结果重新检查。但此规则仅用于辅助警示，最终以原始数字的修正为准。

三、 其他列处理

景别 (Framing)、视效 (VFX)、成绩 (OK/NG): 这些列通常为中文或简单符号（如 √, ×, 0）。直接保留OCR识别结果，仅做简单的字符标准化（如将 √ 和 × 的统一）即可。

四、 输出要求

请严格按照以下JSON格式输出，不要包含任何其他内容：

{{
  "headers": ["场号", "镜号", "次数", "景别", "时码", "视效", "成绩"],
  "rows": [
    {{
      "scene": "场号值",
      "shot": "镜号值", 
      "take": "次数值",
      "framing": "景别值",
      "timecode": "时码值",
      "vfx": "视效值",
      "result": "成绩值"
    }}
  ]
}}

注意：输入数据是结构化的表格格式，包含表头和数据行的明确分离，请充分利用这个结构信息来提高处理准确性。只输出JSON，不要包含任何解释或Markdown内容。"""
        
        # 确保字符串编码正确
        try:
            if isinstance(json_data, bytes):
                json_data = json_data.decode('utf-8')
            elif not isinstance(json_data, str):
                json_data = str(json_data)
            
            user_prompt = "请处理以下数据：" + json_data
            
            # 构建请求体
            request_body = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False
            }
            
        except UnicodeDecodeError as e:
            error_msg = f"字符编码错误: {str(e)}"
            logging.error(error_msg)
            print(error_msg)
            return None
        
        # 记录请求信息
        logging.info("=" * 80)
        logging.info(f"开始调用 DeepSeek API - {datetime.now()}")
        logging.info("请求体 (Request Body):")
        
        # 为了避免编码问题，截断过长的内容
        request_body_str = json.dumps(request_body, ensure_ascii=False, indent=2)
        if len(request_body_str) > 2000:  # 如果请求体太长，截断显示
            truncated_body = {
                "model": request_body["model"],
                "messages": [
                    {"role": "system", "content": request_body["messages"][0]["content"][:200] + "..."},
                    {"role": "user", "content": f"数据长度: {len(request_body['messages'][1]['content'])} 字符"}
                ],
                "stream": request_body["stream"]
            }
            logging.info(json.dumps(truncated_body, ensure_ascii=False, indent=2))
        else:
            logging.info(request_body_str)
        logging.info("=" * 80)
        
        # 打印请求体到控制台（简化版本）
        print("\n" + "=" * 80)
        print("请求体 (Request Body) - 简化显示:")
        print(f"模型: {request_body['model']}")
        print(f"消息数量: {len(request_body['messages'])}")
        print(f"用户数据长度: {len(request_body['messages'][1]['content'])} 字符")
        print("=" * 80 + "\n")
        
        try:
            print("正在调用 DeepSeek API...")
            
            # 直接调用API，不进行额外的编码处理
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False
            )
            
            print("API 调用成功!")
            response_content = response.choices[0].message.content
            print(f"响应内容长度: {len(response_content)} 字符")
            
            # 记录API调用结果和原始响应
            try:
                logging.info("API 调用成功")
                logging.info(f"响应内容长度: {len(response_content)} 字符")
                logging.info("DeepSeek原始响应:")
                logging.info(response_content)
                logging.info("响应内容已获取")
                logging.info("=" * 80)
            except:
                print("日志记录出现问题，但API调用成功")
                print("DeepSeek原始响应:")
                print(response_content)
            
            return response_content
            
        except Exception as e:
            error_msg = f"调用 DeepSeek API 时发生错误: {type(e).__name__}: {str(e)}"
            print(error_msg)
            try:
                logging.error(error_msg)
            except:
                pass  # 忽略日志记录错误
            return None


def process_slate_data(json_data, api_key, scene_numbers=None):
    """
    向后兼容的函数接口
    """
    processor = DeepSeekProcessor()
    return processor.process_slate_data(json_data, api_key, scene_numbers)


# 测试示例
if __name__ == "__main__":
    # 测试用例
    test_json_data = {
        "CellInfos": [
            [
                {"Text": "场号", "Polygon": []},
                {"Text": "镜号", "Polygon": []},
                {"Text": "次数", "Polygon": []},
                {"Text": "景别", "Polygon": []},
                {"Text": "时码", "Polygon": []},
                {"Text": "视效", "Polygon": []},
                {"Text": "成绩", "Polygon": []}
            ],
            [
                {"Text": "212b", "Polygon": []},
                {"Text": "001", "Polygon": []},
                {"Text": "1", "Polygon": []},
                {"Text": "全景", "Polygon": []},
                {"Text": "10:30:15", "Polygon": []},
                {"Text": "无", "Polygon": []},
                {"Text": "OK", "Polygon": []}
            ]
        ]
    }
    
    processor = DeepSeekProcessor()
    # 注意：实际使用时需要传入有效的API密钥
    # result = processor.process_slate_data(test_json_data, "your-api-key-here")
    # print(result) 