#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path


class AppConfig:
    """应用配置管理类"""
    
    def __init__(self):
        # API配置
        self.deepseek_api_key = "sk-f71759d6e28b4985818ea73abcc4eebb"
        
        # 腾讯云API配置
        self.tencent_secret_id = "AKIDWs21iNq7A1g7Vpy8B2iBXktvpkX8bv2w"
        self.tencent_secret_key = "qVxCE3f4GH6h5GdwFlN1a2LWWJtGPL3a"
        
        # 图像处理配置
        self.lut_path = "/Users/sbr/Desktop/OCR.cube"
        
        # 裁剪配置
        self.crop_config = {
            'h_start': 2,    # 第3根水平线 (索引从0开始)
            'h_end': -1,     # 最后一根水平线
            'v_start': 0,    # 第1根垂直线
            'v_end': 7       # 第8根垂直线
        }
        
        # 并行处理配置
        self.max_workers = 10
        self.batch_size = 2  # 每批处理的图像数量
        self.batch_interval = 2.0  # 批次间隔秒数
        
        # 支持的图像格式
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}
        
        # 默认表格列头
        self.default_headers = ["场号", "镜号", "次数", "景别", "时码", "视效", "成绩"]
        
        # UI配置
        self.window_config = {
            'min_width': 1400,
            'min_height': 900,
            'default_width': 1600,
            'default_height': 1000,
            'splitter_sizes': [600, 900]
        }
        
        # 日志配置
        self.log_config = {
            'level': 'INFO',
            'file': 'deepseek_api.log',
            'format': '%(asctime)s - %(levelname)s - %(message)s'
        }
    
    @classmethod
    def from_file(cls, config_path):
        """从配置文件加载配置"""
        config = cls()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 更新配置项
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                        
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        return config
    
    def save_to_file(self, config_path):
        """保存配置到文件"""
        try:
            # 创建目录（如果不存在）
            Path(config_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 准备要保存的配置数据
            config_data = {
                'deepseek_api_key': self.deepseek_api_key,
                'tencent_secret_id': self.tencent_secret_id,
                'tencent_secret_key': self.tencent_secret_key,
                'lut_path': self.lut_path,
                'crop_config': self.crop_config,
                'max_workers': self.max_workers,
                'batch_size': self.batch_size,
                'batch_interval': self.batch_interval,
                'window_config': self.window_config,
                'log_config': self.log_config
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
                
            return True
            
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get_config_path(self):
        """获取默认配置文件路径"""
        home_dir = Path.home()
        config_dir = home_dir / '.yyhg_ocr'
        config_dir.mkdir(exist_ok=True)
        return config_dir / 'config.json'
    
    def validate_config(self):
        """验证配置的有效性"""
        errors = []
        
        # 验证LUT文件路径
        if self.lut_path and not os.path.exists(self.lut_path):
            errors.append(f"LUT文件不存在: {self.lut_path}")
        
        # 验证API密钥
        if not self.deepseek_api_key or not self.deepseek_api_key.strip():
            errors.append("DeepSeek API密钥未设置")
        
        # 验证腾讯云API配置
        if not self.tencent_secret_id or not self.tencent_secret_id.strip():
            errors.append("腾讯云 SecretId 未设置")
        
        if not self.tencent_secret_key or not self.tencent_secret_key.strip():
            errors.append("腾讯云 SecretKey 未设置")
        
        # 验证数值配置
        if self.max_workers <= 0:
            errors.append("最大工作线程数必须大于0")
        
        if self.batch_size <= 0:
            errors.append("批处理大小必须大于0")
        
        if self.batch_interval < 0:
            errors.append("批处理间隔不能为负数")
        
        return errors 