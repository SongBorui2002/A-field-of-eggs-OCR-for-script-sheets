import base64
import urllib
import requests

def get_file_content_as_base64(path, urlencoded=False):
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

# 测试连接
if __name__ == "__main__":
    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting"
    
    # 请将 'test.jpg' 替换为您要测试的图片路径
    image_path = "/Users/sbr/Desktop/3.png"
    
    # 获取图片的base64编码
    image = get_file_content_as_base64(image_path, True)
    
    payload = f'image={image}'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Bearer bce-v3/ALTAK-5bpz5CXoG1RPNoJUcnQxM/45b590570028c6caad771032ede02bf34419d46c'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
    
    print(response.text) 