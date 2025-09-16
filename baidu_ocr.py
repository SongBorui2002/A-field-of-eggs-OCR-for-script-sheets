import base64
import urllib
import requests


class BaiduOCR:
    """百度OCR处理器类"""
    
    def __init__(self, access_token="bce-v3/ALTAK-5bpz5CXoG1RPNoJUcnQxM/45b590570028c6caad771032ede02bf34419d46c"):
        """
        初始化百度OCR处理器
        :param access_token: 百度API访问令牌
        """
        self.access_token = access_token
        self.base_url = "https://aip.baidubce.com/rest/2.0/ocr/v1"
    
    def get_file_content_as_base64(self, path, urlencoded=False):
        """
        获取文件base64编码
        :param path: 文件路径
        :param urlencoded: 是否对结果进行urlencoded 
        :return: base64编码信息
        """
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf8")
            if urlencoded:
                content = urllib.parse.quote_plus(content)
        return content
    
    def handwriting_ocr(self, image_path):
        """
        手写文字识别
        :param image_path: 图像文件路径
        :return: OCR识别结果
        """
        url = f"{self.base_url}/handwriting"
        
        # 获取图片的base64编码
        image = self.get_file_content_as_base64(image_path, True)
        
        payload = f'image={image}'
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Bearer {self.access_token}'
        }
        
        try:
            response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
            return response.text
        except Exception as e:
            print(f"百度OCR识别失败: {e}")
            return None
    
    def general_ocr(self, image_path, detect_direction=False, probability=False):
        """
        通用文字识别
        :param image_path: 图像文件路径
        :param detect_direction: 是否检测图像朝向
        :param probability: 是否返回识别结果中每一行的置信度
        :return: OCR识别结果
        """
        url = f"{self.base_url}/general_basic"
        
        # 获取图片的base64编码
        image = self.get_file_content_as_base64(image_path, True)
        
        payload = f'image={image}'
        if detect_direction:
            payload += '&detect_direction=true'
        if probability:
            payload += '&probability=true'
            
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Bearer {self.access_token}'
        }
        
        try:
            response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
            return response.text
        except Exception as e:
            print(f"百度OCR识别失败: {e}")
            return None
    
    def table_ocr(self, image_path):
        """
        表格文字识别
        :param image_path: 图像文件路径
        :return: OCR识别结果
        """
        url = f"{self.base_url}/table"
        
        # 获取图片的base64编码
        image = self.get_file_content_as_base64(image_path, True)
        
        payload = f'image={image}'
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Bearer {self.access_token}'
        }
        
        try:
            response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
            return response.text
        except Exception as e:
            print(f"百度OCR识别失败: {e}")
            return None


# ==================== 向后兼容的函数接口 ====================

def get_file_content_as_base64(path, urlencoded=False):
    """向后兼容的函数接口"""
    ocr = BaiduOCR()
    return ocr.get_file_content_as_base64(path, urlencoded)


# 测试连接
if __name__ == "__main__":
    # 请将 'test.jpg' 替换为您要测试的图片路径
    image_path = "/Users/sbr/Desktop/3.png"
    
    # 创建百度OCR实例
    ocr = BaiduOCR()
    
    # 进行手写文字识别
    result = ocr.handwriting_ocr(image_path)
    
    print(result) 