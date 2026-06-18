# Power Automate 흐름 만들기 (HTTP 요청 → SharePoint 저장)

봇이 보낸 JSON을 받아 SharePoint의 **기본/심화** 폴더에 파일로 저장하는 흐름입니다.
모두 **표준 커넥터**라 프리미엄 라이선스가 필요 없습니다.

> ⚠️ 저장 위치는 **여향란님의 개인 OneDrive를 공유받은 폴더**입니다. 공유받은 다른 계정으로 흐름을 만들 것이므로
> **SharePoint: 파일 만들기**(사이트 주소 = 그 개인 OneDrive)를 사용합니다.

---

## 0. 확정된 값 (이 프로젝트) ⭐

주신 폴더 URL을 분해한 결과입니다. 아래 두 값을 그대로 사용하세요.

- **사이트 주소 (Site Address)**
  ```
  https://develice-my.sharepoint.com/personal/hryeo_elicer_com
  ```
- **저장 폴더 경로 (사이트 기준)** — 끝에 과정(기본/심화)이 붙음
  ```
  /Documents/2026 스타트업AI기술인력양성(이어드림스쿨)/10. 출석관리-(양식)증명서/01. (출석) 공가처리 증빙 자료/{01.기본|02.심화}
  ```

> 이 위치는 **여향란(hryeo@elicer.com)님의 개인 OneDrive**입니다.
> 흐름은 **이 폴더에 편집 권한이 있는 계정**으로 만들어야 하고, SharePoint 커넥터의 사이트 주소는
> 목록에 안 보이므로 **"사용자 지정 값 입력"**으로 위 주소를 직접 넣습니다.

---

## 1. 새 흐름 만들기

1. <https://make.powerautomate.com> 접속 → 왼쪽 **내 흐름** → **새 흐름 → 인스턴트 클라우드 흐름**.
2. 이름 입력(예: `공가 증빙 저장`) → 트리거 선택 창에서 **건너뛰기**.
3. 검색창에 **`HTTP 요청을 받은 경우`** (영문: *When an HTTP request is received*)를 추가.

## 2. 트리거 설정 (요청 본문 스키마)

1. 트리거에서 **요청 본문 JSON 스키마**에 `flow/request-schema.json` 내용을 붙여넣기.
   (또는 **"샘플 페이로드를 사용하여 스키마 생성"** 클릭 후 `flow/sample-payload.json` 붙여넣기)
2. (선택) 톱니바퀴 ⚙️ → 설정에서 허용 HTTP 메서드를 **POST**로 제한.

> 트리거 **URL은 흐름을 저장한 뒤** 생성됩니다. 마지막에 복사합니다.

## 3. 파일 만들기 (SharePoint) — 핵심 액션

새 단계 추가 → **SharePoint** → **파일 만들기 (Create file)**.

| 입력 | 값 |
|------|----|
| **사이트 주소** | **사용자 지정 값 입력** → `https://develice-my.sharepoint.com/personal/hryeo_elicer_com` |
| **폴더 경로** | **식**으로 입력 (아래 참고) — 결과가 `…/01. (출석) 공가처리 증빙 자료/01.기본` 형태 |
| **파일 이름** | 동적 콘텐츠 **`fileName`** |
| **파일 콘텐츠** | 식(expression): `base64ToBinary(triggerBody()?['fileContentBase64'])` |

### 폴더 경로를 동적으로(기본/심화) 만드는 법 — 식(fx) 사용
실제 폴더 이름이 **`01.기본` / `02.심화`** 이므로 `if()`로 매핑합니다. (파일명엔 그대로 `기본`/`심화`가 들어감)
**폴더 경로** 칸 클릭 → **식(fx)** 탭에 아래를 붙여넣으세요:
```
concat('/Documents/2026 스타트업AI기술인력양성(이어드림스쿨)/10. 출석관리-(양식)증명서/01. (출석) 공가처리 증빙 자료/', if(equals(triggerBody()?['level'], '기본'), '01.기본', '02.심화'))
```
→ `level`이 `기본`이면 `…/01. (출석) 공가처리 증빙 자료/01.기본` 에 저장됩니다.

> ✅ 폴더 이름이 바뀌면 위 `'01.기본'`, `'02.심화'` 부분만 실제 이름과 **똑같이(띄어쓰기 포함)** 고치세요.
> ⚠️ 대상 폴더(`01.기본`/`02.심화`)가 그 안에 미리 있어야 합니다.

### "파일 콘텐츠" 식 입력 방법
입력칸 클릭 → **식(fx)** 탭 → 아래 붙여넣기 → 확인:
```
base64ToBinary(triggerBody()?['fileContentBase64'])
```

## 4. (권장) 비밀키 검증 + 응답 추가

무단 호출 차단과 봇으로의 정확한 성공/실패 회신을 위해 추가합니다.

1. **파일 만들기** 위에 **조건(Condition)** 추가:
   - `triggerBody()?['apiKey']` **다음과 같음** → `.env`의 `RELAY_SECRET` 값
2. **예(True)** 분기: 위 3번의 **파일 만들기** 이동 → 그 아래 **응답(Response)** 추가
   - 상태 코드 `200`, 본문 `{ "ok": true, "fileName": @{triggerBody()?['fileName']} }`
3. **아니요(False)** 분기: **응답(Response)** 추가
   - 상태 코드 `401`, 본문 `{ "ok": false, "error": "unauthorized" }`

> 응답 액션을 쓰면 흐름이 동기 처리되어 봇이 실제 상태코드(200/401)를 받습니다.
> 생략하면 트리거가 곧바로 `202`를 돌려주고 봇은 항상 "성공"으로 표시합니다(파일은 정상 저장됨).

## 5. 저장 후 URL 복사

1. **저장**.
2. 트리거 **HTTP 요청을 받은 경우**를 다시 열어 **HTTP POST URL** 복사.
3. 봇의 `.env` → `POWER_AUTOMATE_URL` 에 붙여넣기.

## 6. 단독 테스트 (봇 없이)

PowerShell에서:
```powershell
$body = Get-Content -Raw -Path .\flow\sample-payload.json
Invoke-RestMethod -Method Post -Uri "<여기에 POST URL>" -ContentType "application/json; charset=utf-8" -Body $body
```
→ SharePoint의 `…/01. (출석) 공가처리 증빙 자료/01.기본/` 에 1픽셀 PNG가
`06.01_기본_서울_윤소민_공가처리 증빙자료.jpg` 이름으로 생기면 성공입니다.

---

## 문제 해결

- **폴더 선택기에 공유 OneDrive가 안 보임**: 정상입니다(공유받은 개인 OneDrive는 탐색이 안 될 때가 많음).
  위 3번처럼 **식(fx)으로 폴더 경로를 직접 지정**하세요. (개인 OneDrive의 라이브러리 이름은 `Documents`)
- **403/권한 오류**: 흐름을 만든(=SharePoint 커넥터에 로그인한) 계정이 이 폴더에 **편집 권한**이 있어야 합니다.
- **같은 이름 파일이 덮어쓰기 됨**: 충돌을 피하려면 봇 `filename`에 시간 등을 덧붙이세요.
- **큰 파일 실패**: HTTP 트리거/액션 크기 제한이 있으므로 사진·PDF는 가급적 ~20MB 이하 권장.
