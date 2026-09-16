/* 글쓰기 튜토리얼 - 2단계(페이지 넘김 + 코스1 전체 + 코스2·3 신설).
   1단계 대비 바뀐 점:
   - 학습 카드·퀴즈 문항을 한 화면에 다 쌓지 않고 하나씩만 보여준다(renderCard/
     renderQuestion). 카드는 진입 즉시 "다음"이 활성화되고, 문항은 답을 확인한
     뒤에만 "다음 문제"가 활성화된다(학습 상태를 눈으로 확인하고 넘어가자는 요청).
   - 카드가 두 가지 콘텐츠 스키마를 지원한다: 원고지 칸 비교(c.grids, 코스1)와
     평문 문장 비교(c.examples, 코스2·3 - 원고지가 필요 없는 콘텐츠라서 새로 추가).
   - 퀴즈 opts도 grid-spec({rows})과 평문({text}) 둘 다 지원(buildChoice 분기).
   - /api/complete 페이로드에 track/course를 추가로 보낸다 - 라우트가 더 이상
     트랙/코스를 서버 상수로 고정하지 않고 요청에서 받으므로(트랙/코스 확장).
   - ○/✕ 도장(.stamp)과 gpEl 원고지 렌더러는 1단계 그대로 유지. */

const lesson = JSON.parse(document.getElementById('lessonData').textContent);
const HOME_URL = window.TUTORIAL_HOME_URL || '/tutorial/';
const TRACK = window.TUTORIAL_TRACK || '';
const COURSE = window.TUTORIAL_COURSE || '';

/* ===== 원고지 렌더러 (1단계 그대로) ===== */
function parseRow(s){
  const cells=[]; let i=0;
  while(i<s.length){
    let hl=false, mid=false;
    if(s[i]==='!'){ hl=true; i++; }
    else if(s[i]==='#'){ hl=true; mid=true; i++; }
    let t;
    if(s[i]==='{'){ const j=s.indexOf('}',i); t=s.slice(i+1,j); i=j+1; }
    else { t=s[i]; i++; }
    if(t===' ') t='';
    cells.push({t:t,hl:hl,mid:mid});
  }
  return cells;
}
function gpEl(spec){
  const rows=spec.rows.map(parseRow);
  const n=spec.n || rows.reduce((m,r)=>Math.max(m,r.length),0);
  const wrap=document.createElement('div');
  wrap.className='gp'+(spec.tone?' '+spec.tone:'');
  rows.forEach(function(r){
    const rowEl=document.createElement('div');
    rowEl.className='gp-row';
    rowEl.style.gridTemplateColumns='repeat('+n+', var(--cell))';
    for(let k=0;k<n;k++){
      const c=r[k]||{t:'',hl:false,mid:false};
      const sp=document.createElement('span');
      sp.textContent=c.t;
      const cls=[];
      if(c.t.length>1) cls.push('two');
      if(!c.mid && (c.t==='.'||c.t===',')) cls.push('bl');
      if(c.t==='“') cls.push('qo');
      if(c.t==='”') cls.push('qc');
      if(c.hl) cls.push('hl');
      if(cls.length) sp.className=cls.join(' ');
      rowEl.appendChild(sp);
    }
    wrap.appendChild(rowEl);
  });
  return wrap;
}

/* ===== 평문 예문 렌더러 (코스2·3 - 원고지 칸이 필요 없는 카드용) ===== */
function exampleEl(ex){
  const wrap=document.createElement('div'); wrap.className='ex-wrap';
  const tag=document.createElement('div'); tag.className='ex-tag '+ex.tone;
  tag.textContent = ex.label ? ex.label : (ex.tone==='bad' ? '✕ 이렇게 쓰면 안 돼요' : '○ 이렇게 써요');
  const box=document.createElement('div'); box.className='ex-box '+ex.tone;
  box.textContent=ex.text;
  wrap.appendChild(tag); wrap.appendChild(box);
  return wrap;
}

/* ===== 서버 저장 (best-effort - 실패해도 화면 진행은 막지 않는다) ===== */
function post(url, body){
  return fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'same-origin',
    body: JSON.stringify(body),
  }).catch(() => null);
}

