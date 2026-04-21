# 抖音情绪类文案创作系统（单体版）开发文档

## 1. 文档信息
- 项目名称：抖音情绪类文案创作系统
- 项目代号：Douyin Copy Engine
- 版本：V1.0
- 架构方式：前后端不分离单体应用
- 推荐技术栈：Python + Flask + Jinja2 + SQLAlchemy + MySQL
- 目标：为抖音情绪八卦/聊天记录/口播类内容提供高效率的文案创作、改写、审核与导出能力

---

## 2. 项目背景
当前短视频内容生产中，真正影响起号和变现效率的不是剪辑，而是文案产出速度、标题命中率、争议设计能力和复用效率。为了提高内容生产效率，需要开发一套面向抖音情绪类内容的文案创作系统。

该系统的核心价值不是“自动发视频”，而是：
1. 快速录入热点/选题
2. 一次生成多个版本文案
3. 一键改写和风格切换
4. 进入审核池管理
5. 一键导出给剪辑或发布使用

---

## 3. 建设目标
### 3.1 业务目标
- 将单条文案平均生产时间压缩到 30 秒内
- 实现单日 50 条以上候选文案产出能力
- 建立爆款结构模板库，支持后续复用

### 3.2 产品目标
- 操作简单，适合非技术运营使用
- 先聚焦“文案生产”，不做自动发布
- 第一版先跑通核心闭环：选题 → 生成 → 改写 → 审核 → 导出

### 3.3 技术目标
- 使用单体架构，降低开发复杂度
- 支持快速本地部署和轻量服务器部署
- 后续可逐步扩展为任务队列、数据分析和模板推荐系统

---

## 4. 用户角色
### 4.1 创作者
- 新建选题
- 生成文案
- 改写文案
- 导出文案

### 4.2 运营
- 管理选题列表
- 审核生成结果
- 收藏模板
- 复用爆款结构

### 4.3 管理员
- 管理系统用户
- 维护提示词模板
- 管理敏感词规则
- 查看历史生成记录

---

## 5. 功能范围

### 5.1 选题管理
#### 功能说明
- 新建单个选题
- 批量录入选题
- 为选题打分类、标签、情绪标签
- 按状态筛选选题

#### 字段定义
- 标题
- 分类
- 标签
- 情绪标签
- 来源
- 状态（待生成 / 已生成 / 已归档）
- 创建时间
- 更新时间

#### 常见分类
- 情侣冲突
- 婚姻现实
- 职场情绪
- 站队争议
- 口播观点
- 聊天记录剧情

---

### 5.2 文案生成
#### 功能说明
根据选题和模板生成抖音情绪类文案。

#### 输入项
- 选题
- 模板
- 内容类型
- 生成数量
- 情绪强度
- 内容长度

#### 输出项
- 标题 3~5 个
- 正文文案 1~3 版
- 评论引导 2~3 个
- 封面短句 2~3 个

#### 支持的内容类型
- 聊天记录型
- 口播型
- 剧情摘要型

---

### 5.3 文案改写
#### 功能说明
对已有文案进行风格调整和重复度优化。

#### 支持动作
- 更像真人
- 更有争议
- 更扎心
- 更短
- 改成聊天记录格式
- 改成口播格式
- 再生成 3 版

---

### 5.4 审核池
#### 功能说明
将生成后的文案统一放入审核池，供人工筛选、编辑和导出。

#### 支持操作
- 查看详情
- 编辑文案
- 审核通过
- 标记需修改
- 作废
- 收藏为模板

---

### 5.5 模板库
#### 功能说明
保存可复用的爆款结构和提示词模板。

#### 模板类型
- 强冲突型
- 委屈共鸣型
- 现实扎心型
- 反转型
- 站队争议型
- 聊天截图型

#### 字段
- 模板名称
- 模板类型
- 提示词正文
- 描述
- 是否启用

---

### 5.6 导出功能
#### 功能说明
将审核通过的文案导出给剪辑或发布人员使用。

#### 支持形式
- 页面一键复制
- 导出 TXT
- 导出 JSON

