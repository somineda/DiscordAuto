# -*- coding: utf-8 -*-
"""
공가 증빙파일 제출 봇 (Discord 버튼/폼 → Power Automate → SharePoint)

흐름:
  1) #공가제출 채널에 [📋 공가제출] 버튼 패널을 설치 (관리자가 채널에 "!공가패널" 입력)
  2) 사용자가 버튼 클릭 → 팝업 폼(이름 / 공가 날짜 / 거점) 입력
  3) 과정(기본/심화) 드롭다운 선택
  4) "파일을 올려주세요" 안내 → 채널에 사진/PDF 업로드
  5) 봇이 파일명을 만들어 Power Automate로 전달 → SharePoint(기본/심화) 저장

파일명: 06.01_기본_서울_윤소민_공가처리 증빙자료.jpg
        ( {공가날짜MM.DD}_{과정}_{거점}_{이름}_공가처리 증빙자료.{확장자} )

※ 디스코드는 모달(팝업 폼) 안에 '파일 업로드' 칸을 넣을 수 없어, 파일만 마지막 단계로 받습니다.
⚠️ 디스코드 개발자 포털에서 "MESSAGE CONTENT INTENT"를 반드시 켜야 합니다.
"""

import os
import re
import base64
import asyncio
import logging

import discord
import aiohttp
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 설정 (.env)
# ---------------------------------------------------------------------------
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_URL")
RELAY_SECRET = os.getenv("RELAY_SECRET", "")
MAX_MB = float(os.getenv("MAX_FILE_MB", "20"))
FILE_WAIT = int(os.getenv("FILE_WAIT_SECONDS", "120"))   # 과정 선택 후 파일 업로드 대기(초)
SELECT_TIMEOUT = 300                                       # 과정 드롭다운 유효시간(초)
DELETE_UPLOAD = os.getenv("DELETE_UPLOAD", "false").strip().lower() in ("1", "true", "yes", "y")

# 감지할 채널. 쉼표로 여러 개 가능. 비우면 이름에 "공가제출"이 든 채널 사용.
CHANNEL_IDS = {int(x) for x in re.split(r"[,\s]+", os.getenv("GONGA_CHANNEL_ID", "").strip()) if x.isdigit()}
CHANNEL_NAME_KEYWORD = "공가제출"

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".pdf"}
PANEL_BUTTON_ID = "gonga:open"   # 재시작해도 동작하는 영구 버튼 custom_id

_missing = [k for k, v in {"DISCORD_TOKEN": DISCORD_TOKEN, "POWER_AUTOMATE_URL": POWER_AUTOMATE_URL}.items() if not v]
if _missing:
    raise SystemExit(f"[설정 오류] .env 파일에 다음 값을 설정하세요: {', '.join(_missing)}")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gonga-bot")

# 파일 업로드를 기다리는 중인 사용자(on_message 중복 안내 방지)
WAITING_USERS = set()


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------
def normalize_date(raw: str) -> str:
    """'MM.DD'로 정규화. (06.01, 6.1, 6/1, 0601 허용) 빈 값은 허용하지 않음."""
    nums = re.findall(r"\d+", (raw or "").strip())
    if len(nums) == 1 and len(nums[0]) == 4:
        mm, dd = int(nums[0][:2]), int(nums[0][2:])
    elif len(nums) >= 2:
        mm, dd = int(nums[0]), int(nums[1])
    else:
        raise ValueError("날짜 형식을 이해하지 못했어요. 예: `06.01`")
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        raise ValueError("날짜 범위가 올바르지 않아요. 예: `06.01`")
    return f"{mm:02d}.{dd:02d}"


def sanitize(part: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "", part).strip()
    return re.sub(r"\s+", " ", cleaned)


def build_filename(mmdd, level, base, name, ext, index, total) -> str:
    fn = f"{mmdd}_{level}_{base}_{name}_공가처리 증빙자료"
    if total > 1:           # 한 번에 여러 파일이면 이름 충돌 방지용 번호
        fn += f"_{index}"
    return fn + ext


