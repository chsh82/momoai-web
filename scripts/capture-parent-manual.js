// -*- coding: utf-8 -*-
/**
 * 학부모 사용 설명서용 화면 스크린샷 자동 캡처.
 *
 * momoai.kr에 학부모 계정으로 로그인해서, 설명서 섹션별 화면을
 * mobile(390x844)/desktop(1280x800) 두 뷰포트로 각각 캡처한다.
 * 로그인 정보는 .env(MANUAL_BASE_URL/MANUAL_PARENT_ID/MANUAL_PARENT_PW)에서만
 * 읽는다 - 코드에 절대 적지 않는다.
 *
 * 실행: npm run capture:manual
 *       npm run capture:manual -- --only=01-1   (특정 항목만)
 *
 * 셀렉터는 대부분 getByRole/getByText(텍스트 기반)를 쓴다 - UI가 조금
 * 바뀌어도(클래스명 변경 등) 깨지지 않게 하기 위함. 라우트는 전부
 * app/parent_portal/routes.py, templates/base.html(사이드바 링크 텍스트)을
 * 직접 읽어서 확인한 실제 값이다(추측 없음).
 *
 * 실패해도 멈추지 않는다 - 한 화면이 실패해도 note에 사유를 남기고
 * 다음 화면으로 계속 진행한다. 마지막에 성공/스킵/실패 요약을 찍는다.
 */
'use strict';

require('dotenv').config();
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = process.env.MANUAL_BASE_URL;
const PARENT_ID = process.env.MANUAL_PARENT_ID;
const PARENT_PW = process.env.MANUAL_PARENT_PW;

if (!BASE_URL || !PARENT_ID || !PARENT_PW) {
  console.error(
    '.env에 MANUAL_BASE_URL / MANUAL_PARENT_ID / MANUAL_PARENT_PW를 먼저 채워주세요.\n' +
    '(.env.example 참고 - 이 스크립트는 자격증명을 코드에 절대 적지 않고 .env에서만 읽습니다.)'
  );
  process.exit(1);
}

const OUT_DIR = path.join(__dirname, '..', 'docs', 'manual-screenshots');
const VIEWPORTS = {
  mobile: { width: 390, height: 844 },
  desktop: { width: 1280, height: 800 },
};

const WAIT_AFTER_LOAD_MS = 300;

// CLI: --only=01-1,02-2 로 특정 항목만, --viewport=mobile 로 특정 뷰포트만
const onlyArg = process.argv.find((a) => a.startsWith('--only='));
const onlyIds = onlyArg ? onlyArg.replace('--only=', '').split(',').map((s) => s.trim()) : null;
const viewportArg = process.argv.find((a) => a.startsWith('--viewport='));
const onlyViewport = viewportArg ? viewportArg.replace('--viewport=', '').trim() : null;

/** 결과 요약용 */
const results = []; // { id, name, viewport, status: 'ok'|'skipped'|'failed', note }

function record(id, name, viewport, status, note) {
  results.push({ id, name, viewport, status, note: note || '' });
  const mark = status === 'ok' ? '✅' : status === 'skipped' ? '⏭️ ' : '❌';
  console.log(`${mark} [${viewport}] ${id} ${name}${note ? ' - ' + note : ''}`);
}

async function waitSettled(page) {
  try {
    await page.waitForLoadState('networkidle', { timeout: 15000 });
  } catch (e) {
    // networkidle 타임아웃은 흔함(폴링/웹소켓 등) - 무시하고 계속 진행
  }
  await page.waitForTimeout(WAIT_AFTER_LOAD_MS);
}

async function shoot(page, viewport, id, name, filename, opts) {
  opts = opts || {};
  const dir = path.join(OUT_DIR, viewport);
  fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, filename);
  await page.screenshot({ path: filePath, fullPage: opts.fullPage !== false });
  record(id, name, viewport, 'ok', path.relative(OUT_DIR, filePath));
}