#### 导出模板 A：聊天记录稿
- 标题
- 角色 A 对话
- 角色 B 对话
- 评论引导

#### 导出模板 B：口播稿
- 标题
- 开头钩子
- 正文
- 结尾互动句

---

### 5.7 敏感词与风险提示（V1 可简化）
#### 功能说明
在保存和导出时检测高风险词汇，并给出提示。

#### 结果等级
- 低风险
- 中风险
- 高风险

#### 处理策略
- 低风险：允许保存
- 中风险：提示复核
- 高风险：阻止导出或要求确认

---

## 6. 非功能需求
### 6.1 响应时间
- 单条文案生成：10 秒内
- 一次生成 3 个版本：30 秒内

### 6.2 可用性
- 页面简洁
- 操作不超过 3 次点击完成单次生成
- 支持移动端基础浏览（但优先桌面端）

### 6.3 安全性
- 登录鉴权
- 记录操作日志
- 不在前端暴露大模型密钥

### 6.4 可维护性
- 采用模块化目录结构
- 服务层封装大模型调用
- 模板、提示词、敏感词均可配置

---

## 7. 业务流程
### 7.1 主流程
1. 用户新建选题
2. 选择模板和内容类型
3. 点击生成
4. 系统返回多个候选文案
5. 用户选择一个保存到审核池
6. 用户编辑调整
7. 审核通过
8. 一键复制或导出

### 7.2 爆款模板复用流程
1. 从模板库选中某个爆款结构
2. 输入新选题
3. 一键生成
4. 人工审核
5. 保存结果

### 7.3 改写流程
1. 打开某条已生成文案
2. 点击改写按钮
3. 系统返回改写版本
4. 用户替换或另存为新版本

---

## 8. 页面原型说明

### 8.1 登录页
字段：
- 用户名
- 密码
- 登录按钮

### 8.2 首页仪表盘
显示：
- 今日新增选题数
- 今日生成文案数
- 待审核数量
- 已通过数量
- 模板数

### 8.3 选题列表页
功能：
- 搜索选题
- 按分类筛选
- 按状态筛选
- 新建选题
- 批量导入（V2）

表格列：
- ID
- 标题
- 分类
- 标签
- 状态
- 创建时间
- 操作

### 8.4 文案生成页
布局建议：
- 左栏：选题信息
- 中栏：模板和生成参数
- 右栏：生成结果

操作：
- 选择模板
- 选择内容类型
- 设置生成数量
- 点击生成
- 保存到审核池

### 8.5 审核池页
表格列：
- ID
- 标题
- 类型
- 状态
- 更新时间
- 操作

详情页支持：
- 编辑
- 改写
- 通过
- 驳回
- 导出
- 收藏模板

### 8.6 模板库页
展示：
- 模板名称
- 类型
- 描述
- 是否启用
- 编辑按钮
- 套用按钮

---

## 9. 技术方案

### 9.1 技术选型
#### 后端
- Python 3.11+
- Flask
- Flask-Login
- Flask-SQLAlchemy
- WTForms（可选）

#### 模板渲染
- Jinja2
- Bootstrap 5（推荐，减少前端开发量）

#### 数据库
- MySQL 8.0
- 开发环境可用 SQLite

#### AI 调用
- 统一封装 LLM 服务
- 使用环境变量管理 API Key

#### 部署
- Gunicorn + Nginx
- Linux 服务器

---

## 10. 单体应用目录结构

```text
copy_engine/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── instance/
│   └── app.db
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models.py
│   ├── forms.py
│   ├── services/
│   │   ├── llm_service.py
│   │   ├── content_service.py
│   │   ├── rewrite_service.py
│   │   └── risk_service.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── topics.py
│   │   ├── contents.py
│   │   ├── reviews.py
│   │   └── templates.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── topics/
│   │   │   ├── list.html
│   │   │   ├── create.html
│   │   │   └── detail.html
│   │   ├── contents/
│   │   │   ├── generate.html
│   │   │   ├── detail.html
│   │   │   └── edit.html
│   │   ├── reviews/
│   │   │   ├── list.html
│   │   │   └── detail.html
│   │   └── templates/
│   │       ├── list.html
│   │       └── edit.html
│   └── static/
│       ├── css/
│       ├── js/
│       └── img/
└── migrations/
```