def ext_ok(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXT


def in_target_channel(channel) -> bool:
    if CHANNEL_IDS:
        return channel.id in CHANNEL_IDS
    return CHANNEL_NAME_KEYWORD in (getattr(channel, "name", "") or "")


def panel_embed() -> discord.Embed:
    return discord.Embed(
        title="📋 공가 증빙 제출",
        description=(
            "아래 **[공가제출]** 버튼을 눌러 시작하세요.\n\n"
            "1️⃣ 이름 · 공가 날짜 · 거점 입력\n"
            "2️⃣ 과정(기본/심화) 선택\n"
            "3️⃣ 사진/PDF 파일 업로드\n\n"
            "※ 파일은 마지막 단계에서 이 채널에 올립니다."
        ),
        color=0x4E79A7,
    )


# ---------------------------------------------------------------------------
# 업로드 처리
# ---------------------------------------------------------------------------
async def upload_one(att, level, name, base, mmdd, index, total, submitted_by):
    """파일 하나를 Power Automate로 전송. (성공여부, 파일명, 오류) 반환."""
    ext = os.path.splitext(att.filename)[1].lower()
    filename = build_filename(mmdd, level, base, name, ext, index, total)
    raw = await att.read()
    b64 = base64.b64encode(raw).decode("ascii")
    payload = {
        "fileName": filename,
        "level": level,                 # 기본 / 심화 (= 저장될 하위 폴더명)
        "fileContentBase64": b64,
        "apiKey": RELAY_SECRET,
        # --- 참고용 메타데이터 ---
        "submittedBy": submitted_by,
        "base": base,
        "name": name,
        "date": mmdd,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(POWER_AUTOMATE_URL, json=payload,
                              timeout=aiohttp.ClientTimeout(total=60)) as r:
                body = await r.text()
                if r.status not in (200, 201, 202):
                    log.error("PA 오류 %s: %s", r.status, body[:300])
                    return (False, filename, "인증 실패(RELAY_SECRET)" if r.status == 401 else f"상태 {r.status}")
    except Exception:
        log.exception("PA 호출 실패")
        return (False, filename, "서버 연결 실패")
    return (True, filename, None)


async def collect_and_upload(interaction: discord.Interaction, name, base, mmdd, level):
    """과정 선택 후: 같은 사용자가 이 채널에 올린 파일을 기다렸다가 저장."""
    uid = interaction.user.id
    WAITING_USERS.add(uid)

    def check(m: discord.Message) -> bool:
        return (m.author.id == uid and m.channel.id == interaction.channel_id
                and len(m.attachments) > 0)

    try:
        msg = await interaction.client.wait_for("message", timeout=FILE_WAIT, check=check)
    except asyncio.TimeoutError:
        await interaction.edit_original_response(
            content="⌛ 시간이 초과됐어요. 다시 **[📋 공가제출]** 버튼을 눌러 주세요.")
        return
    finally:
        WAITING_USERS.discard(uid)

    valid = [a for a in msg.attachments if ext_ok(a.filename)]
    if not valid:
        await interaction.edit_original_response(
            content="❌ 사진/PDF만 제출할 수 있어요. 다시 **[📋 공가제출]** 버튼을 눌러 주세요.")
        return
    too_big = [a for a in valid if a.size > MAX_MB * 1024 * 1024]
    if too_big:
        await interaction.edit_original_response(
            content=f"❌ {MAX_MB:.0f}MB 이하 파일만 가능해요. 다시 시도해 주세요.")
        return

    await interaction.edit_original_response(content="⏳ 저장 중...")
    total = len(valid)
    results = [await upload_one(a, level, name, base, mmdd, i, total, str(interaction.user))
               for i, a in enumerate(valid, start=1)]
    oks = [f for ok, f, _ in results if ok]
    fails = [(f, e) for ok, f, e in results if not ok]

    lines = []
    if oks:
        lines.append("✅ 저장 완료:\n" + "\n".join(f"• `{f}`" for f in oks))
    if fails:
        lines.append("⚠️ 실패(관리자 문의):\n" + "\n".join(f"• `{f}` — {e}" for f, e in fails))
    await interaction.edit_original_response(content="\n\n".join(lines))
    log.info("제출 처리: %s (%s) 성공 %d/실패 %d", name, level, len(oks), len(fails))

    if DELETE_UPLOAD and not fails:
        try:
            await msg.delete()
        except discord.HTTPException:
            pass


# ---------------------------------------------------------------------------
# UI: 과정 드롭다운 → 폼 모달 → 영구 패널 버튼
# ---------------------------------------------------------------------------
class LevelSelect(discord.ui.Select):
    def __init__(self, name, base, mmdd):
        super().__init__(
            placeholder="과정을 선택하세요 (기본 / 심화)",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="기본", value="기본", emoji="📗"),
                discord.SelectOption(label="심화", value="심화", emoji="📘"),
            ],
        )
        self.g_name = name
        self.g_base = base
        self.g_mmdd = mmdd

    async def callback(self, interaction: discord.Interaction):
        level = self.values[0]
        await interaction.response.edit_message(
            content=(f"이름 **{self.g_name}** · 날짜 **{self.g_mmdd}** · 거점 **{self.g_base}** · 과정 **{level}**\n"
                     f"이제 **이 채널에 파일(사진/PDF)을 올려 주세요.** ({FILE_WAIT}초 이내)"),
            view=None,
        )
        await collect_and_upload(interaction, self.g_name, self.g_base, self.g_mmdd, level)


