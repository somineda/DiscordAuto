# -*- coding: utf-8 -*-
"""디스코드 연결 점검용 (로그인되면 정보 출력 후 즉시 종료). 진단용이며 봇 본체와 무관."""
import os
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CID = (os.getenv("GONGA_CHANNEL_ID") or "").strip()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"[OK] 로그인 성공: {client.user} (id={client.user.id})")
    print(f"[OK] 가입된 서버 {len(client.guilds)}개")
    for g in client.guilds:
        print(f"     - {g.name} (id={g.id})")
    if CID.isdigit():
        ch = client.get_channel(int(CID))
        if ch is not None:
            print(f"[OK] 대상 채널 인식됨: #{getattr(ch, 'name', '?')} (서버: {getattr(ch.guild, 'name', '?')})")
        else:
            print(f"[경고] 채널 ID {CID} 를 못 찾음 → 봇이 그 채널의 서버에 초대됐는지 / View 권한 확인")
    else:
        print("[정보] GONGA_CHANNEL_ID 가 비어 있음 (이름에 '공가제출' 든 채널 자동 인식 모드)")
    await client.close()


async def main():
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=45)
    except asyncio.TimeoutError:
        print("[실패] 45초 내 로그인되지 않음 (네트워크/토큰 확인)")
        await client.close()
    except discord.LoginFailure:
        print("[실패] 토큰이 올바르지 않습니다 → .env 의 DISCORD_TOKEN 다시 확인")
    except discord.PrivilegedIntentsRequired:
        print("[실패] MESSAGE CONTENT INTENT 가 꺼져 있습니다 → 개발자 포털 Bot 화면에서 켜고 Save")


asyncio.run(main())
