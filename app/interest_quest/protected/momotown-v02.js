/* Final display-only festival overlay. FORM/V12/scorer remain canonical. */
const FESTIVAL_FRAME=MOMOTOWN_V02.form_version;
const festivalScenes=new Map(MOMOTOWN_V02.scenes.map(s=>[s.source_item_id,s]));
const festivalOptions=new Map(MOMOTOWN_V02.scenes.flatMap(s=>s.options.map(o=>[o.source_option_id,o.proposed_text])));
function festivalCurrent(s){return s?.response_frame_version===FESTIVAL_FRAME;}
const festivalBase={init,question,pause,greeting,intro,guide,reportHtml,reportModel,recordFrame};
init=function(){festivalBase.init();session.response_frame_version=FESTIVAL_FRAME;session.copy_version=MOMOTOWN_V02.copy_version;render();};
greeting=function(){let h=festivalBase.greeting();return h.replace(esc(GREETING[greetingIndex]),esc(greetingIndex===0?MOMOTOWN_V02.opening.admin_first:MOMOTOWN_V02.opening.student[greetingIndex])).replace('너의 다음 이야기를 찾아서','모모타운 축제에 온 걸 환영해!');};
intro=function(){return festivalBase.intro().replaceAll('모모의 이야기 탐험단','모모타운 축제').replace('좋아하는 일을 따라,','모모타운 축제에서,').replace('32개의 이야기에서 내가 맡고 싶은 활동을 골라 출발해요.','아홉 마을이 모인 하나의 타운에서, 하고 싶은 활동을 골라요.');};
guide=function(){return festivalBase.guide().replace('잘한다고 느끼는 일이나 해보고 싶은 일 중, 내가 맡고 싶은 활동 하나를 골라요.','장면마다 내가 해 보고 싶은 활동 하나를 골라요.').replace('다음 탐험도 찾아봐요.','축제에서 만난 관심을 돌아봐요.');};
question=function(){let h=festivalBase.question();if(!festivalCurrent(session))return h;const q=FORM.items[session.cursor],c=festivalScenes.get(q.id);h=h.replace(esc(q.title),esc(c.title)).replace(esc(q.scene),esc(c.scene));const oldQuestion=session.response_frame_version===FORM_V12?POLICY.response_frame.common_question:q.question;h=h.replace(esc(oldQuestion),esc(c.question));for(const o of q.options)h=h.replace(esc(o.text),esc(festivalOptions.get(o.id)));h=h.replace('</p><div class="scene-source">','</p><div class="scene-source">');return h.replace('<p id="scene-copy">'+esc(c.scene)+'</p>','<p id="scene-copy">'+esc(c.scene)+'</p><p class="festival-dialogue">'+esc(c.dialogue)+'</p>').replace('<p class="q-help" id="question-help">내가 맡고 싶은 활동 하나를 골라 주세요.</p>','<p class="q-help sr-only" id="question-help">네 가지 중 하나를 선택하세요.</p>');};
pause=function(){if(!festivalCurrent(session))return festivalBase.pause();const c=MOMOTOWN_V02.chapters[Math.floor(session.cursor/8)],previous=MOMOTOWN_V02.chapters[c.chapter-2];return crumb(c.title)+`<section class="chapter-screen paper" data-chapter="${c.chapter}"><div class="chapter-art" style="--scene:url('${placeImage(c.chapter===2?'PLAZA':'MOMO_AMPHITHEATRE')}')"><div class="chapter-hosts">${characterImage('momo','','모모')}</div></div><div class="chapter-copy"><div class="eyebrow">${c.chapter}장 · ${session.cursor} / 32 기록</div><h1>${esc(c.title)}</h1>${previous?`<p>${esc(previous.closing)}</p>`:''}<p>${esc(c.intro)}</p><div class="actions chapter-actions">${button('다음 이야기로 →','continueJourney()',false,true)}</div><p class="micro">각 장은 여덟 장면이에요. 체험은 이야기 속 상황이며 실제 과제를 수행하지 않아요.</p></div></section>`;};
recordFrame=function(s){return festivalCurrent(s)?'하고 싶은 활동을 고른 관심 전용 기록이에요. 이전 안내 버전과 같은 척도로 비교하지 않아요.':festivalBase.recordFrame(s);};
/* Only replace evidence in a derived report model; never canonical source rows. */
reportModel=function(s){const m=festivalBase.reportModel(s);if(!m||!festivalCurrent(s))return m;const copy=e=>({...e,title:festivalScenes.get(e.item_id||e.source_item_id)?.title||e.title,option_text:festivalOptions.get(e.option_id)||e.option_text});m.reps=m.reps.map(r=>({...r,evidence:r.evidence.map(copy)}));m.paths=m.paths.map(p=>({...p,row:{...p.row,evidence:p.row.evidence.map(copy)},evidence:p.evidence.map(copy)}));return m;};
reportHtml=function(m){let h=festivalBase.reportHtml(m);if(!festivalCurrent(m.s))return h;for(const q of FORM.items){h=h.replaceAll(esc(q.title),esc(festivalScenes.get(q.id).title));for(const o of q.options)h=h.replaceAll(esc(o.text),esc(festivalOptions.get(o.id)));}return h;};
document.querySelector('.brand strong').textContent='모모타운 축제';
document.querySelector('.brand small').textContent='아홉 마을, 하나의 타운 · 하고 싶은 일을 찾는 방문';
document.querySelector('.footer').innerHTML='<p>모모타운 축제 · 하고 싶은 일을 찾는 여행<br>진행 중인 선택은 기록 파일로 백업할 수 있어요.</p>';
window.festivalIdentity={mode:location.protocol==='file:'?'LOCAL_ADMIN_PREVIEW':'pending',display_name:null};
const FESTIVAL_API='/student/interest-quest';
const festivalDisplayRender=render,festivalContentInit=init,festivalContentGreeting=greeting;
function festivalIdentityReady(){return ['student','admin_preview','LOCAL_ADMIN_PREVIEW'].includes(window.festivalIdentity.mode);}
function festivalModeLabel(){return window.festivalIdentity.mode==='LOCAL_ADMIN_PREVIEW'?'로컬 관리자 미리보기 · 학생 데이터로 저장하지 않아요.':window.festivalIdentity.mode==='admin_preview'?'관리자 미리보기 · 학생 데이터로 저장하지 않아요.':'학생 모드 · 완료한 응답과 선호는 서버 저장 성공을 확인해요.';}
function festivalIdentityBlock(){return `<section class="paper identity-unavailable"><h1>학생 신원을 확인하고 있어요</h1><p role="alert" tabindex="-1">${window.festivalIdentity.mode==='unavailable'?'신원을 확인할 수 없어요. 연결이나 계정 정보를 확인한 뒤 다시 시도해 주세요.':'확인 전에는 새 방문을 시작할 수 없어요.'}</p>${button('신원 확인 다시 시도','loadFestivalContext()')}</section>`;}
async function loadFestivalContext(){
 if(location.protocol==='file:')return;
 window.festivalIdentity={mode:'pending',display_name:null};render(false);
 try{const response=await fetch(FESTIVAL_API+'/context',{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error('context');const c=await response.json();if(!['student','admin_preview'].includes(c.mode)||c.form_version!==FESTIVAL_FRAME||c.copy_version!==MOMOTOWN_V02.copy_version||(c.mode==='student'&&(typeof c.display_name!=='string'||!c.display_name.trim()||!c.csrf_token)))throw Error('context');window.festivalIdentity={...c,display_name:c.mode==='student'?c.display_name:null};}
 catch(e){window.festivalIdentity={mode:'unavailable',display_name:null};}
 render(false);document.querySelector('.identity-unavailable [role=alert]')?.focus();
}
init=function(){if(!festivalIdentityReady()){render();return;}festivalContentInit();};
greeting=function(){let h=festivalContentGreeting();if(greetingIndex===0&&window.festivalIdentity.mode==='student')h=h.replace(esc(MOMOTOWN_V02.opening.admin_first),esc(MOMOTOWN_V02.opening.student[0].replace('{학생실명}',window.festivalIdentity.display_name)));return h;};
render=function(focus=true){if(!festivalIdentityReady()){$('#main').innerHTML=festivalIdentityBlock();return;}festivalDisplayRender(focus);if(['greeting','intro','guide'].includes(view))$('#main').insertAdjacentHTML('afterbegin',`<p class="festival-mode" role="status">${festivalModeLabel()}</p>`);};
render(false);
/* Context is loaded after all final overlay hooks are installed. */

const festivalResultBase={finish,choose,render,printResult,printUnified,result,storyTie};
function festivalFingerprint(s){return JSON.stringify([s.response_frame_version,s.values]);}
function festivalState(s){if(!s)return null;const fingerprint=festivalFingerprint(s);if(s.festival?.fingerprint!==fingerprint)s.festival={fingerprint,seen:{},preference:null,acknowledged:false,selected:null,submitting:false};return s.festival;}
function festivalActive(){return view==='report'?(reportReturn==='sample'?sampleSession:session):dataForResult().s;}
function festivalCandidates(s){return reportModel(s)?.paths.map(p=>p.row.domain_id)||[];}
function festivalMissing(s){const f=festivalState(s);return festivalCandidates(s).flatMap((id,i)=>['intro','study'].filter(section=>!f.seen[id]?.includes(section)).map(section=>({id,section,tab:i===0?(section==='intro'?'core':'connections'):i===1?'second':'third'})));}
function festivalAllowed(s){const f=festivalState(s);return !!(festivalCurrent(s)&&s.result&&festivalCandidates(s).length===3&&!festivalMissing(s).length&&f.acknowledged&&f.preference?.selected_village_id&&festivalCandidates(s).includes(f.preference.selected_village_id));}
finish=function(){if(!festivalIdentityReady()||!session)return;festivalState(session);festivalResultBase.finish();};
choose=function(id){if(!session)return;const q=FORM.items[session.cursor];if(q.options.some(o=>o.id===id)&&session.values[session.cursor]!==id){session.festival=null;$('#print-root').innerHTML='';}festivalResultBase.choose(id);};
function festivalVisitMissing(tab){closeDialog();view='result';setTab(tab);}
function festivalGate(s=festivalActive()){
 if(!s?.result)return false;
 if(!festivalCurrent(s)){openDialog('이전 안내 버전의 기록',`<p>${esc(recordFrame(s))}</p><p>이 기록을 관심 전용 새 응답으로 바꾸거나 선호와 합치지 않아요. 새 축제 방문에서 다시 선택해 주세요.</p>${button('새 방문 시작하기','closeDialog();init()')}`);return false;}
 if(festivalAllowed(s))return true;
 const missing=festivalMissing(s);
 if(missing.length){openDialog('세 마을을 먼저 만나 보자',`<p role="alert">아직 만나지 않은 마을의 안내와 공부 화면이 있어요. 화면을 둘러본 기록이며, 읽고 이해했는지 평가하지 않아요.</p><div class="actions">${[...new Map(missing.map(x=>[x.tab,x])).values()].map(x=>button(esc(villageName(x.id))+(x.tab==='connections'?' 공부 보기':' 만나기'),`festivalVisitMissing('${x.tab}')`)).join('')}</div>`);return false;}
 festivalPreferenceDialog(s);return false;
}
function festivalPreferenceDialog(s=festivalActive()){
 const f=festivalState(s),ids=festivalCandidates(s);
 openDialog('마음에 드는 마을 고르기',`<section id="festival-preference"><h2>${esc(MOMOTOWN_V02.preference.question)}</h2><p>${esc(MOMOTOWN_V02.preference.instruction)}</p><p class="festival-mode">${festivalModeLabel()}</p><div class="preference-candidates" role="group" aria-label="세 마을 중 한 곳 선택">${ids.map(id=>`<button type="button" class="preference-card" data-village="${id}" aria-pressed="${f.selected===id}" onclick="festivalSelectPreference('${id}')" ${f.submitting?'disabled':''}><img src="${placeImage(id)}" alt=""><b>${esc(villageName(id))}</b></button>`).join('')}</div><p id="festival-save-status" role="alert" tabindex="-1">${esc(f.error||'')}</p><button class="btn" id="festival-confirm" onclick="festivalConfirmPreference()" ${!f.selected||f.submitting?'disabled':''}>${f.submitting?'저장 확인 중…':esc(MOMOTOWN_V02.preference.cta)}</button></section>`);
}
function festivalSelectPreference(id){const s=festivalActive(),f=festivalState(s);if(f.submitting||!festivalCandidates(s).includes(id))return;if(f.selected!==id)f.preference_request_id=null;f.selected=id;f.error='';document.querySelectorAll('.preference-card').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.village===id)));$('#festival-confirm').disabled=false;}
function festivalOpenReport(s){closeDialog();reportReturn=s===sampleSession?'sample':'result';view='report';render();}
async function festivalConfirmPreference(){const s=festivalActive(),f=festivalState(s);if(f.submitting||!festivalCandidates(s).includes(f.selected)||festivalMissing(s).length)return;f.preference={selected_village_id:f.selected,analysis_revision:'ADMIN_PREVIEW',displayed_villages_in_order:festivalCandidates(s),origin:'ADMIN_PREVIEW'};f.acknowledged=true;festivalOpenReport(s);}
printResult=function(){const s=festivalActive();if(festivalGate(s))festivalOpenReport(s);};
printUnified=function(){if(festivalGate(festivalActive()))festivalResultBase.printUnified();};
/* Ctrl+P bypasses printUnified: never trust cached material from another visit. */
addEventListener('beforeprint',()=>{
 const root=$('#print-root'),s=festivalActive();root.innerHTML='';
 if(!festivalIdentityReady()||!s||!festivalAllowed(s))return;
 root.innerHTML=reportHtml(reportModel(s));
 const appendix=root.querySelector('.response-appendix');
 if(appendix){if($('#include-appendix')?.checked)appendix.open=true;else appendix.remove();}
});
storyTie=function(m){return `<p class="story-note">${esc(MOMOTOWN_V02.tie_copy)}</p>`;};
result=function(){const s=dataForResult().s;return festivalResultBase.result()+(!festivalCurrent(s)?`<p class="banner" role="status">${esc(recordFrame(s))}</p>`:'');};
render=function(focus=true){
 if(!festivalIdentityReady())return festivalResultBase.render(focus);
 if(view==='report'&&!festivalAllowed(festivalActive())){view=reportReturn==='sample'?'sample':'result';festivalResultBase.render(focus);festivalGate(festivalActive());return;}
 festivalResultBase.render(focus);
 if(!['result','sample'].includes(view))return;
 const s=festivalActive();if(!festivalCurrent(s)||!s?.result)return;const f=festivalState(s),ids=festivalCandidates(s);
 const sections=resultTab==='core'?[[ids[0],['intro']]]:resultTab==='connections'?[[ids[0],['study']]]:resultTab==='second'?[[ids[1],['intro','study']]]:resultTab==='third'?[[ids[2],['intro','study']]]:[];
 for(const [id,shown] of sections){if(!id)continue;const actual=shown.filter(section=>document.querySelector(section==='intro'?`.village-discovery[data-village="${id}"]`:`.study-connections[data-path="${id}"]`));f.seen[id]=[...new Set([...(f.seen[id]||[]),...actual])];}
};
/* HTTP contract: student writes only, server/client agreement before results. */
const festivalServerBase={finish,render,festivalConfirmPreference,festivalAllowed};
function festivalStudent(){return window.festivalIdentity.mode==='student';}
async function festivalRequest(path,payload){
 if(!festivalStudent())throw Error('학생 모드에서만 저장할 수 있어요.');
 const response=await fetch(FESTIVAL_API+path,{method:payload?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:payload?{'Content-Type':'application/json','X-CSRFToken':window.festivalIdentity.csrf_token}:{},...(payload?{body:JSON.stringify(payload)}:{})});
 if(!response.ok)throw Error('서버 저장을 확인하지 못했어요. 연결을 확인한 뒤 다시 시도해 주세요.');
 return response.json();
}
function festivalAnalysisMatches(s,a,presented){
 if(!a||!Array.isArray(a.domains)||a.domains.length!==9)return false;
 const local=s.result||InterestScoring.score(responseRows(s),FORM),fields=['domain_id','selected_count','offered_count','comparison_units','display_order'];
 const equal=local.domains.every(row=>{const remote=a.domains.find(d=>d.domain_id===row.domain_id);return remote&&fields.every(k=>remote[k]===row[k]);});
 const reps=representativeData(local).reps.map(d=>d.domain_id);
 return equal&&JSON.stringify(a.representatives)===JSON.stringify(reps)&&JSON.stringify(presented||a.representatives)===JSON.stringify(reps);
}
function festivalStillActive(s,f){return (s===session||s===sampleSession)&&s.festival===f&&festivalFingerprint(s)===f.fingerprint;}
function festivalSaveScreen(){const f=festivalState(session);return `<section class="paper"><h1>결과를 서버와 확인하고 있어요</h1><p role="alert" tabindex="-1" id="festival-attempt-status">${esc(f?.error||'32개 응답을 저장하고 같은 분석인지 확인해요.')}</p><div class="actions"><button class="btn" onclick="finish()" ${f?.saving?'disabled':''}>결과 저장 다시 시도</button>${button('선택한 응답 수정','backToReview()',true)}</div></section>`;}
finish=async function(){
 if(!festivalIdentityReady()||!session)return;
 if(!festivalStudent()||!festivalCurrent(session))return festivalServerBase.finish();
 const s=session,f=festivalState(s);if(f.saving)return;
 let navigation=festivalNavigationGeneration;
 try{const local=InterestScoring.score(responseRows(s),FORM);f.saving=true;f.error='';f.attempt_request_id ||=crypto.randomUUID();view='festival-saving';render();navigation=festivalNavigationGeneration;
 const saved=await festivalRequest('/attempts',{request_id:f.attempt_request_id,form_version:FESTIVAL_FRAME,answers:[...s.values]});
 if(!festivalStillActive(s,f))return;
 if(!saved.attempt_id||!saved.analysis_revision||!festivalAnalysisMatches({...s,result:local},saved.analysis,saved.presented_villages))throw Error('서버 분석과 화면 분석이 일치하지 않아 결과를 열지 않았어요. 운영자에게 확인해 주세요.');
 const check=await festivalRequest('/attempts/'+encodeURIComponent(saved.attempt_id));
 if(!festivalStillActive(s,f))return;
 if(check.attempt_id!==saved.attempt_id||check.analysis_revision!==saved.analysis_revision||!festivalAnalysisMatches({...s,result:local},check.analysis,check.presented_villages))throw Error('서버 저장 결과를 확인하지 못했어요. 다시 시도해 주세요.');
 Object.assign(f,{attempt_id:saved.attempt_id,analysis_revision:saved.analysis_revision,verified:true,server_seen:{}});s.result=local;f.saving=false;
 if(navigation!==festivalNavigationGeneration)return;
 resultTab='core';view='result';render();festivalRememberAttempt(f.attempt_id);
 }catch(e){if(!festivalStillActive(s,f))return;f.saving=false;f.error=e.message;if(navigation!==festivalNavigationGeneration)return;view='festival-saving';render();$('#festival-attempt-status')?.focus();}
};
async function festivalFlushPresentations(s,f){
 if(!festivalStudent()||!f.verified||!festivalStillActive(s,f))return;
 for(const id of festivalCandidates(s)){
  if(!festivalStillActive(s,f))return;
  const shown=f.seen[id]||[],sent=f.server_seen?.[id]||[];
  if(!shown.some(section=>!sent.includes(section)))continue;
  await festivalRequest('/attempts/'+encodeURIComponent(f.attempt_id)+'/presentation',{analysis_revision:f.analysis_revision,domain_id:id,sections:[...shown]});
  if(!festivalStillActive(s,f))return;
  const check=await festivalRequest('/attempts/'+encodeURIComponent(f.attempt_id));
  if(check.analysis_revision!==f.analysis_revision||!festivalAnalysisMatches(s,check.analysis,check.presented_villages))throw Error('서버의 최신 분석을 다시 확인해 주세요.');
  f.server_seen||={};f.server_seen[id]=[...shown];
 }
}
function festivalQueuePresentations(s){const f=festivalState(s);if(!festivalStudent()||!f.verified)return;f.presentation_queue=(f.presentation_queue||Promise.resolve()).catch(()=>{}).then(()=>festivalFlushPresentations(s,f));f.presentation_queue.catch(()=>{});}
festivalConfirmPreference=async function(){
 const s=festivalActive(),f=festivalState(s);
 if(!festivalStudent())return festivalServerBase.festivalConfirmPreference();
 if(f.submitting||!f.verified||festivalMissing(s).length||!festivalCandidates(s).includes(f.selected))return;
 f.submitting=true;f.error='';f.preference_request_id ||=crypto.randomUUID();festivalPreferenceDialog(s);
 const navigation=festivalNavigationGeneration;
 try{
  await (f.presentation_queue||Promise.resolve()).catch(()=>{});await festivalFlushPresentations(s,f);
  if(!festivalStillActive(s,f))return;
  const payload={request_id:f.preference_request_id,analysis_revision:f.analysis_revision,selected_village_id:f.selected};
  const saved=await festivalRequest('/attempts/'+encodeURIComponent(f.attempt_id)+'/preference',payload);
  if(!festivalStillActive(s,f))return;
  if(!saved.preference||saved.preference.selected_village_id!==payload.selected_village_id||!festivalAnalysisMatches(s,saved.analysis))throw Error('선호 저장과 기존 분석을 확인하지 못했어요. 다시 시도해 주세요.');
  const check=await festivalRequest('/attempts/'+encodeURIComponent(f.attempt_id));
  if(!festivalStillActive(s,f))return;
  if(check.analysis_revision!==f.analysis_revision||check.preference?.selected_village_id!==payload.selected_village_id||!festivalAnalysisMatches(s,check.analysis,check.presented_villages))throw Error('서버에 저장된 선택을 확인하지 못했어요. 다시 시도해 주세요.');
  f.preference=check.preference;f.acknowledged=true;f.submitting=false;
  if(navigation===festivalNavigationGeneration)festivalOpenReport(s);
 }catch(e){if(!festivalStillActive(s,f))return;f.submitting=false;f.error=e.message;if(navigation!==festivalNavigationGeneration)return;festivalPreferenceDialog(s);$('#festival-save-status')?.focus();}
};
festivalAllowed=function(s){return festivalServerBase.festivalAllowed(s)&&(!festivalStudent()||festivalState(s).verified===true);};
render=function(focus=true){
 if(festivalIdentityReady()&&view==='festival-saving'){$('#main').innerHTML=festivalSaveScreen();return;}
 festivalServerBase.render(focus);
 if(['result','sample'].includes(view)){const s=festivalActive();if(festivalCurrent(s))festivalQueuePresentations(s);}
};
render(false);
/* Versioned file snapshots never confer student acknowledgement. */
const festivalRecordBase={readFile,applyImport,loadFestivalContext,init};
let festivalNavigationGeneration=0;
/* Data acknowledgements survive departure; only current navigation may open UI. */
const festivalNavigationBase={goHome,backToReview,closeDialog,render};
let festivalRenderedView=view;
goHome=function(){festivalNavigationGeneration++;return festivalNavigationBase.goHome();};
backToReview=function(){festivalNavigationGeneration++;return festivalNavigationBase.backToReview();};
closeDialog=function(){festivalNavigationGeneration++;return festivalNavigationBase.closeDialog();};
addEventListener('popstate',()=>{festivalNavigationGeneration++;},true);
$('#dialog').addEventListener('cancel',()=>{festivalNavigationGeneration++;});
render=function(focus=true){if(view!==festivalRenderedView){festivalNavigationGeneration++;festivalRenderedView=view;}return festivalNavigationBase.render(focus);};
function festivalSnapshot(s){
 if(!festivalCurrent(s)||!s.result)return null;
 const f=festivalState(s);return {form_version:FESTIVAL_FRAME,copy_version:MOMOTOWN_V02.copy_version,answers:[...s.values],attempt_id:f.attempt_id||null,analysis_revision:f.analysis_revision||f.preference?.analysis_revision||null,presented_villages:festivalCandidates(s),seen:JSON.parse(JSON.stringify(f.seen)),preference:f.preference||null};
}
function festivalRecord(s){
 const frame=s.response_frame_version||FORM.form_version,complete=s.values.every(v=>v!==null);
 return {schema:'momo-interest-record-v1',module_id:FORM.module_id,form_id:FORM.form_id,form_version:frame,response_frame_version:frame,canonical_form_version:FORM.form_version,copy_version:festivalCurrent(s)?MOMOTOWN_V02.copy_version:null,scoring_version:FORM.scoring_version,experience_version:FORM.experience_version,content_digest:FORM.content_digest,data_origin:s.origin,cursor:s.cursor,responses:responseRows(s),quest_choice:s.quest,result:complete?InterestScoring.score(responseRows(s),FORM):null,representative_rule_version:RULE_V12,preference_snapshot:festivalSnapshot(s)};
}
exportRecord=function(forceResult=true){const s=view==='report'?(reportReturn==='sample'?sampleSession:session):(['result','sample'].includes(view)&&forceResult?dataForResult().s:session);if(!s)return toast('아직 저장할 기록이 없어요.');saveBlob(new Blob([JSON.stringify(festivalRecord(s),null,2)],{type:'application/json'}),'모모타운_방문기록.json');exportedRecords.set(s,memoryFingerprint(s));};
function festivalValidateSnapshot(raw,valid){
 const p=raw.preference_snapshot;if(p===null||p===undefined)return null;
 const s={...valid,response_frame_version:FESTIVAL_FRAME,result:InterestScoring.score(FORM.items.map((q,i)=>({item_id:q.id,option_id:valid.values[i]})),FORM)},ids=festivalCandidates(s);
 if(p.form_version!==FESTIVAL_FRAME||p.copy_version!==MOMOTOWN_V02.copy_version||JSON.stringify(p.answers)!==JSON.stringify(valid.values)||JSON.stringify(p.presented_villages)!==JSON.stringify(ids)||!p.seen||typeof p.seen!=='object'||Array.isArray(p.seen))throw Error('선호 스냅샷과 응답·버전·세 마을 순서가 일치하지 않아요.');
 for(const [id,sections] of Object.entries(p.seen))if(!ids.includes(id)||!Array.isArray(sections)||sections.some(x=>!['intro','study'].includes(x)))throw Error('마을 화면 기록을 확인할 수 없어요.');
 if(p.preference&&(!ids.includes(p.preference.selected_village_id)||p.preference.analysis_revision!==p.analysis_revision||(p.preference.displayed_villages_in_order&&JSON.stringify(p.preference.displayed_villages_in_order)!==JSON.stringify(ids))))throw Error('선호와 분석 버전이 일치하지 않아요.');
 return p;
}
readFile=async function(file){
 if(!file)return;
 try{
  if(file.size>1000000)throw Error('1MB 이하의 JSON 기록을 골라 주세요.');
  const raw=JSON.parse(await file.text());
  if(raw.form_version!==FESTIVAL_FRAME){if((raw.response_frame_version&&raw.response_frame_version!==raw.form_version)||raw.preference_snapshot||raw.copy_version===MOMOTOWN_V02.copy_version)throw Error('이전 기록과 새 안내 버전이 섞여 있어요. 원본 기록 파일을 확인해 주세요.');return festivalRecordBase.readFile(file);}
  if(raw.response_frame_version!==FESTIVAL_FRAME||raw.canonical_form_version!==FORM.form_version||raw.copy_version!==MOMOTOWN_V02.copy_version)throw Error('안내 버전 정보가 일치하지 않아요.');
  const valid=InterestScoring.validateRecord({...raw,form_version:FORM.form_version},FORM);if(festivalStudent()&&valid.origin==='SYNTHETIC_EXAMPLE')throw Error('가상 예시는 학생의 실제 응답으로 저장하지 않아요.');const snapshot=festivalValidateSnapshot(raw,valid);
  pendingImport={...valid,response_frame_version:FESTIVAL_FRAME,festival_snapshot:snapshot,festival_import:true};
  if(session?.values.some(v=>v!==null))openDialog('불러온 기록으로 바꿀까요?',`<p>현재 선택을 바꾸기 전에 필요한 기록을 저장해 주세요.</p>${button('불러오기','applyImport()')}${button('취소','cancelImport()',true)}`);else await applyImport();
 }catch(e){pendingImport=null;toast(e instanceof SyntaxError?'올바른 JSON 기록 파일이 아닙니다.':e.message);}
};
applyImport=async function(){
 if(pendingImport){festivalNavigationGeneration++;$('#print-root').innerHTML='';}
 if(!pendingImport?.festival_import)return festivalRecordBase.applyImport();
 const p=pendingImport;pendingImport=null;closeDialog();
 const s={values:[...p.values],cursor:p.cursor,quest:p.quest,origin:p.origin,result:p.complete?InterestScoring.score(FORM.items.map((q,i)=>({item_id:q.id,option_id:p.values[i]})),FORM):null,started_at:null,response_frame_version:FESTIVAL_FRAME,copy_version:MOMOTOWN_V02.copy_version};
 if(s.origin==='SYNTHETIC_EXAMPLE')sampleSession=s;else session=s;
 editReturn=false;resultTab='core';view=p.complete?(s===sampleSession?'sample':'result'):'question';
 const f=festivalState(s);
 if(p.festival_snapshot&&!festivalStudent()){f.seen=p.festival_snapshot.seen;f.preference=p.festival_snapshot.preference;f.acknowledged=false;}
 if(festivalStudent()&&p.complete){if(p.festival_snapshot?.attempt_id)await festivalRestoreAttempt(p.festival_snapshot.attempt_id,s);else await finish();}
 else render();
};
function festivalRememberAttempt(id){if(location.protocol==='file:')return;const url=new URL(location.href);url.hash='attempt='+encodeURIComponent(id);history.replaceState(history.state,'',url);}
async function festivalRestoreAttempt(id,imported=null){
 if(!festivalStudent())return;
 const generation=++festivalNavigationGeneration,identity=window.festivalIdentity,previous=session,fingerprint=previous?festivalFingerprint(previous):null;
 const stillCurrent=()=>generation===festivalNavigationGeneration&&identity===window.festivalIdentity&&festivalStudent()&&session===previous&&(!previous||festivalFingerprint(previous)===fingerprint);
 $('#print-root').innerHTML='';
 try{
  const raw=await festivalRequest('/attempts/'+encodeURIComponent(id));
  if(!stillCurrent())return;
  if(raw.form_version!==FESTIVAL_FRAME||raw.copy_version!==MOMOTOWN_V02.copy_version||!Array.isArray(raw.answers)||raw.answers.length!==32)throw Error('서버 기록의 응답과 버전을 확인할 수 없어요. 운영자에게 확인해 주세요.');
  InterestScoring.validateResponses(FORM.items.map((q,i)=>({item_id:q.id,option_id:raw.answers[i]})),FORM);
  if(imported&&JSON.stringify(imported.values)!==JSON.stringify(raw.answers))throw Error('파일 응답과 서버 기록이 일치하지 않아요.');
  const s=imported||{values:[...raw.answers],cursor:31,quest:null,origin:'LOCAL_USER_INPUT',started_at:null,response_frame_version:FESTIVAL_FRAME,copy_version:MOMOTOWN_V02.copy_version};
  s.result=InterestScoring.score(responseRows(s),FORM);
  if(raw.attempt_id!==id||!raw.analysis_revision||!festivalAnalysisMatches(s,raw.analysis,raw.presented_villages))throw Error('서버 분석과 화면 분석이 일치하지 않아요.');
  const f=festivalState(s);Object.assign(f,{attempt_id:id,analysis_revision:raw.analysis_revision,verified:true,seen:{},server_seen:{},preference:null,acknowledged:false});
  if(Array.isArray(raw.presentations))for(const row of raw.presentations){const shown=row.shown_sections;if(festivalCandidates(s).includes(row.domain_id)&&Array.isArray(shown)&&shown.every(x=>['intro','study'].includes(x))){f.seen[row.domain_id]=[...shown];f.server_seen[row.domain_id]=[...shown];}}
  const pref=raw.preference;if(pref&&pref.analysis_revision===f.analysis_revision&&festivalCandidates(s).includes(pref.selected_village_id)&&JSON.stringify(pref.displayed_villages_in_order)===JSON.stringify(festivalCandidates(s))){f.preference=pref;f.acknowledged=!festivalMissing(s).length;}
  session=s;view='result';resultTab='core';festivalRememberAttempt(id);render();
 }catch(e){if(!stillCurrent())return;if(!session)session={values:Array(32).fill(null),cursor:0,quest:null,origin:'LOCAL_USER_INPUT',response_frame_version:FESTIVAL_FRAME,result:null};const f=festivalState(session);f.error=e.message;f.verified=false;f.acknowledged=false;view='festival-saving';render();$('#festival-attempt-status')?.focus();}
}
loadFestivalContext=async function(){const generation=++festivalNavigationGeneration;$('#print-root').innerHTML='';await festivalRecordBase.loadFestivalContext();if(generation!==festivalNavigationGeneration)return;if(festivalStudent()){const hash=new URLSearchParams(location.hash.slice(1)),id=hash.get('attempt');if(id)await festivalRestoreAttempt(id);}};
init=function(){festivalNavigationGeneration++;if(!festivalIdentityReady())return festivalRecordBase.init();if(location.protocol!=='file:'&&location.hash.startsWith('#attempt='))history.replaceState(history.state,'',location.pathname+location.search);festivalRecordBase.init();$('#print-root').innerHTML='';};
render(false);
const festivalTransitionBase={pause,anticipation,crumb};
pause=function(){let h=festivalTransitionBase.pause();if(festivalCurrent(session)&&festivalStudent()&&session.cursor===8)h=h.replace('<div class="chapter-copy">','<div class="chapter-copy"><p>'+esc(window.festivalIdentity.display_name)+', 이번에는 체험하는 자리를 둘러보자.</p>');return h;};
anticipation=function(){return festivalTransitionBase.anticipation().replace('<p class="lead">',`<p>${esc(MOMOTOWN_V02.chapters[3].closing)}</p><p class="lead">`);};
crumb=function(label){return festivalTransitionBase.crumb(label).replace('이야기 탐험단','모모타운 축제');};
showManagement=function(){openDialog('기록 저장·불러오기',`<p>${festivalStudent()?'32개 응답을 모두 고른 뒤 서버 저장 성공을 확인하고 결과를 열어요. 선호도 확정할 때 서버 저장 성공을 확인해요. 진행 중인 응답은 자동 저장하지 않으니 기록 파일로 백업해 주세요.':'관리자 미리보기는 현재 페이지에서만 진행하며 학생 데이터로 저장하지 않아요. JSON 파일로 백업할 수 있어요.'}</p><div class="actions">${button('현재 기록 파일 저장','exportRecord()')}${button('기록 불러오기','closeDialog();loadFile()',true)}</div><p>파일에는 내가 고른 활동과 버전이 담겨요. 이름은 파일에 담지 않아요.</p>`);};
const festivalSampleBase=qaSampleSession;
qaSampleSession=function(key){const s=festivalSampleBase(key);s.response_frame_version=FESTIVAL_FRAME;s.copy_version=MOMOTOWN_V02.copy_version;return s;};
if(location.protocol!=='file:')loadFestivalContext();
