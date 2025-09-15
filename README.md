# A Field of Eggs - OCR for Script Sheets

一个用于脚本表格OCR识别的Python项目。

## 功能特性

- 支持多种OCR引擎（百度、腾讯、DeepSeek）
- 图像预处理和表格检测
- 用户友好的GUI界面
- PDF转PNG功能
- 颜色科学LUT测试

## 主要文件

- `main.py` - 主程序入口
- `main_window.py` - GUI主窗口
- `ocr_pipeline.py` - OCR处理管道
- `image_process.py` - 图像处理模块
- `deepseek_processor.py` - DeepSeek API处理器
- `tencent_ocr.py` - 腾讯OCR接口
- `baidu_ocr.py` - 百度OCR接口
- `pdf_to_png.py` - PDF转换工具

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
python main.py
```

## 注意事项

- 使用前请配置相应的API密钥
- 确保已安装所需的Python依赖包