---

## 11. 数据库设计

### 11.1 users
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| username | varchar(50) | 用户名 |
| password_hash | varchar(255) | 密码摘要 |
| role | varchar(20) | admin/operator/creator |
| created_at | datetime | 创建时间 |

### 11.2 topics
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| title | varchar(255) | 选题标题 |
| category | varchar(50) | 分类 |
| tags | varchar(255) | 标签，逗号分隔或 JSON |
| emotion_level | int | 情绪强度 1~5 |
| source | varchar(100) | 来源 |
| status | varchar(20) | draft/generated/archived |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 11.3 templates
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| name | varchar(100) | 模板名 |
| template_type | varchar(30) | strong_conflict/chat/spoken |
| prompt | text | 提示词正文 |
| description | text | 描述 |
| is_active | tinyint | 是否启用 |
| created_at | datetime | 创建时间 |

### 11.4 contents
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| topic_id | bigint FK | 关联选题 |
| template_id | bigint FK | 关联模板 |
| title | text | 文案标题 |
| body | longtext | 文案正文 |
| comment_hook | text | 评论引导 |
| cover_text | text | 封面短句 |
| content_type | varchar(20) | chat/spoken/story |
| version_no | int | 版本号 |
| status | varchar(20) | generated/pending_review/approved/rejected |
| risk_level | varchar(20) | low/medium/high |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 11.5 rewrite_logs
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| content_id | bigint FK | 文案 ID |
| action | varchar(50) | more_human/shorten/chat_format 等 |
| before_text | longtext | 改写前 |
| after_text | longtext | 改写后 |
| created_at | datetime | 创建时间 |

### 11.6 review_records
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| content_id | bigint FK | 文案 ID |
| reviewer_id | bigint FK | 审核人 |
| review_status | varchar(20) | pending/approved/rejected |
| review_note | text | 审核备注 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 11.7 operation_logs（可选）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| user_id | bigint | 用户 |
| action | varchar(50) | 操作类型 |
| target_type | varchar(30) | topics/contents/templates |
| target_id | bigint | 目标 ID |
| detail | text | 详情 |
| created_at | datetime | 创建时间 |

---

## 12. 核心模型关系
- 一个 Topic 可以生成多个 Content
- 一个 Template 可以被多个 Content 复用
- 一个 Content 可以有多个 Rewrite Log
- 一个 Content 可以有多个 Review Record

---

## 13. 路由设计（页面路由）

### 13.1 认证
- `GET /login` 登录页
- `POST /login` 登录提交
- `GET /logout` 退出登录

### 13.2 首页
- `GET /` 仪表盘

### 13.3 选题
- `GET /topics` 选题列表
- `GET /topics/create` 新建页
- `POST /topics/create` 创建选题
- `GET /topics/<id>` 选题详情
- `POST /topics/<id>/archive` 归档

### 13.4 文案
- `GET /contents/generate/<topic_id>` 文案生成页
- `POST /contents/generate/<topic_id>` 提交生成
- `GET /contents/<id>` 文案详情
- `POST /contents/<id>/rewrite` 文案改写
- `POST /contents/<id>/save-review` 保存到审核池
- `POST /contents/<id>/update` 更新文案
- `GET /contents/<id>/export` 导出文案

### 13.5 审核池
- `GET /reviews` 审核池列表
- `GET /reviews/<content_id>` 审核详情
- `POST /reviews/<content_id>/approve` 审核通过
- `POST /reviews/<content_id>/reject` 审核驳回

### 13.6 模板
- `GET /templates` 模板列表
- `GET /templates/create` 新建模板页
- `POST /templates/create` 新建模板
- `GET /templates/<id>/edit` 编辑模板页
- `POST /templates/<id>/edit` 保存模板

---

## 14. 接口清单（单体内部可同步支持 JSON）
为便于后续扩展，建议关键动作页面接口同时支持表单和 JSON。

