"""媒体生成服务：根据文案生成图片和视频"""
import logging
import os
import re
import subprocess
import textwrap
import time
import uuid
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

WANX_SUBMIT_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
WANX_TASK_BASE = "https://dashscope.aliyuncs.com/api/v1/tasks/"


class MediaGenerationService:
    """统一封装图片生成和视频合成功能"""

    def __init__(self, app=None):
        self._image_client = None
        self._output_dir = None
        self._use_wanx = False
        self._dashscope_key = ""
        self._wanx_model = "wanx-v1"
        self._wanx_size = "720*1280"
        self._wanx_style = "<auto>"
        self._wanx_poll_sec = 120
        self._bgm_path = ""
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """初始化服务"""
        root = app.config.get("INSTANCE_PATH")
        if not root or not str(root).strip():
            root = getattr(app, "instance_path", None) or os.path.join(os.getcwd(), "instance")
        self._output_dir = Path(root) / "media_output"
        self._output_dir.mkdir(parents=True, exist_ok=True)

        key = app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        base_raw = app.config.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "") or ""
        base_l = base_raw.lower()

        self._dashscope_key = key or ""
        self._wanx_model = app.config.get("DASHSCOPE_T2I_MODEL", "wanx-v1")
        self._wanx_size = app.config.get("WANX_IMAGE_SIZE", "720*1280")
        self._wanx_style = app.config.get("WANX_STYLE", "<auto>")
        self._wanx_poll_sec = int(app.config.get("WANX_TASK_POLL_SEC", 120))

        # DashScope 兼容模式 base 下 OpenAI 的 images.generate 不可用，改走通义万相 HTTP 异步接口
        self._use_wanx = bool(key) and (
            "dashscope.aliyuncs.com" in base_l or "dashscope-intl.aliyuncs.com" in base_l
        )

        self._image_client = None
        if key and not self._use_wanx:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {"api_key": key}
                if base_raw.strip():
                    kwargs["base_url"] = base_raw.strip()
                self._image_client = OpenAI(**kwargs)
            except Exception as e:
                logger.warning("OpenAI 图像客户端初始化失败: %s", e)
                self._image_client = None

        if self._use_wanx:
            logger.info("媒体配图：已启用通义万相 %s（%s）", self._wanx_model, self._wanx_size)

        self._bgm_path = (app.config.get("MEDIA_BGM_PATH") or "").strip()

    def generate_images_from_copy(
        self,
        copy_text: str,
        num_images: int = 3,
        style: str = "vivid"
    ) -> list[str]:
        """
        根据文案生成图片
        
        Args:
            copy_text: 文案内容
            num_images: 生成图片数量
            style: 图片风格 (vivid/natural)
            
        Returns:
            生成的图片路径列表
        """
        if self._use_wanx:
            try:
                return self._generate_images_via_wanx(copy_text, num_images)
            except Exception as e:
                logger.exception("通义万相配图失败，回退占位图: %s", e)
                return self._generate_placeholder_images(num_images, copy_excerpt=copy_text)

        if not self._image_client:
            logger.warning("图像生成客户端未初始化，返回占位图片")
            return self._generate_placeholder_images(num_images, copy_excerpt=copy_text)

        image_paths = []
        image_prompt = self._copy_to_image_prompt(copy_text)

        try:
            for i in range(num_images):
                response = self._image_client.images.generate(
                    model="dall-e-3",
                    prompt=image_prompt,
                    size="1024x1024",
                    quality="standard",
                    style=style,
                    n=1,
                )
                image_url = response.data[0].url
                image_path = self._download_image(
                    image_url, f"dalle_{uuid.uuid4().hex[:8]}_{i + 1}.png"
                )
                image_paths.append(str(image_path.resolve()))
        except Exception as e:
            logger.exception("图片生成失败: %s", e)
            return self._generate_placeholder_images(num_images, copy_excerpt=copy_text)

        return image_paths

    def create_slideshow_video(
        self,
        image_paths: list[str],
        output_name: str = "slideshow.mp4",
        duration_per_image: float = 3.0,
        transition_duration: float = 0.5,
        add_text_overlay: bool = True,
        text_content: str = ""
    ) -> str:
        """
        将图片序列合成为走马灯视频
        
        Args:
            image_paths: 图片路径列表
            output_name: 输出视频文件名
            duration_per_image: 每张图片显示时长（秒）
            transition_duration: 转场时长（秒）
            add_text_overlay: 是否添加文字叠加
            text_content: 叠加的文字内容
            
        Returns:
            生成的视频路径
        """
        if not image_paths:
            raise ValueError("图片路径列表不能为空")
        
        output_path = self._output_dir / output_name
        
        try:
            # 使用 ffmpeg 创建走马灯视频
            self._create_video_with_ffmpeg(
                image_paths,
                output_path,
                duration_per_image,
                transition_duration,
                add_text_overlay,
                text_content
            )
            
            logger.info(f"视频生成成功: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.exception("视频生成失败: %s", e)
            raise

    def _copy_to_image_prompt(self, copy_text: str) -> str:
        """将文案转换为图像生成提示词"""
        # 提取文案关键信息，转换为视觉描述
        prompt = f"""Create a visually striking image for social media content.
        
Content theme: {copy_text[:200]}

Style requirements:
- Modern and eye-catching
- Suitable for Douyin/TikTok platform
- High contrast and vibrant colors
- Clean composition
- Emotional and engaging"""
        
        return prompt

    def _wanx_frame_prompt(self, copy_text: str, index: int, total: int) -> str:
        """按分镜生成中文提示词，突出大模型文生图能力。"""
        story = copy_text.strip()[:700]
        beats = [
            "近景餐桌碗筷与蒸汽，冷暖对比灯光，紧张对峙氛围，景深虚化背景",
            "中景客厅或餐厅一角，人物剪影或侧脸，情绪留白，构图偏上给标题区",
            "特写手机微光或门窗光线打在墙面，悬疑与克制",
            "远景城市夜景或楼道暖灯，孤独与拉扯感",
            "意象抽象光影、碎裂倒影、风吹窗帘，象征关系裂痕",
        ]
        lens = beats[index % len(beats)]
        return (
            f"{lens}。仿真人像纪实摄影风格，自然肤色与微表情，真实室内环境光，"
            f"电影级调色与浅景深，竖屏 9:16；可侧脸或半身，避免夸张卡通脸；"
            f"禁止水印、角标、字幕条。剧情（第{index + 1}/{total}幕）：{story}"
        )

    def _wanx_submit_task(self, prompt: str, negative_prompt: str) -> str:
        body: dict[str, Any] = {
            "model": self._wanx_model,
            "input": {
                "prompt": prompt[:1800],
                "negative_prompt": negative_prompt[:500],
            },
            "parameters": {
                "style": self._wanx_style,
                "size": self._wanx_size,
                "n": 1,
            },
        }
        headers = {
            "Authorization": f"Bearer {self._dashscope_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        r = requests.post(WANX_SUBMIT_URL, headers=headers, json=body, timeout=60)
        data = r.json()
        if r.status_code >= 400 or data.get("code"):
            err = data.get("message") or data.get("code") or r.text
            raise RuntimeError(f"万相提交失败: {err}")
        out = data.get("output") or {}
        tid = out.get("task_id")
        if not tid:
            raise RuntimeError(f"万相未返回 task_id: {data}")
        return str(tid)

    def _wanx_poll_task(self, task_id: str) -> list[str]:
        headers = {"Authorization": f"Bearer {self._dashscope_key}"}
        url = WANX_TASK_BASE + task_id
        deadline = time.time() + self._wanx_poll_sec
        while time.time() < deadline:
            r = requests.get(url, headers=headers, timeout=45)
            r.raise_for_status()
            data = r.json()
            out = data.get("output") or {}
            status = (out.get("task_status") or "").upper()
            if status == "SUCCEEDED":
                results = out.get("results") or []
                urls: list[str] = []
                for item in results:
                    if isinstance(item, dict) and item.get("url"):
                        urls.append(str(item["url"]))
                if urls:
                    return urls
                raise RuntimeError("万相成功但无图片 URL")
            if status in ("FAILED", "CANCELED", "UNKNOWN"):
                msg = out.get("message") or out.get("code") or data.get("message") or status
                raise RuntimeError(f"万相任务结束异常: {msg}")
            time.sleep(2)
        raise TimeoutError(f"万相任务超时（>{self._wanx_poll_sec}s）")

    def _generate_images_via_wanx(self, copy_text: str, num_images: int) -> list[str]:
        """通义万相异步文生图：每帧独立提示词 + 限流间隔。"""
        neg = (
            "低分辨率，模糊，畸形手指，文字水印，字幕条，角标，"
            "色情裸露，血腥暴力，二维码，整屏密集文字，"
            "卡通低龄化，3D 渲染塑料脸，与剧情无关的夸张道具与杂乱背景"
        )
        raw_n = int(num_images)
        n = max(1, min(raw_n, 6))
        if raw_n > n:
            logger.warning("通义万相限流：本次最多生成 %s 张（请求 %s 张）", n, raw_n)
        paths: list[str] = []
        for i in range(n):
            prompt = self._wanx_frame_prompt(copy_text, i, n)
            tid = self._wanx_submit_task(prompt, neg)
            urls = self._wanx_poll_task(tid)
            fn = f"wanx_{uuid.uuid4().hex[:10]}_{i + 1}.png"
            p = self._download_image(urls[0], fn)
            paths.append(str(p.resolve()))
            if i < n - 1:
                time.sleep(0.55)
        return paths

    def _download_image(self, url: str, filename: str) -> Path:
        """下载图片到本地"""
        image_path = self._output_dir / filename
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(image_path, 'wb') as f:
            f.write(response.content)
        
        return image_path

    def _generate_placeholder_images(self, num_images: int, copy_excerpt: str = "") -> list[str]:
        """生成占位图片；可把文案摘要画在图上，便于与视频内容对应。"""
        from PIL import Image, ImageDraw, ImageFont

        image_paths = []
        excerpt = (copy_excerpt or "").strip() or "（暂无文案）"
        excerpt = excerpt[:1200]
        batch = uuid.uuid4().hex[:10]

        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
        except OSError:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 26)
            except OSError:
                font = ImageFont.load_default()

        for i in range(num_images):
            img = Image.new("RGB", (1080, 1920), color=(24, 36, 48))
            d = ImageDraw.Draw(img)
            chunk = textwrap.fill(excerpt, width=22)
            header = f"第 {i + 1}/{num_images} 帧 · 占位配图"
            body = f"{header}\n\n{chunk}"
            d.multiline_text((40, 80), body, fill=(245, 248, 252), font=font, spacing=8)

            image_path = self._output_dir / f"ph_{batch}_{i + 1}.png"
            img.save(image_path)
            image_paths.append(str(image_path.resolve()))

        return image_paths

    @staticmethod
    def _seconds_to_ass_time(sec: float) -> str:
        sec = max(0.01, float(sec))
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec - h * 3600 - m * 60
        whole = int(s)
        cs = int(round((s - whole) * 100))
        if cs >= 100:
            whole += 1
            cs = 0
        return f"{h}:{m:02d}:{whole:02d}.{cs:02d}"

    @staticmethod
    def _ass_escape_line(s: str) -> str:
        return s.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")

    _MOOD_KW: dict[str, tuple[str, ...]] = {
        "sad": (
            "分手", "离婚", "离开", "失去", "遗憾", "孤独", "眼泪", "难过", "心痛",
            "失恋", "放手", "挽回", "痛苦", "崩溃", "委屈", "想念", "告别", "永别",
        ),
        "warm": (
            "治愈", "温暖", "陪伴", "谢谢", "感恩", "阳光", "拥抱", "好转", "生日",
            "家人", "孩子", "妈妈", "爸爸", "幸福", "被爱", "温柔", "安心",
        ),
        "energetic": (
            "逆袭", "创业", "奋斗", "坚持", "胜利", "冲", "突破", "自律", "年入",
            "搞钱", "翻身", "励志", "燃", "干货", "必看", "挑战", "打卡",
        ),
        "mysterious": (
            "真相", "反转", "秘密", "细思", "震惊", "居然", "没想到", "悬疑", "案件",
            "揭秘", "背后", "隐藏", "谁在", "到底",
        ),
    }

    def _infer_copy_mood(self, text: str) -> str:
        """根据标题/正文关键词粗判情绪，用于选内置配乐或配乐目录下的文件。"""
        t = (text or "")[:2000]
        scores: dict[str, int] = {k: 0 for k in ("sad", "warm", "energetic", "mysterious", "calm")}
        for mood, kws in self._MOOD_KW.items():
            for w in kws:
                if w and w in t:
                    scores[mood] += t.count(w)
        best = max(scores.values())
        if best <= 0:
            return "calm"
        tops = [m for m, s in scores.items() if s == best and m != "calm"]
        if not tops:
            return "calm"
        # 并列时优先级：伤感 > 悬疑 > 激昂 > 温暖 > 平静
        order = ("sad", "mysterious", "energetic", "warm")
        for m in order:
            if m in tops:
                return m
        return tops[0]

    def _split_text_for_n_segments(self, raw: str, n: int) -> list[str]:
        """按走马灯张数 n 切段：优先按句读切，再按字数均分。"""
        raw = (raw or "").strip()[:4000]
        n = max(1, int(n))
        if not raw:
            return [" "] * n
        if n == 1:
            return [raw]
        flat = " ".join(raw.replace("\r\n", "\n").replace("\r", "\n").split())
        parts = [p.strip() for p in re.split(r"(?<=[。！？!?…])", flat) if p.strip()]
        if len(parts) < n:
            return self._split_by_char_budget(flat, n)
        total = sum(len(p) for p in parts)
        budget = max(8, (total + n - 1) // n)
        out: list[str] = []
        buf: list[str] = []
        cur = 0
        for s in parts:
            if cur + len(s) > budget and buf and len(out) < n - 1:
                out.append("".join(buf))
                buf = [s]
                cur = len(s)
            else:
                buf.append(s)
                cur += len(s)
        out.append("".join(buf))
        while len(out) < n:
            out.append(" ")
        while len(out) > n:
            out[-2] = (out[-2] + out[-1]).strip()
            out.pop()
        return [x.strip() or " " for x in out]

    @staticmethod
    def _split_by_char_budget(text: str, n: int) -> list[str]:
        text = text.strip() or " "
        L = len(text)
        if n <= 1:
            return [text]
        base = max(1, (L + n - 1) // n)
        out: list[str] = []
        i = 0
        for seg_i in range(n):
            if seg_i == n - 1:
                out.append(text[i:])
                break
            end = min(L, i + base)
            cut = end
            if end < L:
                window = text[i : min(L, end + 16)]
                for sep in ("。", "，", "、", "；", " ", "\n"):
                    pos = window.rfind(sep, 1, len(window))
                    if pos > max(4, len(window) // 4):
                        cut = i + pos + (1 if sep != " " else 1)
                        break
            seg = text[i:cut].strip()
            out.append(seg or " ")
            i = cut if cut > i else i + 1
        while len(out) < n:
            out.append(" ")
        return out[:n]

    def _write_copy_ass(
        self,
        path: Path,
        raw: str,
        num_segments: int,
        segment_duration_sec: float,
    ) -> None:
        """底部大字幕：按每张图时长切段，多条 Dialogue 接力显示。"""
        n = max(1, int(num_segments))
        seg_dur = max(0.2, float(segment_duration_sec))
        segments = self._split_text_for_n_segments(raw, n)
        font_size = 48
        wrap_w = 18
        margin_v = 130
        events: list[str] = []
        for i in range(n):
            t0 = self._seconds_to_ass_time(i * seg_dur)
            t1 = self._seconds_to_ass_time((i + 1) * seg_dur)
            chunk = segments[i] if i < len(segments) else " "
            lines = textwrap.wrap(chunk, width=wrap_w) or [" "]
            body = r"\N".join(self._ass_escape_line(line) for line in lines)
            fade_in = min(280, int(seg_dur * 80))
            fade_out = min(380, int(seg_dur * 100))
            events.append(
                f"Dialogue: 0,{t0},{t1},SubStyle,,0,0,0,,"
                f"{{\\fad({fade_in},{fade_out})}}{body}"
            )
        events_block = "\n".join(events)
        ass = f"""[Script Info]
Title:copy_overlay
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: SubStyle,Microsoft YaHei,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H98000000,0,0,0,0,100,100,0,0,1,3,2,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{events_block}
"""
        path.write_text(ass, encoding="utf-8-sig")

    @staticmethod
    def _subtitles_filter_path(ass_path: Path) -> str:
        """ffmpeg subtitles= 滤镜内路径转义（Windows 盘符等）。"""
        p = ass_path.resolve().as_posix()
        if len(p) > 2 and p[1] == ":":
            p = p[0] + "\\:" + p[2:]
        return p.replace("'", "\\'")

    @staticmethod
    def _aeval_bgm_expr(mood: str) -> str:
        """按情绪生成 lavfi aevalsrc 表达式（无版权顾虑，仅垫底）。"""
        swell = "(0.52+0.48*sin(2*PI*0.22*t))"
        if mood == "sad":
            core = (
                "0.11*sin(2*PI*110*t)+0.09*sin(2*PI*130*t)+0.07*sin(2*PI*146*t)"
            )
            return f"{core}*{swell}"
        if mood == "warm":
            return (
                "0.12*sin(2*PI*261.63*t)+0.1*sin(2*PI*329.63*t)+0.08*sin(2*PI*392*t)"
            ) + f"*{swell}"
        if mood == "energetic":
            trem = "(0.58+0.42*sin(2*PI*3.6*t))"
            return (
                "0.1*sin(2*PI*392*t)+0.09*sin(2*PI*493.88*t)+0.07*sin(2*PI*587.33*t)"
            ) + f"*{trem}"
        if mood == "mysterious":
            return "0.12*sin(2*PI*98*t)+0.11*sin(2*PI*103*t)+0.06*sin(2*PI*65*t)"
        # calm
        return (
            "0.13*sin(2*PI*220*t)+0.1*sin(2*PI*261.63*t)+0.08*sin(2*PI*329.63*t)"
        ) + f"*{swell}"

    def _synthesize_bgm(self, duration_sec: float, mood: str) -> Path:
        """无用户配乐（或目录无匹配）时，按情绪生成不同氛围垫底音。"""
        outp = self._output_dir / f"bgm_{mood}_{uuid.uuid4().hex[:8]}.mp3"
        dur = max(10.0, min(float(duration_sec) + 2.0, 600.0))
        expr = self._aeval_bgm_expr(mood)
        lav = f"aevalsrc={expr}:d={dur}:s=44100"
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", lav, "-c:a", "libmp3lame", "-q:a", "5", str(outp)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            logger.error("内置配乐生成失败: %s", r.stderr)
            raise RuntimeError("内置配乐生成失败，请配置 MEDIA_BGM_PATH 指向本地 mp3/wav")
        logger.info("已按情绪「%s」生成内置垫底配乐", mood)
        return outp.resolve()

    def _pick_theme_bgm_from_dir(self, directory: Path, mood: str) -> Path | None:
        """目录下优先选 {mood}.mp3 / 中文别名，否则任取一个 mp3/wav。"""
        mood_l = (mood or "calm").lower()
        zh = {
            "sad": "伤感",
            "warm": "温暖",
            "energetic": "激昂",
            "mysterious": "悬疑",
            "calm": "平静",
        }
        names = [f"{mood_l}.mp3", f"{mood_l}.wav"]
        alias = zh.get(mood_l)
        if alias:
            names.extend([f"{alias}.mp3", f"{alias}.wav"])
        for name in names:
            p = directory / name
            if p.is_file():
                return p
        for ext in (".mp3", ".wav"):
            found = sorted(directory.glob(f"*{ext}"))
            for p in found:
                if p.is_file():
                    return p
        return None

    def _resolve_bgm_file(self, duration_sec: float, theme_text: str = "") -> Path:
        mood = self._infer_copy_mood(theme_text)
        if self._bgm_path:
            p = Path(self._bgm_path)
            if p.is_file():
                logger.info("使用固定配乐文件（未按关键词替换）: %s", p.name)
                return p.resolve()
            if p.is_dir():
                picked = self._pick_theme_bgm_from_dir(p, mood)
                if picked:
                    logger.info("配乐目录按文案情绪「%s」选用: %s", mood, picked.name)
                    return picked.resolve()
                logger.warning("配乐目录内无 mp3/wav，改用内置情绪配乐「%s」: %s", mood, p)
            else:
                logger.warning("MEDIA_BGM_PATH 无效，改用内置情绪配乐「%s」: %s", mood, self._bgm_path)
        return self._synthesize_bgm(duration_sec, mood)

    def _create_video_with_ffmpeg(
        self,
        image_paths: list[str],
        output_path: Path,
        duration_per_image: float,
        transition_duration: float,
        add_text_overlay: bool,
        text_content: str,
    ):
        """
        竖屏图片 concat → 可选 ASS 烧录文案 → 合并背景音乐（循环铺满，-shortest 以视频为准）。
        """
        _ = transition_duration
        n = len(image_paths)
        if n == 0:
            raise ValueError("图片路径列表不能为空")

        normalized: list[str] = []
        for p in image_paths:
            rp = Path(p).resolve()
            if not rp.is_file():
                raise FileNotFoundError(f"图片不存在: {p}")
            normalized.append(str(rp))

        t = str(float(duration_per_image))
        total_dur = float(duration_per_image) * n

        inputs: list[str] = []
        for p in normalized:
            inputs.extend(["-loop", "1", "-t", t, "-i", p])

        chain = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            "format=yuv420p,setpts=PTS-STARTPTS"
        )
        parts: list[str] = []
        for i in range(n):
            parts.append(f"[{i}:v]{chain}[v{i}]")
        concat_in = "".join(f"[v{i}]" for i in range(n))
        parts.append(f"{concat_in}concat=n={n}:v=1:a=0[outv]")
        fc_base = ";".join(parts)

        overlay = bool(add_text_overlay and (text_content or "").strip())
        if overlay:
            ass_path = self._output_dir / f"ov_{uuid.uuid4().hex[:10]}.ass"
            self._write_copy_ass(
                ass_path,
                text_content,
                num_segments=n,
                segment_duration_sec=float(duration_per_image),
            )
            esc = self._subtitles_filter_path(ass_path)
            filter_complex = fc_base + f";[outv]subtitles='{esc}':charenc=UTF-8[vout]"
            vmap = "[vout]"
        else:
            filter_complex = fc_base
            vmap = "[outv]"

        # 配乐情绪与文案对齐：即使关闭烧录字幕，仍可用传入的 text_content 推断
        bgm = self._resolve_bgm_file(total_dur, (text_content or "").strip())
        audio_idx = n

        cmd: list[str] = [
            "ffmpeg",
            "-y",
            *inputs,
            "-stream_loop",
            "-1",
            "-i",
            str(bgm),
            "-filter_complex",
            filter_complex,
            "-map",
            vmap,
            "-map",
            f"{audio_idx}:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path.resolve()),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error("ffmpeg stderr: %s", result.stderr)
            raise RuntimeError(f"视频合成失败: {result.stderr[:1200] if result.stderr else result.stdout}")


# 全局实例
media_service = MediaGenerationService()