async function login(page) {
  await page.goto(new URL('/auth/login', BASE_URL).toString());
  await page.getByLabel('이메일').fill(PARENT_ID);
  await page.getByLabel('비밀번호').fill(PARENT_PW);
  await page.getByRole('button', { name: '로그인' }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/auth/login'), { timeout: 15000 });
  await waitSettled(page);
}

async function openMobileSidebar(page) {
  // base.html에 mobileMenuOpen 토글 버튼이 두 개 있다: 54번 줄은
  // class="hidden"인 죽은 폴백 버튼이고, 1376번 줄이 실제 헤더 햄버거
  // 버튼이다. :visible로 걸러서 실제 보이는 버튼만 클릭한다.
  const toggle = page.locator('button[\\@click*="mobileMenuOpen"]:visible').first();
  if (await toggle.count()) {
    await toggle.click();
    await page.waitForTimeout(400); // Alpine x-collapse 애니메이션
  }
}

async function clickFirstChildFrom(page, linkGetter) {
  // "자녀 선택" 인덱스 페이지에서 첫 번째 자녀 카드/링크를 클릭해 상세로 이동.
  const link = linkGetter(page).first();
  await link.waitFor({ state: 'visible', timeout: 8000 });
  await link.click();
  await waitSettled(page);
}

/**
 * 각 항목: { id, name, kind: 'path' | 'action', path?, run?(page) }
 * kind='path'면 그냥 goto 후 캡처. kind='action'이면 run(page, viewport)에서
 * 직접 이동/클릭/캡처까지 다 처리(다단계 화면용).
 */
function buildShots() {
  return [
    // ── 01. 로그인 및 기본 설정 ──────────────────────────────
    {
      id: '01-1', name: '로그인 화면',
      kind: 'action',
      run: async (page, viewport) => {
        await page.goto(new URL('/auth/login', BASE_URL).toString());
        await waitSettled(page);
        await shoot(page, viewport, '01-1', '로그인 화면', '01-1_로그인_화면.png');
      },
    },
    { id: '01-2', name: '로그인 후 첫 화면(대시보드)', kind: 'path', path: '/parent/' },
    { id: '01-3', name: '내 정보 화면', kind: 'path', path: '/profile/' },
    { id: '01-4', name: '비밀번호 변경 화면', kind: 'path', path: '/profile/change-password' },

    // ── 02. 앱 설치 및 알림 ──────────────────────────────────
    {
      id: '02-1', name: '사이드바 열린 상태(전체 메뉴)',
      kind: 'action',
      run: async (page, viewport) => {
        await page.goto(new URL('/parent/', BASE_URL).toString());
        await waitSettled(page);
        if (viewport === 'mobile') await openMobileSidebar(page);
        // 고정(fixed) 오버레이 사이드바라 fullPage 스크롤 캡처 대신 뷰포트
        // 그대로 찍는다(전체 페이지로 찍으면 사이드바가 상단에만 남고
        // 스크롤된 나머지 영역엔 안 보일 수 있음).
        await shoot(page, viewport, '02-1', '사이드바 열린 상태', '02-1_사이드바_전체메뉴.png', { fullPage: false });
      },
    },
    { id: '02-2', name: '알림 목록 화면', kind: 'path', path: '/notifications/' },
    {
      id: '02-3', name: '홈 화면에 추가(iOS/Android)',
      kind: 'action',
      run: async (page, viewport) => {
        record('02-3', '홈 화면에 추가(iOS/Android)', viewport, 'skipped', '수동 촬영 필요 - OS 자체 UI라 자동 캡처 불가');
      },
    },

    // ── 03. 자녀 연결 ────────────────────────────────────────
    {
      id: '03-1', name: '사이드바 자녀 관리 메뉴',
      kind: 'action',
      run: async (page, viewport) => {
        await page.goto(new URL('/parent/', BASE_URL).toString());
        await waitSettled(page);
        if (viewport === 'mobile') await openMobileSidebar(page);
        await shoot(page, viewport, '03-1', '사이드바 자녀 관리 메뉴', '03-1_자녀연결_메뉴.png', { fullPage: false });
      },
    },
    { id: '03-2', name: '자녀 연결 입력 폼', kind: 'path', path: '/parent/link-child' },
    { id: '03-3', name: '연결된 자녀 목록', kind: 'path', path: '/parent/children' },

    // ── 04. 자녀 출결 현황 ───────────────────────────────────
    {
      id: '04-1', name: '출결 현황(자녀 탭 + 수업별 출석률 요약)',
      kind: 'action',
      run: async (page, viewport) => {
        await page.goto(new URL('/parent/attendance', BASE_URL).toString());
        await waitSettled(page);
        await clickFirstChildFrom(page, (p) => p.locator('a[href*="/parent/attendance/"]'));
        await shoot(page, viewport, '04-1', '출결 현황', '04-1_출결_현황.png');
      },
    },
    {
      id: '04-2', name: '세션별 상세 출석 내역',
      kind: 'action',
      run: async (page, viewport) => {
        // 이 앱은 세션별 상세가 04-1과 같은 화면에 함께 표시되고 별도
        // URL이 없다(templates/parent/attendance.html 확인) - 같은 화면을
        // 그대로 다시 찍되 로그에 사유를 남긴다.
        await page.goto(new URL('/parent/attendance', BASE_URL).toString());
        await waitSettled(page);
        await clickFirstChildFrom(page, (p) => p.locator('a[href*="/parent/attendance/"]'));
        await shoot(page, viewport, '04-2', '세션별 상세 출석 내역', '04-2_세션별_상세.png');
        results[results.length - 1].note += ' (04-1과 동일 화면 - 별도 상세 페이지 없음, 한 화면에 세션별 내역 포함)';
      },
    },

    // ── 05. 과제 및 첨삭 ─────────────────────────────────────
    { id: '05-1', name: '제출한 에세이 목록', kind: 'path', path: '/parent/essays' },
    {
      id: '05-2', name: '첨삭 완료된 글 상세(점수/코멘트/수정내용)',
      kind: 'action',
      run: async (page, viewport) => {
        await page.goto(new URL('/parent/essays', BASE_URL).toString());
        await waitSettled(page);
        // main 안으로 범위를 좁힌다 - 사이드바에도 "/parent/essays/submit"
        // 링크가 있어서 범위를 안 좁히면 그게 먼저 잡힘(DOM 순서상 사이드바가 먼저).
        await clickFirstChildFrom(page, (p) => p.locator('main a[href*="/parent/essays/"]'));
        // 알림 권한 배너 문구("첨삭 완료, 공지, 문자 등 알림을...")에도 "첨삭 완료"가
        // 부분 문자열로 들어있어 exact 매치로 좁혀야 실제 상태 배지만 잡힌다.
        const done = page.getByText('첨삭 완료', { exact: true }).first();
        if (!(await done.count())) {
          record('05-2', '첨삭 완료된 글 상세', viewport, 'skipped', '첨삭 완료된 글이 없어 건너뜀');
          return;
        }
        // "첨삭 완료" 텍스트가 붙은 카드 전체(가장 가까운 <a>)를 클릭
        const card = done.locator('xpath=ancestor::a[1]');
        await card.first().click();
        await waitSettled(page);
        await shoot(page, viewport, '05-2', '첨삭 완료된 글 상세', '05-2_첨삭_상세.png');
      },
    },
    { id: '05-3', name: '글 제출하기 폼', kind: 'path', path: '/parent/essays/submit' },

    // ── 06. 학습 교재 및 동영상 ──────────────────────────────
    { id: '06-1', name: '학습 교재 목록', kind: 'path', path: '/parent/materials' },
    { id: '06-2', name: '학습 동영상 목록', kind: 'path', path: '/parent/videos' },

    // ── 07. 평가 정보 ────────────────────────────────────────
    { id: '07-1', name: '독서논술 MBTI 결과', kind: 'path', path: '/parent/reading-mbti' },
    { id: '07-2', name: '주간 평가', kind: 'path', path: '/parent/weekly-evaluation' },
    { id: '07-3', name: 'ACE 분기 평가 리포트', kind: 'path', path: '/parent/ace-evaluation' },

    // ── 08. 보강수업 신청 ────────────────────────────────────
    {
      id: '08-1', name: '보강 가능한 수업 목록',
      kind: 'action',
      run: async (page, viewport) => {
        await page.goto(new URL('/parent/makeup-classes', BASE_URL).toString());
        await waitSettled(page);
        await clickFirstChildFrom(page, (p) => p.locator('a[href*="/parent/makeup-classes/"]'));
        await shoot(page, viewport, '08-1', '보강 가능한 수업 목록', '08-1_보강_목록.png');
      },
    },
    {
      id: '08-2', name: '사유 입력 폼',
      kind: 'action',
      run: async (page, viewport) => {
        await page.goto(new URL('/parent/makeup-classes', BASE_URL).toString());
        await waitSettled(page);
        await clickFirstChildFrom(page, (p) => p.locator('a[href*="/parent/makeup-classes/"]'));
        const applyBtn = page.getByRole('button', { name: '신청하기' }).first();
        if (!(await applyBtn.count())) {
          record('08-2', '사유 입력 폼', viewport, 'skipped', '보강 신청 가능한 수업이 없어 폼을 열 수 없음');
          return;
        }
        await applyBtn.click();
        await page.waitForTimeout(300);
        // 폼만 제출하지 않고 화면만 캡처(실제 신청 액션은 절대 실행 안 함)
        await shoot(page, viewport, '08-2', '사유 입력 폼', '08-2_사유_입력폼.png');
      },
    },

    // ── 09. 결제 관리 ────────────────────────────────────────
    { id: '09-1', name: '수업별 납부 현황', kind: 'path', path: '/parent/payments' },

    // ── 10. 게시판 ───────────────────────────────────────────
    { id: '10-1', name: '공지사항', kind: 'path', path: '/parent/announcements' },
    { id: '10-2', name: '선생님 피드백', kind: 'path', path: '/parent/feedback' },
    { id: '10-3', name: '문의 게시판', kind: 'path', path: '/inquiry/' },
  ];
}

async function runForViewport(browser, viewport, shots) {
  const context = await browser.newContext({ viewport: VIEWPORTS[viewport] });
  const page = await context.newPage();

  try {
    await login(page);
  } catch (e) {
    record('01-1', '로그인', viewport, 'failed', `로그인 실패 - ${e.message}`);
    await context.close();
    return; // 로그인 실패하면 이 뷰포트의 나머지는 전부 의미 없음
  }

  for (const shot of shots) {
    if (onlyIds && !onlyIds.includes(shot.id)) continue;
    if (shot.id === '01-1') continue; // 로그인 화면은 로그인 전에 별도 처리(아래)
    try {
      if (shot.kind === 'path') {
        await page.goto(new URL(shot.path, BASE_URL).toString());
        await waitSettled(page);
        const filename = `${shot.id}_${shot.name.replace(/[\\/:*?"<>|]/g, '')}.png`;
        await shoot(page, viewport, shot.id, shot.name, filename);
      } else {
        await shot.run(page, viewport);
      }
    } catch (e) {
      record(shot.id, shot.name, viewport, 'failed', e.message);
    }
  }

  await context.close();
}

async function main() {
  const shots = buildShots();
  const browser = await chromium.launch();

  for (const viewport of Object.keys(VIEWPORTS)) {
    if (onlyViewport && viewport !== onlyViewport) continue;
    if (onlyIds && !onlyIds.includes('01-1') && onlyIds.every((id) => !shots.find((s) => s.id === id))) continue;

    console.log(`\n=== ${viewport} (${VIEWPORTS[viewport].width}x${VIEWPORTS[viewport].height}) ===`);

    // 01-1(로그인 화면)은 로그인하기 전 상태라 별도로 먼저 찍는다.
    if (!onlyIds || onlyIds.includes('01-1')) {
      const loginShot = shots.find((s) => s.id === '01-1');
      const context = await browser.newContext({ viewport: VIEWPORTS[viewport] });
      const page = await context.newPage();
      try {
        await loginShot.run(page, viewport);
      } catch (e) {
        record('01-1', '로그인 화면', viewport, 'failed', e.message);
      }
      await context.close();
    }

    await runForViewport(browser, viewport, shots);
  }

  await browser.close();

  console.log('\n=== 캡처 결과 요약 ===');
  const ok = results.filter((r) => r.status === 'ok').length;
  const skipped = results.filter((r) => r.status === 'skipped').length;
  const failed = results.filter((r) => r.status === 'failed').length;
  console.log(`성공 ${ok}건 / 스킵 ${skipped}건 / 실패 ${failed}건 (총 ${results.length}건)\n`);

  if (skipped > 0) {
    console.log('--- 스킵된 화면 ---');
    results.filter((r) => r.status === 'skipped').forEach((r) => console.log(`  [${r.viewport}] ${r.id} ${r.name} - ${r.note}`));
  }
  if (failed > 0) {
    console.log('--- 실패한 화면 ---');
    results.filter((r) => r.status === 'failed').forEach((r) => console.log(`  [${r.viewport}] ${r.id} ${r.name} - ${r.note}`));
  }

  process.exit(failed > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error('스크립트 실행 중 예상치 못한 오류:', e);
  process.exit(1);
});