### 14.1 创建选题
**POST /topics/create**

请求字段：
- title
- category
- tags
- emotion_level
- source

返回：
- 成功跳转到选题列表或详情页

### 14.2 生成文案
**POST /contents/generate/<topic_id>**

请求字段：
- template_id
- content_type
- variants
- emotion_level
- max_length

处理逻辑：
1. 读取 Topic
2. 读取 Template
3. 组装 Prompt
4. 调用 LLM
5. 解析结果
6. 保存 contents 记录
7. 返回结果列表

### 14.3 改写文案
**POST /contents/<id>/rewrite**

请求字段：
- action

支持值：
- more_human
- more_conflict
- shorten
- chat_format
- spoken_format
- regen_3

返回：
- 改写后的文本
- 可选择替换原文或新增版本

### 14.4 保存到审核池
**POST /contents/<id>/save-review**

处理逻辑：
- 将 content.status 改为 pending_review
- 创建 review_record，状态为 pending

### 14.5 审核通过
**POST /reviews/<content_id>/approve**

处理逻辑：
- content.status = approved
- review_record.status = approved

### 14.6 审核驳回
**POST /reviews/<content_id>/reject**

请求字段：
- review_note

处理逻辑：
- content.status = rejected
- review_record.status = rejected

### 14.7 导出
**GET /contents/<id>/export?format=txt**

支持：
- txt
- json
- copy（页面复制模式）

---

## 15. 服务层设计

### 15.1 llm_service.py
职责：
- 统一封装模型调用
- 管理请求参数
- 捕获异常
- 规范返回结构

建议接口：
```python
class LLMService:
    def generate(self, prompt: str) -> str:
        pass
```

### 15.2 content_service.py
职责：
- 构建生成提示词
- 解析模型输出
- 保存文案结果

建议接口：
```python
class ContentService:
    def build_prompt(self, topic, template, content_type, emotion_level, max_length):
        pass

    def generate_contents(self, topic, template, content_type, variants=3):
        pass
```

### 15.3 rewrite_service.py
职责：
- 根据动作构建改写提示词
- 保存改写日志

建议接口：
```python
class RewriteService:
    def rewrite(self, content, action):
        pass
```

### 15.4 risk_service.py
职责：
- 敏感词扫描
- 风险等级判断
- 替换建议

建议接口：
```python
class RiskService:
    def scan(self, text: str) -> dict:
        pass
```

---

## 16. Prompt 设计规范
为了让开发可配置，建议将 Prompt 分为三层：
1. 系统角色层
2. 任务要求层
3. 输出格式层

### 16.1 文案生成 Prompt 模板
```text
你是抖音情绪类爆款文案专家。

目标：围绕给定选题写适合抖音发布的情绪类文案。

要求：
1. 开头直接冲突
2. 句子短，口语化
3. 留争议，不给标准答案
4. 适合聊天记录/口播视频
5. 控制在指定长度内

请输出：
1. 标题 3 个
2. 正文 3 版
3. 评论引导 2 个
4. 封面短句 2 个

选题：{topic_title}
分类：{topic_category}
模板：{template_name}
内容类型：{content_type}
情绪强度：{emotion_level}
```

### 16.2 改写 Prompt 模板
```text
请对下面文案做改写。

改写目标：{action}
要求：
1. 保留核心冲突
2. 提高真实感
3. 不要写成长文章
4. 适合抖音口语表达

原文如下：
{body}
```

---

## 17. 示例代码骨架（单体应用）
以下为开发起步骨架，便于研发快速搭建。

### 17.1 app.py
```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
```

### 17.2 app/__init__.py
```python
from flask import Flask
from .extensions import db, login_manager
from .routes.auth import auth_bp
from .routes.dashboard import dashboard_bp
from .routes.topics import topics_bp
from .routes.contents import contents_bp
from .routes.reviews import reviews_bp
from .routes.templates import templates_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(topics_bp)
    app.register_blueprint(contents_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(templates_bp)

    with app.app_context():
        db.create_all()

    return app
```

