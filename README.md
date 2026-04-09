### 📝 项目简介

这是一个用于自动重写视频脚本的 AI 工具，能够智能提取文章风格、专有名词和大纲，并对文本进行重写优化。

### 🔧 环境要求

Python 3.10.1

pip 包管理工具

### 📦 安装步骤

克隆项目

```bash
git clone (https://git.no-fish.cn/EW-Flow/ai-video-demo.git)
cd ai-video-demo
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 🚀 使用方法

文件准备

将需要处理的 .docx 格式文件放入 input 文件夹中

运行程序

```bash
python app.py
```

#### 运行选项

程序启动后会提示选择模式：

```
1. 单文件模式：处理指定路径的单个文件

2. 文件夹模式：批量处理 input 目录下的所有文件
```

#### 输出结果

处理后的文件会自动保存在 output 文件夹中

预计18000字,30章,需要550秒

```
成功处理的文件命名格式：原文件名.txt

处理失败的文件命名格式：原文件名\_failed.txt
```

📁 目录结构

```text
ai-video-demo/
├── input/ # 放置待处理的 .docx 文件
├── output/ # 处理结果输出目录
├── app.py # 主程序入口
├── requirements.txt # 项目依赖
└── service/ # 核心服务模块
```

### ⚙️ 功能特点

- **自动识别文章章节分隔符**！！！

- 提取文章风格特征

- 识别专有名词和实体

- 智能重写文本

- 支持批量处理

- 自动重试机制

⚠️ 注意事项
仅支持 .docx 格式文件

请确保 input 和 output 文件夹存在且有读写权限

处理大量文件时请耐心等待
