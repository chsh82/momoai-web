/* 글쓰기 튜토리얼 - 전달된 샘플 HTML의 <script>를 옮긴 것.
   바뀐 점(1단계 지시서 6절):
   - 하드코딩된 LESSON 상수 제거 -> #lessonData script 태그에서 파싱
   - LESSON.quiz -> lesson.questions (0단계 JSON 키 이름에 맞춤, buildQuiz/renderResult 포함 전부)
   - /api/answer의 question_id는 인덱스가 아니라 문항 id(예: elem-c1-l1-q3)
   - /api/complete 응답의 points로 마일리지 표시, points_awarded=false면 그 줄 자체를 숨김
     (renderResult()의 mileN = n*5 같은 클라이언트 계산 마일리지는 만들지 않음)
   - CSRF 토큰 처리 없음(이 리포는 CSRFProtect가 전역으로 꺼져 있고 기존 JSON API도 안 씀)
   - ○/✕ 도장(.stamp, settle())과 버튼 배열 순회 방식은 샘플 그대로 유지 */

const lesson = JSON.parse(document.getElementById('lessonData').textContent);
const HOME_URL = window.TUTORIAL_HOME_URL || '/tutorial/';

/* ===== 원고지 렌더러 (샘플 gpEl/parseRow 그대로) ===== */
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
    if(!res || !res.ok) return {points_awarded:false, points:0};
    return await res.json();
  }catch(e){
    return {points_awarded:false, points:0};
  }
}

/* ===== 상태 ===== */
let answered={};          // qi -> {correct}

function go(id){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('on'));
  document.getElementById(id).classList.add('on');
  window.scrollTo(0,0);
}
function goHome(){ window.location.href = HOME_URL; }

/* ===== 레슨 시작 ===== */
function startLesson(){
  answered={};
  removeFinBar();
  buildDots();
  buildCards();
  buildQuiz();
  const ct=document.getElementById('cardTotal'); if(ct) ct.textContent=lesson.cards.length;
  go('learn');
}

function buildDots(){
  const d=document.getElementById('lessonDots'); d.innerHTML='';
  const total=lesson.questions.length;
  for(let i=0;i<total;i++){ const el=document.createElement('i'); el.id='dot'+i; d.appendChild(el); }
  document.getElementById('dot0').classList.add('now');
}
function refreshDots(){
  lesson.questions.forEach((q,i)=>{
    const el=document.getElementById('dot'+i);
    el.classList.remove('now','done');
    if(answered[i]) el.classList.add('done');
  });
  const nextI=lesson.questions.findIndex((q,i)=>!answered[i]);
  if(nextI>=0) document.getElementById('dot'+nextI).classList.add('now');
}

/* ===== 카드 ===== */
function buildCards(){
  const box=document.getElementById('cards'); box.innerHTML='';
  lesson.cards.forEach((c)=>{
    const card=document.createElement('div'); card.className='card';
    let h='<div class="cn"><span class="b">'+c.no+'</span><h3>'+c.title+'</h3>'
         +(c.star?'<span class="star">★ 자주 틀려요</span>':'')+'</div>';
    h+='<div class="say">'+c.say+'</div>';
    if(c.why) h+='<div class="why"><span class="q">?</span><div><b>왜 그럴까요?</b> '+c.why+'</div></div>';
    card.innerHTML=h;
    c.grids.forEach(g=>{
      const w=document.createElement('div'); w.className='gpwrap';
      const tg=document.createElement('div'); tg.className='gptag '+g.tone;
      tg.textContent=(g.tone==='bad'?'✕ ':'○ ')+g.tag;
      w.appendChild(tg); w.appendChild(gpEl(g));
      card.appendChild(w);
    });
    if(c.remember){
      const r=document.createElement('div'); r.className='remember';
      r.innerHTML='<span class="momo">모모</span><div><b>기억해요</b> '+c.remember+'</div>';
      card.appendChild(r);
    }
    box.appendChild(card);
  });
}

