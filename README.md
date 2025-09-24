# 场记单OCR处理系统

一个完整的影视后期场记单数字化处理系统，支持从PDF/图像到DaVinci Resolve元数据导入的全流程自动化处理。

## 🎯 系统概述

本系统专为影视后期制作设计，能够自动识别场记单中的表格数据，并通过AI处理生成结构化的场记信息，最终导入到DaVinci Resolve中进行后期制作管理。

### 核心功能
- 📄 **PDF转图像**: 支持PDF文件转换为高质量PNG图像
- 🖼️ **图像预处理**: LUT色彩校正 + 智能表格裁剪
- 🔍 **OCR识别**: 腾讯云表格OCR精确识别场记数据
- 🤖 **AI处理**: DeepSeek大模型智能修复和结构化数据
- 📊 **表格编辑**: 可视化表格编辑器，支持拖拽填充和批量操作
- 🎬 **元数据管理**: 自动匹配和更新CSV元数据文件
- 🎞️ **DaVinci集成**: 一键导入元数据到DaVinci Resolve
- 📁 **自动分场**: 根据Scene元数据自动组织剪辑到不同文件夹

## 🏗️ 系统架构

```
PDF文件 → 图像处理 → OCR识别 → AI处理 → 表格编辑 → 元数据更新 → DaVinci导入
   ↓         ↓         ↓        ↓        ↓         ↓          ↓
pdf_to_png → image_process → ocr_pipeline → deepseek_processor → table_editor → metadata_processor → import_metadata_to_resolve
```

### 处理流程详解

1. **PDF转换** (`pdf_to_png.py`)
   - 支持PyMuPDF和pdf2image两种引擎
   - 可配置DPI和页面范围
   - 自动选择最优转换引擎

2. **图像预处理** (`image_process.py`)
   - LUT色彩校正处理
   - 智能表格检测和裁剪
   - 支持批量并行处理
   - 针对Apple M3 Max优化

3. **OCR识别** (`ocr_pipeline.py`)
   - 腾讯云表格OCR API
   - 自动解析表格结构
   - 转换为结构化数据格式

4. **AI智能处理** (`deepseek_processor.py`)
   - DeepSeek大模型处理
   - 智能修复OCR错误
   - 场号继承和时码标准化
   - 生成规范JSON格式

5. **表格编辑** (`table_editor.py`)
   - 可视化表格编辑器
   - 支持拖拽填充和序列生成
   - 批量选择和编辑操作
   - 右键菜单快捷操作

6. **元数据处理** (`metadata_processor.py`)
   - CSV元数据文件处理
   - 自动匹配场记信息
   - 生成更新后的CSV文件

7. **DaVinci集成** (`import_metadata_to_resolve.py`)
   - 自动导入元数据到DaVinci Resolve
   - 支持Scene、Shot、Take等字段
   - 自动设置Clip Name模板

8. **分场组织** (`organize_by_scene.py`)
   - 根据Scene元数据自动分场
   - 创建对应文件夹结构
   - 移动剪辑到相应场景文件夹

## 📋 系统要求

### 硬件要求
- **推荐**: Apple M3 Max或同等性能处理器
- **内存**: 16GB以上
- **存储**: 至少2GB可用空间

### 软件要求
- **操作系统**: macOS 10.15+ / Windows 10+ / Linux
- **Python**: 3.8+
- **DaVinci Resolve**: 18.0+ (用于元数据导入)

### 依赖库
```bash
# 核心依赖
PySide6>=6.5.0
pandas>=1.5.0
opencv-python>=4.8.0
numpy>=1.24.0

# PDF处理
PyMuPDF>=1.23.0
pdf2image>=3.1.0

# 图像处理
colour-science>=0.4.0
Pillow>=9.5.0

# OCR和AI
tencentcloud-sdk-python>=3.0.0
openai>=1.0.0

# 其他工具
chardet>=5.0.0
psutil>=5.9.0
```

## 🚀 安装指南

### 1. 克隆项目
```bash
git clone <repository-url>
cd YYHG_ocr
```

### 2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置API密钥
创建配置文件 `~/.yyhg_ocr/config.json`:
```json
{
  "deepseek_api_key": "your-deepseek-api-key",
  "tencent_secret_id": "your-tencent-secret-id", 
  "tencent_secret_key": "your-tencent-secret-key",
  "lut_path": "/path/to/your/OCR.cube"
}
```

### 5. 准备LUT文件
将色彩校正LUT文件 `OCR.cube` 放置在项目根目录或配置指定路径。

## 📖 使用指南