async function postComplete(body){
  try{
    const res = await post('/tutorial/api/complete', body);
    if(!res || !res.ok) return {points_awarded:false, points:0, saved:false};
    if(res.status===204) return {points_awarded:false, points:0, saved:true}; // 학생 외 역할 - 저장 대상 아님(정상)
    const data = await res.json();
    return Object.assign({saved:true}, data);
  }catch(e){
    return {points_awarded:false, points:0, saved:false};
  }
}

/* ===== 상태 ===== */
let answered={};   // qi -> {correct, ruleName, ruleNo, type, selectedIndex?, fillState?}
let cardIdx=0;
let quizIdx=0;

function go(id){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('on'));
  document.getElementById(id).classList.add('on');
  window.scrollTo(0,0);
}
function goHome(){ window.location.href = HOME_URL; }

/* ===== 레슨 시작 ===== */
function startLesson(){
  answered={};
  cardIdx=0;
  quizIdx=0;
  buildDots();
  renderCard(0);
  go('learn');
}

function buildDots(){
  const d=document.getElementById('lessonDots'); d.innerHTML='';
  const total=lesson.questions.length;
  for(let i=0;i<total;i++){ const el=document.createElement('i'); el.id='dot'+i; d.appendChild(el); }
}
function refreshDots(){
  lesson.questions.forEach((q,i)=>{
    const el=document.getElementById('dot'+i);
    el.classList.remove('now','done');
    if(answered[i]) el.classList.add('done');
    if(i===quizIdx) el.classList.add('now');
  });
}

/* ===== 카드 (학습 화면 - 한 번에 한 장) ===== */
function cardBodyHtml(c){
  let h='<div class="cn"><span class="b">'+c.no+'</span><h3>'+c.title+'</h3>'
       +(c.star?'<span class="star">★ 자주 틀려요</span>':'')+'</div>';
  h+='<div class="say">'+c.say+'</div>';
  return h;
}
function renderCard(idx){
  cardIdx=idx;
  const c=lesson.cards[idx];
  const box=document.getElementById('cards'); box.innerHTML='';
  const card=document.createElement('div'); card.className='card';
  card.innerHTML=cardBodyHtml(c);

  if(c.grids){
    c.grids.forEach(g=>{
      // 원고지를 왼쪽에 고정하고 설명 태그를 오른쪽에 둔다(칸 위치가
      // 태그 유무/길이에 따라 흔들리지 않게) - 폭이 좁아 같이 못 들어가면
      // flex-wrap으로 태그가 아래로 자연스럽게 내려간다.
      const w=document.createElement('div'); w.className='gpwrap';
      const tg=document.createElement('div'); tg.className='gptag '+g.tone;
      tg.textContent=(g.tone==='bad'?'✕ ':'○ ')+g.tag;
      w.appendChild(gpEl(g)); w.appendChild(tg);
      card.appendChild(w);
    });
  }
  if(c.examples){
    c.examples.forEach(ex=> card.appendChild(exampleEl(ex)));
  }
  if(c.why){
    // "?" 아이콘 대신 "왜 그럴까요?" 문구 자체를 배지에 넣는다 - 옆
    // 설명과 같은 줄 높이(align-items:center)로 맞춰서 보여준다.
    const w=document.createElement('div'); w.className='why';
    w.innerHTML='<span class="q">왜 그럴까요?</span><div>'+c.why+'</div>';
    card.appendChild(w);
  }
  if(c.remember){
    const r=document.createElement('div'); r.className='remember';
    r.innerHTML='<span class="momo">모모</span><div><b>기억해요</b> '+c.remember+'</div>';
    card.appendChild(r);
  }
  box.appendChild(card);

  const counter=document.getElementById('cardCounter');
  if(counter) counter.textContent=(idx+1)+' / '+lesson.cards.length;

  const prevBtn=document.getElementById('cardPrevBtn');
  const nextBtn=document.getElementById('cardNextBtn');
  prevBtn.disabled = (idx===0);
  const isLast = idx===lesson.cards.length-1;
  nextBtn.textContent = isLast ? '✏️ 퀴즈 풀기 →' : '다음 ›';
}
function cardPrev(){ if(cardIdx>0) renderCard(cardIdx-1); }
function cardNext(){
  if(cardIdx<lesson.cards.length-1){ renderCard(cardIdx+1); }
  else { startQuiz(); }
}