### 17.3 app/extensions.py
```python
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth_bp.login'
```

### 17.4 config.py
```python
import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
```

### 17.5 models.py
```python
from datetime import datetime
from .extensions import db


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50))
    tags = db.Column(db.String(255))
    emotion_level = db.Column(db.Integer, default=3)
    source = db.Column(db.String(100))
    status = db.Column(db.String(20), default='draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Template(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    template_type = db.Column(db.String(30))
    prompt = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('template.id'))
    title = db.Column(db.Text)
    body = db.Column(db.Text)
    comment_hook = db.Column(db.Text)
    cover_text = db.Column(db.Text)
    content_type = db.Column(db.String(20), default='chat')
    version_no = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='generated')
    risk_level = db.Column(db.String(20), default='low')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 17.6 llm_service.py
```python
import os
from openai import OpenAI


class LLMService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = os.getenv('OPENAI_MODEL', 'gpt-5.4')

    def generate(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )
        return response.output_text
```

### 17.7 content_service.py
```python
from .llm_service import LLMService


class ContentService:
    def __init__(self):
        self.llm = LLMService()

    def build_prompt(self, topic, template, content_type, emotion_level, max_length=200):
        return f"""
你是抖音情绪类爆款文案专家。
请围绕以下选题生成适合抖音发布的文案。

选题：{topic.title}
分类：{topic.category}
模板：{template.name}
类型：{content_type}
情绪强度：{emotion_level}
最大长度：{max_length}

输出：
1. 标题3个
2. 正文3版
3. 评论引导2个
4. 封面短句2个
"""

    def generate(self, topic, template, content_type='chat', emotion_level=3, max_length=200):
        prompt = self.build_prompt(topic, template, content_type, emotion_level, max_length)
        return self.llm.generate(prompt)
```

---

## 18. 前端页面开发说明（Jinja + Bootstrap）
### 18.1 base.html
统一定义：
- 顶部导航
- 侧边菜单
- 消息提示区
- 内容渲染区

### 18.2 通用 UI 规范
- 表格页使用 Bootstrap table
- 表单使用 card + form-control
- 操作按钮统一：主操作蓝色，危险操作红色
- 生成结果使用卡片分组展示

### 18.3 生成页交互建议
- 提交生成时显示 loading
- 返回结果后按“标题 / 正文 / 评论引导 / 封面短句”分组
- 每条结果旁边有“保存到审核池”按钮

---

## 19. 开发排期建议
### 第 1 阶段：MVP（3~5 天）
- 登录
- 选题管理
- 模板管理
- 文案生成
- 文案详情
- 审核池
- 导出

### 第 2 阶段（2~4 天）
- 改写功能
- 风险提示
- 操作日志
- 首页统计

### 第 3 阶段（后续扩展）
- 爆款模板推荐
- 指标回流
- 批量任务生成
- 视频脚本生成

---

## 20. 验收标准
项目达到以下条件即可视为 V1 可上线：
1. 用户可登录系统
2. 可创建选题
3. 可选择模板生成至少 3 个版本文案
4. 可对文案执行至少 3 种改写动作
5. 可将文案送审、通过或驳回
6. 可导出已通过文案
7. 系统可保存历史数据

---

## 21. 风险与边界
### 21.1 本期不做
- 自动发布抖音
- 自动视频剪辑
- 热点爬虫接入
- 多组织协作权限系统

### 21.2 主要风险
- 模型输出格式不稳定
- 风险文案误判
- 生成质量依赖 Prompt 设计

### 21.3 建议措施
- 强制要求模型输出结构化内容
- 保留人工审核环节
- 模板和提示词支持后台配置

---

## 22. 最终开发建议
这套系统第一版应坚持“轻、快、能用”的原则：
- 架构上用单体应用
- 页面上用 Jinja 模板渲染
- 功能上聚焦文案生产闭环
- 发布和视频生成放到 V2 以后再做

只要第一版把“生成质量 + 改写效率 + 审核导出”做好，就已经足够支撑内容团队起号和试错。

