# YYHG OCR - 场记单OCR处理系统

一个基于Python的场记单OCR（光学字符识别）处理系统，专门用于影视制作中场记单的自动化识别和处理。

## 功能特性

- 🖼️ **多格式支持**: 支持PDF、PNG、JPG等多种图像格式
- 🔍 **智能OCR**: 集成多种OCR引擎（腾讯云OCR、百度OCR等）
- 🎯 **表格识别**: 专门针对场记单表格结构进行优化识别
- 🤖 **AI增强**: 集成DeepSeek API进行结果优化和结构化处理
- 📊 **批量处理**: 支持大批量图像的并行处理
- 🎨 **图像预处理**: 自动图像增强、去噪、二值化等预处理功能
- 🎬 **DaVinci Resolve集成**: 支持与达芬奇调色软件的API集成
- 💻 **友好界面**: 基于PySide6的现代化图形用户界面

## 系统要求

- Python 3.8+
- PySide6
- OpenCV
- PIL/Pillow
- 其他依赖项见requirements.txt

## 安装和使用

1. 克隆项目
```bash
git clone https://github.com/SongBorui2002/YYHG_ocr.git
cd YYHG_ocr
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行程序
```bash
python main.py
```

## 项目结构

- `main.py` - 程序入口
- `main_window.py` - 主界面窗口
- `ocr_pipeline.py` - OCR处理流水线
- `image_process.py` - 图像预处理模块
- `deepseek_processor.py` - DeepSeek API处理模块
- `tencent_ocr.py` - 腾讯云OCR接口
- `baidu_ocr.py` - 百度OCR接口
- `pdf_to_png.py` - PDF转图像功能
- `davinci_example.py` - DaVinci Resolve集成示例

## 配置

在使用前，请配置相应的API密钥：
- 腾讯云OCR API密钥
- 百度OCR API密钥
- DeepSeek API密钥

## 许可证

本项目采用MIT许可证。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 联系方式

如有问题或建议，请通过GitHub Issues联系。 