/* ===== 퀴즈 (한 번에 한 문제) ===== */
function startQuiz(){
  quizIdx=0;
  renderQuestion(0);
  go('quiz-screen');
}

function renderQuestion(idx){
  quizIdx=idx;
  const q=lesson.questions[idx];
  const box=document.getElementById('quiz'); box.innerHTML='';

  const el=document.createElement('div'); el.className='q'; el.id='qActive';
  const head=document.createElement('div'); head.className='qhead';
  head.innerHTML='<span class="qno">문제 '+(idx+1)+'</span>'
    +'<span class="qtype">'+(q.type==='fill'?'칸 채우기':'고르기')+'</span>';
  el.appendChild(head);
  const qt=document.createElement('div'); qt.className='qtext'; qt.textContent=q.q;
  el.appendChild(qt);

  if(q.type==='choice') buildChoice(el,q,idx);
  else buildFill(el,q,idx);

  const why=document.createElement('div'); why.className='why-box'; why.id='whyActive';
  el.appendChild(why);
  box.appendChild(el);

  refreshDots();
  updateQuizNav();

  if(answered[idx]) applyAnsweredState(idx,q);
}

function updateQuizNav(){
  const prevBtn=document.getElementById('quizPrevBtn');
  const nextBtn=document.getElementById('quizNextBtn');
  prevBtn.disabled = (quizIdx===0);
  const isLast = quizIdx===lesson.questions.length-1;
  const isAnswered = !!answered[quizIdx];
  nextBtn.disabled = !isAnswered;
  nextBtn.textContent = isLast ? '결과 보기 🎉' : '다음 문제 ›';
}
function quizPrev(){ if(quizIdx>0) renderQuestion(quizIdx-1); }
function quizNext(){
  if(!answered[quizIdx]) return;
  if(quizIdx<lesson.questions.length-1){ renderQuestion(quizIdx+1); }
  else { renderResult(); }
}

/* 옵션이 원고지 grid-spec({rows})인지 평문({text})인지에 따라 다르게 그린다
   - 코스1은 grid-spec, 코스2·3은 평문 문장이라 원고지 칸이 필요 없다. */
function optionContentEl(o){
  if(o && o.rows) return gpEl(o);
  const span=document.createElement('span'); span.className='opt-text';
  span.textContent = o.text||''; return span;
}

function buildChoice(el,q,qi){
  const opts=document.createElement('div'); opts.className='opts';
  const stamp=document.createElement('div'); stamp.className='stamp'; stamp.id='stampActive';
  opts.appendChild(stamp);
  const btns=[];
  q.opts.forEach((o,oi)=>{
    const b=document.createElement('button'); b.className='opt'; b.type='button';
    const k=document.createElement('span'); k.className='key'; k.textContent=['가','나','다','라'][oi];
    b.appendChild(k); b.appendChild(optionContentEl(o));
    b.addEventListener('click',()=>{
      if(answered[qi]) return;
      const ok=(oi===q.a);
      btns.forEach((c,ci)=>{
        c.disabled=true;
        if(ci===q.a) c.classList.add('right');
        else if(ci===oi) c.classList.add('wrong');
        else c.classList.add('dim');
      });
      settle(qi,ok,q,{selectedIndex:oi});
    });
    btns.push(b);
    opts.appendChild(b);
  });
  el.appendChild(opts);
}

