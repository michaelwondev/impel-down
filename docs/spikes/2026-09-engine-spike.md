# 엔진 spike 결과 (2026-09-11, macOS arm64, mitmproxy 12.2.3)

- tarball sha256: `0a09ee3b82569e8985aff8186e4792618b8e5d0c766098db093d09a87d4b013a` (`mitmproxy-12.2.3-macos-arm64.tar.gz`, 54MB)
- tarball 구조: `mitmproxy.app/` 번들 하나. mitmdump는 `mitmproxy.app/Contents/MacOS/mitmdump`, Python 3.14가 `Contents/Frameworks`에 내장.
	- 실행 파일만 떼어 옮기면 프레임워크 상대 경로가 깨진다 — `.app`을 통째로 둔다 (spec·plan에 반영).
- 기동: 정상. `--version` → `Mitmproxy: 12.2.3 binary / Python: 3.14.4`. curl로 받은 파일이라 격리 속성 없음, 서명 경고 없음.
- 연결별 통과·복호화: 기대대로.
	- 규칙 밖 호스트: 인증서 지정 없이 `200` → 터널 통과 (로그에 server connect만, GET 없음).
	- 규칙 호스트: CA 지정 시 `403` + `blocked` 본문. CA 없이는 curl exit 60(인증서 오류) → 복호화 확인.
	- SNI 속성 표기: `data.context.client.sni` 그대로 통함.
- 프록시 적용: 활성 서비스 (측정 전 — 보스 실측)
- 엔진 죽은 상태 트래픽: 브라우저 (측정 전) · python urllib (측정 전)
- 프록시 설정 변경 시 관리자 인증: (측정 전)
- Safari 경유: Private Relay 켬 (측정 전) · 끔 (측정 전)
- Chrome QUIC: (측정 전)
- spec 수정 필요: 엔진 런타임을 "독립 실행 파일"에서 "`mitmproxy.app` 번들"로 (반영함). 그 외는 Step 3·4 결과 후 판단.