class LevelView(discord.ui.View):
    def __init__(self, name, base, mmdd):
        super().__init__(timeout=SELECT_TIMEOUT)
        self.add_item(LevelSelect(name, base, mmdd))


class InfoModal(discord.ui.Modal, title="공가 정보 입력"):
    name = discord.ui.TextInput(label="이름", placeholder="예: 윤소민", max_length=30, required=True)
    date = discord.ui.TextInput(label="공가 날짜 (MM.DD)", placeholder="예: 06.01", max_length=10, required=True)
    base = discord.ui.TextInput(label="거점", placeholder="예: 서울", max_length=30, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            mmdd = normalize_date(self.date.value)
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ {e}\n다시 **[📋 공가제출]** 버튼을 눌러 주세요.", ephemeral=True)
            return
        name = sanitize(self.name.value)
        base = sanitize(self.base.value)
        if not name or not base:
            await interaction.response.send_message("❌ 이름과 거점을 입력해 주세요.", ephemeral=True)
            return
        await interaction.response.send_message(
            content=f"이름 **{name}** · 날짜 **{mmdd}** · 거점 **{base}**\n아래에서 **과정**을 선택하세요 👇",
            view=LevelView(name, base, mmdd),
            ephemeral=True,
        )


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)   # 영구 버튼

    @discord.ui.button(label="공가제출", style=discord.ButtonStyle.primary,
                       emoji="📋", custom_id=PANEL_BUTTON_ID)
    async def open_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InfoModal())


# ---------------------------------------------------------------------------
# 클라이언트 / 이벤트
# ---------------------------------------------------------------------------
class GongaClient(discord.Client):
    async def setup_hook(self):
        self.add_view(PanelView())   # 재시작 후에도 버튼이 동작하도록 등록


intents = discord.Intents.default()
intents.message_content = True       # 채널 첨부/명령을 읽으려면 필요 (개발자 포털도 ON)
client = GongaClient(intents=intents)


@client.event
async def on_ready():
    where = ", ".join(map(str, CHANNEL_IDS)) if CHANNEL_IDS else f'이름에 "{CHANNEL_NAME_KEYWORD}" 포함된 채널'
    log.info("로그인 완료: %s | 감지 대상: %s", client.user, where)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
        return
    if not in_target_channel(message.channel):
        return

    # 관리자: 패널 설치
    if message.content.strip() in ("!공가패널", "!panel"):
        if message.author.guild_permissions.manage_guild:
            await message.channel.send(embed=panel_embed(), view=PanelView())
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        else:
            await message.reply("관리자만 패널을 설치할 수 있어요.", mention_author=False, delete_after=6)
        return

    # 파일을 그냥 올린 경우 안내 (진행 중인 사용자는 wait_for가 처리)
    if message.attachments and message.author.id not in WAITING_USERS:
        await message.reply("📋 **[공가제출]** 버튼을 눌러 제출을 시작해 주세요.",
                            mention_author=False, delete_after=10)


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
