# Power Automate 흐름 만들기 (HTTP 요청 → SharePoint 저장)

봇이 보낸 JSON을 받아 SharePoint의 **기본/심화** 폴더에 파일로 저장하는 흐름입니다.
모두 **표준 커넥터**라 프리미엄 라이선스가 필요 없습니다.

> ⚠️ 원래 계획은 "OneDrive for Business: 파일 만들기"였지만, 저장 위치가
> **공유/SharePoint 라이브러리**(`여향란의 파일 …`)이므로 **SharePoint: 파일 만들기**를 사용합니다.
> (다른 사람이 공유했거나 팀즈/SharePoint 라이브러리가 동기화된 폴더는 OneDrive 커넥터로
> 안정적으로 쓰기 어렵습니다.)

---

## 0. 먼저: 저장 위치의 "사이트 주소"와 "폴더 경로" 알아내기 ⭐가장 중요

SharePoint 커넥터는 로컬 경로(`C:\...\OneDrive - 엘리스\...`)가 아니라 **웹 주소**가 필요합니다.

1. 브라우저에서 해당 폴더를 엽니다.
   - 파일 탐색기에서 `10. 출석관리-(양식)증명서` 폴더(또는 상위 폴더)를 **우클릭 → "온라인에서 보기"**, 또는
   - OneDrive/SharePoint 웹에서 직접 해당 폴더로 이동.
2. 주소창 URL을 복사합니다. 두 가지 형태 중 하나입니다.

   **(A) 팀/사이트 라이브러리인 경우**
   ```
   https://elice.sharepoint.com/sites/<사이트이름>/Shared%20Documents/...
   ```
   → **사이트 주소** = `https://elice.sharepoint.com/sites/<사이트이름>`

   **(B) 누군가의 OneDrive를 공유받은 경우** (`여향란의 파일`이면 이쪽일 가능성이 큼)
   ```
   https://elice-my.sharepoint.com/personal/<여향란계정아이디>/_layouts/15/onedrive.aspx?id=%2Fpersonal%2F<...>%2FDocuments%2F...&...
   ```
   → **사이트 주소** = `https://elice-my.sharepoint.com/personal/<여향란계정아이디>`

3. **폴더 경로**는 아래 1~4단계에서 폴더 선택기(폴더 아이콘)로 클릭만 하면 자동으로 채워지므로
   직접 입력할 필요는 없습니다. (선택기에 안 보이면 맨 아래 "문제 해결" 참고)

> 💡 `elice`는 예시입니다. 실제 테넌트 이름은 위 URL에서 확인하세요.

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
| **사이트 주소** | 0번에서 찾은 사이트 주소 선택 (목록에 없으면 **사용자 지정 값 입력**) |
| **폴더 경로** | 아래 방법 참고 — 끝이 `…/10. 출석관리-(양식)증명서/{level}` 이 되도록 |
| **파일 이름** | 동적 콘텐츠 **`fileName`** |
| **파일 콘텐츠** | 식(expression): `base64ToBinary(triggerBody()?['fileContentBase64'])` |

### 폴더 경로를 동적으로(기본/심화) 만드는 법
1. **폴더 경로**의 폴더 아이콘을 눌러 `… / 10. 출석관리-(양식)증명서` 까지 **탐색해서 선택**.
   (이러면 라이브러리 이름·경로가 자동으로 정확히 입력됩니다.)
2. 입력칸을 **텍스트 편집 모드(`</>` 또는 "T" 토글)**로 바꾼 뒤, 맨 끝에 `/` 를 추가하고
   동적 콘텐츠 **`level`** 을 삽입.
   → 최종 경로 예: `/Shared Documents/…/10. 출석관리-(양식)증명서/기본`

> ✅ 봇이 보내는 `level` 값은 정확히 **`기본`** / **`심화`** 입니다.
> 실제 하위 폴더 이름이 다르면(예: `01.기본`) 봇의 `Choice value`를 그 이름과 똑같이 바꾸세요.

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
→ SharePoint의 `…/10. 출석관리-(양식)증명서/기본/` 에 1픽셀 PNG가
`06.01_기본_서울_윤소민_공가처리 증빙자료.jpg` 이름으로 생기면 성공입니다.

---

## 문제 해결

- **폴더 선택기에 공유 라이브러리가 안 보임**: "사이트 주소"를 0번의 사용자 지정 값으로 넣은 뒤,
  "폴더 경로"도 텍스트 모드로 직접 입력. 경로는 사이트 기준 상대 경로
  (예: `/Shared Documents/…/10. 출석관리-(양식)증명서/기본`).
  영문 라이브러리는 보통 `Shared Documents`, 한글 테넌트는 `Documents`/`문서`일 수 있습니다.
- **403/권한 오류**: 흐름을 만든 계정이 해당 SharePoint 폴더에 **편집 권한**이 있어야 합니다.
- **같은 이름 파일이 덮어쓰기 됨**: 충돌을 피하려면 봇 `filename`에 시간 등을 덧붙이세요.
- **큰 파일 실패**: HTTP 트리거/액션 크기 제한이 있으므로 사진·PDF는 가급적 ~20MB 이하 권장.
