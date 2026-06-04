# -*- coding: utf-8 -*-
"""
Claude API 키 상태 및 연결 점검.

사용법:
    python check_claude_api.py
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for env_file in ['.env.production', '.env']:
    env_path = os.path.join(BASE_DIR, env_file)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        print(f"[환경설정] {env_file} 로드 완료")
        break

api_key = os.environ.get('ANTHROPIC_API_KEY', '')
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY 환경변수가 없습니다.")
    sys.exit(1)

masked = api_key[:8] + '...' + api_key[-4:]
print(f"[API 키] {masked}  (길이: {len(api_key)}자)")

print("\n[연결 테스트] claude-sonnet-4-6 에 최소 요청 전송 중...")

try:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    import time
    t0 = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16,
        messages=[{"role": "user", "content": "ping"}]
    )
    elapsed = time.time() - t0

    print(f"  상태:      OK ({elapsed:.2f}초)")
    print(f"  응답:      {response.content[0].text!r}")
    print(f"  stop_reason: {response.stop_reason}")
    usage = response.usage
    print(f"  input_tokens:  {usage.input_tokens}")
    print(f"  output_tokens: {usage.output_tokens}")
    cache_read = getattr(usage, 'cache_read_input_tokens', 0)
    cache_write = getattr(usage, 'cache_creation_input_tokens', 0)
    if cache_read:
        print(f"  cache_read:    {cache_read}")
    if cache_write:
        print(f"  cache_write:   {cache_write}")
    print("\n결론: API 키 정상, 연결 이상 없음.")

except anthropic.AuthenticationError as e:
    print(f"\nERROR [인증 실패]: API 키가 유효하지 않거나 만료됨.")
    print(f"  상세: {e}")
    print("  → Anthropic 콘솔에서 키 확인/재발급 필요: https://console.anthropic.com")

except anthropic.RateLimitError as e:
    print(f"\nWARN [Rate Limit]: 요청 한도 초과 상태.")
    print(f"  상세: {e}")
    print("  → 잠시 후 재시도하거나 Anthropic 콘솔에서 사용량 확인 필요.")

except anthropic.PermissionDeniedError as e:
    print(f"\nERROR [권한 없음]: 해당 모델 또는 기능 접근 불가.")
    print(f"  상세: {e}")

except anthropic.APIStatusError as e:
    print(f"\nERROR [API 오류 {e.status_code}]: {e}")

except Exception as e:
    print(f"\nERROR [예상치 못한 오류]: {type(e).__name__}: {e}")