function buildFill(el,q,qi){
  const state=Array(q.n).fill(null);
  let sel=0;
  const target=document.createElement('div'); target.className='fill-target';
  const stamp=document.createElement('div'); stamp.className='stamp'; stamp.id='stampActive';
  target.appendChild(stamp);
  const grid=gpEl({n:q.n, rows:['']});
  target.appendChild(grid);
  el.appendChild(target);

  const hint=document.createElement('div'); hint.className='fill-hint';
  hint.textContent='칸을 고른 뒤 아래 조각을 눌러 넣어요. 다시 누르면 지워져요.';
  el.appendChild(hint);

  const pieceBox=document.createElement('div'); pieceBox.className='pieces';
  el.appendChild(pieceBox);

  function cells(){ return [...grid.querySelectorAll('.gp-row span')]; }
  function paint(){
    cells().forEach((sp,i)=>{
      sp.className=''; sp.textContent = state[i]||'';
      if(state[i] && state[i].length>1) sp.classList.add('two');
      if(state[i]!==null) sp.classList.add('filled');
      if(i===sel) sp.classList.add('sel');
    });
    const used={};
    state.forEach(v=>{ if(v!==null) used[v]=(used[v]||0)+1; });
    [...pieceBox.children].forEach(p=>{
      const v=p.dataset.v; const cap=Number(p.dataset.cap);
      const cnt=state.filter(x=>x===v).length;
      p.classList.toggle('used', cnt>=cap);
    });
  }
  cells().forEach((sp,i)=>{
    sp.style.cursor='pointer';
    sp.addEventListener('click',()=>{ if(answered[qi])return;
      if(state[i]!==null){ state[i]=null; sel=i; } else sel=i; paint(); });
  });

  const caps={};
  q.pieces.forEach(v=>caps[v]=(caps[v]||0)+1);
  Object.keys(caps).forEach(v=>{
    const p=document.createElement('button'); p.className='piece'; p.type='button';
    p.dataset.v=v; p.dataset.cap=caps[v];
    p.textContent = v===' '?'␣':v;
    if(v===' ') p.classList.add('blank');
    p.addEventListener('click',()=>{ if(answered[qi])return;
      if(state[sel]!==null){ const nx=state.indexOf(null); if(nx>=0) sel=nx; }
      state[sel]=v;
      const nx=state.indexOf(null); if(nx>=0) sel=nx;
      paint();
    });
    pieceBox.appendChild(p);
  });

  const check=document.createElement('button'); check.className='big'; check.id='fillCheckBtn';
  check.style.width='100%'; check.style.margin='4px 0 0'; check.textContent='확인하기';
  check.addEventListener('click',()=>{
    if(answered[qi]) return;
    let ok=true;
    cells().forEach((sp,i)=>{
      sp.classList.remove('sel');
      const want=q.answer[i]||''; const got=state[i]||'';
      if(got===want){ if(got) sp.classList.add('ok'); }
      else { sp.classList.add('err'); ok=false; }
    });
    check.disabled=true;
    [...pieceBox.children].forEach(p=>p.style.pointerEvents='none');
    settle(qi,ok,q,{fillState:state.slice()});
  });
  el.appendChild(check);

  paint();
}

/* 이전 문제로 돌아왔을 때 - 이미 답한 상태를 다시 계산하지 않고 그대로
   복원한다(정답/오답 판정을 다시 하거나 서버에 또 저장하지 않는다). */
function applyAnsweredState(qi,q){
  const rec=answered[qi];
  if(q.type==='choice'){
    const btns=[...document.querySelectorAll('#qActive .opt')];
    btns.forEach((b,ci)=>{
      b.disabled=true;
      if(ci===q.a) b.classList.add('right');
      else if(ci===rec.selectedIndex) b.classList.add('wrong');
      else b.classList.add('dim');
    });
  } else {
    const cells=[...document.querySelectorAll('#qActive .gp-row span')];
    cells.forEach((sp,i)=>{
      const want=q.answer[i]||''; const got=(rec.fillState&&rec.fillState[i])||'';
      sp.textContent=got;
      if(got.length>1) sp.classList.add('two');
      if(got) sp.classList.add('filled');
      if(got===want){ if(got) sp.classList.add('ok'); } else sp.classList.add('err');
    });
    const check=document.getElementById('fillCheckBtn');
    if(check) check.disabled=true;
    document.querySelectorAll('#qActive .piece').forEach(p=>p.style.pointerEvents='none');
  }
  const stamp=document.getElementById('stampActive');
  if(stamp){
    stamp.classList.add(rec.correct?'y':'n');
    stamp.innerHTML = rec.correct
      ? '<svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="20"/></svg>'
      : '<svg viewBox="0 0 52 52"><line x1="14" y1="14" x2="38" y2="38"/><line x1="38" y1="14" x2="14" y2="38"/></svg>';
    stamp.classList.add('on');
  }
  const why=document.getElementById('whyActive');
  why.innerHTML='<span class="verdict '+(rec.correct?'y':'n')+'">'+(rec.correct?'맞았어요! ':'다시 볼까요. ')+'</span>'+q.why;
  why.classList.add('on');
}

