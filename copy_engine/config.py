import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    INSTANCE_PATH = os.path.join(BASE_DIR, "instance")
    _default_sqlite = os.path.join(INSTANCE_PATH, "app.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{_default_sqlite}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # 通义万相文生图（当 OPENAI_BASE_URL 指向 DashScope 兼容模式时，配图走 wanx 而非 DALL·E）
    DASHSCOPE_T2I_MODEL = os.environ.get("DASHSCOPE_T2I_MODEL", "wanx-v1")
    WANX_IMAGE_SIZE = os.environ.get("WANX_IMAGE_SIZE", "720*1280")
    WANX_STYLE = os.environ.get("WANX_STYLE", "<auto>")
    WANX_TASK_POLL_SEC = int(os.environ.get("WANX_TASK_POLL_SEC", "120"))

    # 媒体成片：可选本地背景音乐（mp3/wav），不配则自动生成简短氛围音并铺满视频时长
    MEDIA_BGM_PATH = os.environ.get("MEDIA_BGM_PATH", "").strip()

    # 逗号分隔敏感词，也可通过环境变量扩展
    SENSITIVE_WORDS = os.environ.get(
        "SENSITIVE_WORDS",
        "自杀,自残,暴力,色情,赌博,毒品,诈骗,恐怖",
    )
