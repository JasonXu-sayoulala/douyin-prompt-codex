# 媒体生成功能安装与使用指南

## 功能概述

本次更新为 `douyin-prompt-codex` 项目添加了完整的媒体生成功能：
- **文案生成**：基于主题和模板生成抖音文案
- **图片生成**：根据文案自动生成配图（使用 DALL-E）
- **视频合成**：将图片序列合成为走马灯视频

## 安装步骤

### 1. 安装 Python 依赖

```bash
cd C:\Users\EDY\.openclaw\workspace-dev\projects\douyin-prompt-codex\copy_engine
pip install -r requirements.txt
```

新增的依赖包：
- `Pillow>=10.0.0` - 图像处理
- `requests>=2.31.0` - HTTP 请求

### 2. 安装 ffmpeg

ffmpeg 是视频合成的核心工具，需要单独安装。

**Windows 安装方式：**

1. 下载 ffmpeg：https://www.gyan.dev/ffmpeg/builds/
2. 解压到任意目录（例如 `C:\ffmpeg`）
3. 将 `C:\ffmpeg\bin` 添加到系统环境变量 PATH
4. 验证安装：
   ```bash
   ffmpeg -version
   ```

### 3. 配置环境变量

在 `.env` 文件中配置 OpenAI API（用于图片生成）：

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件，添加以下配置
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选
OPENAI_MODEL=gpt-4o-mini
```

**注意**：如果不配置 API Key，系统会生成占位图片用于演示。

## 使用方法

### 1. 启动应用

```bash
cd C:\Users\EDY\.openclaw\workspace-dev\projects\douyin-prompt-codex\copy_engine
python app.py
```

应用将在 `http://127.0.0.1:5000` 启动。

### 2. 访问媒体生成页面

1. 登录系统（默认账号：admin / admin123）
2. 点击导航栏的"媒体生成"
3. 选择主题和模板
4. 设置媒体类型和图片数量
5. 点击"开始生成"

### 3. 生成流程

系统会自动完成以下步骤：
1. 根据主题和模板生成文案
2. 将文案转换为图像提示词
3. 调用 DALL-E 生成图片
4. 使用 ffmpeg 将图片合成为视频
5. 提供预览和下载链接

### 4. 查看结果

生成完成后，可以：
- **预览**：在线查看生成的视频和文案
- **下载**：下载视频文件到本地
- **查看文案**：查看完整的文案内容

## 文件结构

```
copy_engine/
├── app/
│   ├── routes/
│   │   └── media.py              # 媒体生成路由
│   ├── services/
│   │   └── media_generation_service.py  # 媒体生成服务
│   └── templates/
│       └── media/
│           ├── generate.html     # 生成页面
│           └── preview.html      # 预览页面
├── instance/
│   └── media_output/             # 生成的媒体文件存储目录
└── requirements.txt              # Python 依赖
```

## 配置说明

### 图片生成配置

在 `media_generation_service.py` 中可以调整：
- `num_images`: 生成图片数量（默认 3）
- `style`: 图片风格（vivid/natural）
- `size`: 图片尺寸（默认 1024x1024）

### 视频合成配置

在 `media_generation_service.py` 中可以调整：
- `duration_per_image`: 每张图片显示时长（默认 3 秒）
- `transition_duration`: 转场时长（默认 0.5 秒）
- `fps`: 视频帧率（默认 30）

## 故障排查

### 1. ffmpeg 未找到

**错误信息**：`ffmpeg: command not found`

**解决方法**：
- 确认 ffmpeg 已安装
- 检查 PATH 环境变量是否包含 ffmpeg 的 bin 目录
- 重启终端或 IDE

### 2. 图片生成失败

**错误信息**：`图像生成客户端未初始化`

**解决方法**：
- 检查 `.env` 文件中的 `OPENAI_API_KEY` 是否正确
- 确认 API Key 有足够的额度
- 如果不需要真实图片，系统会自动生成占位图片

### 3. 视频合成失败

**错误信息**：`视频生成失败`

**解决方法**：
- 检查 ffmpeg 是否正常工作
- 确认图片文件存在且格式正确
- 查看日志文件获取详细错误信息

## 下一步优化

1. **支持更多图像生成模型**：集成通义万相、Midjourney 等
2. **视频模板系统**：预设多种视频风格和转场效果
3. **批量生成**：一次生成多个视频
4. **文字叠加**：在视频中添加文案文字
5. **背景音乐**：为视频添加背景音乐

## 技术栈

- **后端**：Flask + SQLAlchemy
- **图像生成**：OpenAI DALL-E 3
- **图像处理**：Pillow
- **视频合成**：ffmpeg
- **前端**：Bootstrap 5 + Vanilla JavaScript

## 许可证

本项目遵循原项目的许可证。