function settle(qi,ok,q,extra){
  answered[qi]=Object.assign({correct:ok, ruleName:q.ruleName, ruleNo:q.ruleNo, type:q.type}, extra||{});
  const stamp=document.getElementById('stampActive');
  if(stamp){
    stamp.classList.add(ok?'y':'n');
    stamp.innerHTML = ok
      ? '<svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="20"/></svg>'
      : '<svg viewBox="0 0 52 52"><line x1="14" y1="14" x2="38" y2="38"/><line x1="38" y1="14" x2="14" y2="38"/></svg>';
    stamp.classList.add('on');
  }
  const why=document.getElementById('whyActive');
  why.innerHTML='<span class="verdict '+(ok?'y':'n')+'">'+(ok?'맞았어요! ':'다시 볼까요. ')+'</span>'+q.why;
  why.classList.add('on');
  refreshDots();
  updateQuizNav();

  // 문항 저장은 best-effort - 실패해도 화면 진행을 막지 않는다.
  post('/tutorial/api/answer', {
    lesson_id: lesson.id,
    question_id: q.id,
    rule_no: q.ruleNo,
    correct: ok,
  });

  why.scrollIntoView({behavior:'smooth',block:'nearest'});
}

/* ===== 결과 ===== */
async function renderResult(){
  const total=lesson.questions.length;
  const n=Object.values(answered).filter(a=>a.correct).length;
  document.getElementById('scoreN').textContent=n;
  document.getElementById('scoreT').textContent=total;
  document.getElementById('medal').textContent = n===total?'🏆': n>=total/2?'🎉':'🌱';

  const list=document.getElementById('reviewList'); list.innerHTML='';
  let wrong=Object.values(answered).filter(a=>!a.correct);
  if(wrong.length===0){
    list.innerHTML='<div class="row good"><span class="rn">✓</span><div>모든 규정을 다 맞혔어요. 훌륭해요!</div></div>';
  } else {
    wrong.forEach(a=>{
      const r=document.createElement('div'); r.className='row';
      r.innerHTML='<span class="rn">'+a.ruleNo+'</span><div>'+a.ruleName+' — 카드를 다시 볼까요?</div>';
      list.appendChild(r);
    });
  }

  go('result');

  // 완료 저장 + 마일리지는 서버 응답을 받은 뒤에 채운다(클라이언트 계산 없음).
  lastResultPayload = { lesson_id: lesson.id, score: n, total: total, track: TRACK, course: COURSE };
  await tryCompleteSave();
}

/* 진도 저장이 실패(세션 만료·네트워크 오류 등)하면 화면은 이미 "완료"로 보이지만
   서버엔 기록이 안 남아 다음 코스가 계속 잠겨있는 문제가 있었다 - 실패를 화면에
   드러내고 재시도할 수 있게 한다. */
let lastResultPayload = null;
async function tryCompleteSave(){
  const mileEl = document.getElementById('mileLine');
  const warnEl = document.getElementById('saveWarn');
  const data = await postComplete(lastResultPayload);
  if(!data.saved){
    warnEl.hidden = false;
    mileEl.hidden = true;
    return;
  }
  warnEl.hidden = true;
  if(data.points_awarded && data.points > 0){
    document.getElementById('mileN').textContent = data.points;
    mileEl.hidden = false;
  } else {
    mileEl.hidden = true;
  }
}

/* 이 페이지 자체가 이미 "레슨 화면"이므로(홈은 별도 라우트), 로드되자마자
   학습 화면(#learn)으로 초기화한다. */
startLesson();