/* ===== 퀴즈 ===== */
function buildQuiz(){
  const box=document.getElementById('quiz'); box.innerHTML='';
  lesson.questions.forEach((q,qi)=>{
    const el=document.createElement('div'); el.className='q'; el.id='q'+qi;
    const head=document.createElement('div'); head.className='qhead';
    head.innerHTML='<span class="qno">문제 '+(qi+1)+'</span>'
      +'<span class="qtype">'+(q.type==='fill'?'칸 채우기':'고르기')+'</span>';
    el.appendChild(head);
    const qt=document.createElement('div'); qt.className='qtext'; qt.textContent=q.q;
    el.appendChild(qt);

    if(q.type==='choice') buildChoice(el,q,qi);
    else buildFill(el,q,qi);

    const why=document.createElement('div'); why.className='why-box'; why.id='why'+qi;
    el.appendChild(why);
    box.appendChild(el);
  });
}

function buildChoice(el,q,qi){
  const opts=document.createElement('div'); opts.className='opts';
  const stamp=document.createElement('div'); stamp.className='stamp'; stamp.id='stamp'+qi;
  opts.appendChild(stamp);
  const btns=[];
  q.opts.forEach((o,oi)=>{
    const b=document.createElement('button'); b.className='opt'; b.type='button';
    const k=document.createElement('span'); k.className='key'; k.textContent=['가','나','다','라'][oi];
    b.appendChild(k); b.appendChild(gpEl(o));
    b.addEventListener('click',()=>{
      if(answered[qi]) return;
      const ok=(oi===q.a);
      btns.forEach((c,ci)=>{
        c.disabled=true;
        if(ci===q.a) c.classList.add('right');
        else if(ci===oi) c.classList.add('wrong');
        else c.classList.add('dim');
      });
      settle(qi,ok,q);
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
  const stamp=document.createElement('div'); stamp.className='stamp'; stamp.id='stamp'+qi;
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

  const check=document.createElement('button'); check.className='big'; check.style.width='100%';
  check.style.margin='4px 0 0'; check.textContent='확인하기';
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
    settle(qi,ok,q);
  });
  el.appendChild(check);

  paint();
}

function settle(qi,ok,q){
  answered[qi]={correct:ok, ruleName:q.ruleName, ruleNo:q.ruleNo};
  const stamp=document.getElementById('stamp'+qi);
  if(stamp){
    stamp.classList.add(ok?'y':'n');
    stamp.innerHTML = ok
      ? '<svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="20"/></svg>'
      : '<svg viewBox="0 0 52 52"><line x1="14" y1="14" x2="38" y2="38"/><line x1="38" y1="14" x2="14" y2="38"/></svg>';
    stamp.classList.add('on');
  }
  const why=document.getElementById('why'+qi);
  why.innerHTML='<span class="verdict '+(ok?'y':'n')+'">'+(ok?'맞았어요! ':'다시 볼까요. ')+'</span>'+q.why;
  why.classList.add('on');
  refreshDots();

  // 문항 저장은 best-effort - 실패해도 화면 진행을 막지 않는다.
  post('/tutorial/api/answer', {
    lesson_id: lesson.id,
    question_id: q.id,
    rule_no: q.ruleNo,
    correct: ok,
  });

  const allDone=lesson.questions.every((x,i)=>answered[i]);
  if(allDone) showResultButton();
  why.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function showResultButton(){
  let bar=document.getElementById('finBar');
  if(bar) return;
  bar=document.createElement('div'); bar.id='finBar'; bar.style.marginTop='18px';
  const b=document.createElement('button'); b.className='big'; b.style.width='100%'; b.style.margin='0';
  b.textContent='레슨 결과 보기 🎉';
  b.addEventListener('click',renderResult);
  bar.appendChild(b);
  document.getElementById('quiz').appendChild(bar);
}
function removeFinBar(){ const b=document.getElementById('finBar'); if(b) b.remove(); }

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
  const mileEl = document.getElementById('mileLine');
  const data = await postComplete({lesson_id: lesson.id, score: n, total: total});
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