### 启动系统
```bash
python main.py
```

### 基本工作流程

#### 1. 处理PDF文件
- 点击"选择PDF文件"按钮
- 系统自动转换为PNG图像
- 支持批量处理多页PDF

#### 2. 图像预处理
- 自动应用LUT色彩校正
- 智能检测和裁剪表格区域
- 支持手动调整裁剪参数

#### 3. OCR识别
- 使用腾讯云表格OCR API
- 自动识别表格结构和内容
- 生成结构化数据

#### 4. AI智能处理
- DeepSeek大模型修复OCR错误
- 智能场号继承和时码标准化
- 生成规范的场记数据

#### 5. 表格编辑
- 可视化编辑识别结果
- 支持拖拽填充和序列生成
- 批量编辑和验证

#### 6. 元数据更新
- 选择CSV元数据文件
- 自动匹配场记信息
- 生成更新后的CSV文件

#### 7. DaVinci导入
- 确保DaVinci Resolve正在运行
- 运行导入脚本
- 自动设置剪辑元数据

#### 8. 分场组织
- 运行分场脚本
- 根据Scene自动创建文件夹
- 移动剪辑到对应场景

### 命令行工具

#### PDF转换
```bash
python pdf_to_png.py document.pdf -o output_folder/ --dpi 600 --pages 1-5
```

#### 图像处理
```bash
python image_process.py input_image.jpg
python image_process.py --batch input_folder/
```

#### OCR处理
```bash
python ocr_pipeline.py image.png --api-key your-key --scene-numbers 218,R39,24a
```

#### 元数据导入
```bash
python import_metadata_to_resolve.py
```

#### 分场组织
```bash
python organize_by_scene.py
```

## ⚙️ 配置说明

### 图像处理配置
```json
{
  "lut_path": "/path/to/OCR.cube",
  "crop_config": {
    "h_start": 2,
    "h_end": -1,
    "v_start": 0,
    "v_end": 7
  }
}
```

### 并行处理配置
```json
{
  "max_workers": 10,
  "batch_size": 2,
  "batch_interval": 2.0
}
```

### 窗口配置
```json
{
  "window_config": {
    "min_width": 800,
    "min_height": 500,
    "default_width": 1600,
    "default_height": 1000
  }
}
```

## 🔧 高级功能

### 拖拽填充
- 选择单元格后拖拽可自动填充序列
- 支持数字、日期、字母序列
- 智能识别填充模式

### 批量处理
- 支持多图像并行处理
- 自动资源管理和负载均衡
- 进度显示和错误处理

### 场号管理
- 支持自定义场号列表
- 智能场号继承和修复
- 时码格式标准化

### 元数据模板
- 支持DaVinci Resolve模板字符串
- 自动生成Clip Name
- 自定义元数据字段

## 🐛 故障排除

### 常见问题

#### 1. PDF转换失败
- 检查PDF文件是否损坏
- 尝试不同的转换引擎
- 调整DPI设置

#### 2. OCR识别率低
- 检查图像质量和对比度
- 调整LUT处理参数
- 优化表格裁剪区域

#### 3. DaVinci连接失败
- 确保DaVinci Resolve正在运行
- 检查外部脚本访问权限
- 验证项目是否已打开

#### 4. API调用失败
- 检查网络连接
- 验证API密钥有效性
- 查看API配额限制

### 日志文件
- 系统日志: `deepseek_api.log`
- 错误信息会显示在控制台和状态栏

## 📝 开发说明

### 项目结构
```
YYHG_ocr/
├── main.py                 # 主程序入口
├── main_window.py          # 主窗口界面
├── config.py              # 配置管理
├── pdf_to_png.py          # PDF转换模块
├── image_process.py       # 图像处理模块
├── ocr_pipeline.py        # OCR处理流程
├── deepseek_processor.py  # AI处理模块
├── table_editor.py        # 表格编辑器
├── metadata_processor.py  # 元数据处理
├── import_metadata_to_resolve.py  # DaVinci导入
├── organize_by_scene.py   # 分场组织
├── batch_thread.py        # 批处理线程
├── image_viewer.py        # 图像查看器
├── tencent_ocr.py         # 腾讯云OCR
└── OCR.cube              # LUT文件
```

### 扩展开发
- 支持新的OCR服务提供商
- 添加更多图像处理算法
- 扩展元数据字段支持
- 集成其他后期制作软件

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进项目。

## 📞 技术支持

如有问题，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至技术支持邮箱

---

**注意**: 使用本系统前请确保已获得相关API服务的授权，并遵守相应的使用条款和限制。
