/* Additive navigation only. Canonical questions, scoring and saved analysis stay untouched. */
(()=>{'use strict';
 let lastIdentityKey=null,historyKey=null,latest=null,historyStatus='pending';
 const baseRender=render,rememberAttempt=festivalRememberAttempt;
 festivalRememberAttempt=function(id){latest=id;historyStatus='ready';return rememberAttempt(id);};
 // Bind the current browser draft to its authenticated account, not a later cookie.
 festivalRequest=async function(path,payload){
  if(!festivalStudent())throw Error('학생 모드에서만 저장할 수 있어요.');
  const key=window.festivalIdentity.identity_key;
  const headers=payload?{'Content-Type':'application/json','X-CSRFToken':window.festivalIdentity.csrf_token}:{};
  if(key)headers['X-Momo-Identity']=key;
  const response=await fetch(FESTIVAL_API+path,{method:payload?'POST':'GET',credentials:'same-origin',cache:'no-store',headers,...(payload?{body:JSON.stringify(payload)}:{})});
  if(!response.ok)throw Error(response.status===409?'계정 또는 최신 회차가 바뀌었어요. 신원을 다시 확인해 주세요.':'서버 저장을 확인하지 못했어요. 연결을 확인한 뒤 다시 시도해 주세요.');
  if(key&&window.festivalIdentity.identity_key!==key)throw Error('계정이 바뀌었어요.');
  return response.json();
 };
 function safeReturn(){const raw=new URLSearchParams(location.search).get('return_to')||'/';if(!raw.startsWith('/')||raw.startsWith('//')||/[\\\x00-\x20]/.test(raw))return '/';try{const u=new URL(raw,location.origin);if(u.origin!==location.origin||u.pathname.startsWith(FESTIVAL_API))return '/';return u.pathname==='/'||/^\/(student|parent|news|community|courses)\//.test(u.pathname)?u.pathname+u.search:'/';}catch(e){return '/';}}
 const back=document.createElement('a');back.id='momo-return';back.href=safeReturn();back.className='btn secondary';back.textContent='닫기 · 모모아이로 돌아가기';back.style.cssText='display:inline-block;margin:10px 16px;font-size:14px';document.querySelector('header').insertAdjacentElement('afterend',back);if(parent!==window)back.style.display='none';
 back.addEventListener('click',event=>{if(parent!==window){event.preventDefault();festivalNavigationGeneration++;parent.postMessage({type:'momo-interest-close'},location.origin);}});
 let resumedNavigation=null;
 window.momoLayerSuspend=function(){resumedNavigation=null;festivalNavigationGeneration++;};
 function reconcileResumed(s,f){
  if(resumedNavigation!==festivalNavigationGeneration||!s||!f||!festivalStillActive(s,f))return;
  if(view==='festival-saving'&&!f.saving){if(f.verified){view='result';resultTab='core';festivalRememberAttempt(f.attempt_id);}render(false);}
  if(document.querySelector('#festival-preference')&&!f.submitting)festivalPreferenceDialog(s);
 }
 window.momoLayerResume=function(){resumedNavigation=festivalNavigationGeneration;reconcileResumed(session,session?.festival);};
 // The sealed save routines retain data acknowledgements across navigation. Reconcile
 // their eventual completion only into the still-resumed, unchanged draft/view.
 const pendingFinish=finish,pendingPreference=festivalConfirmPreference;
 finish=async function(...args){const s=session,promise=pendingFinish(...args),f=s?.festival;try{return await promise;}finally{reconcileResumed(s,f);}};
 festivalConfirmPreference=async function(...args){const s=festivalActive(),promise=pendingPreference(...args),f=s?.festival;try{return await promise;}finally{reconcileResumed(s,f);}};
 function discardIdentity(){festivalNavigationGeneration++;session=null;sampleSession=null;pendingImport=null;historyKey=null;latest=null;document.getElementById('print-root').innerHTML='';closeDialog();window.festivalIdentity={mode:'unavailable',display_name:null};view='greeting';render(false);}
 let libraryOpen=0;
 window.momoOpenStoredResults=async function(id=null){
  const key=window.festivalIdentity?.identity_key,token=++libraryOpen,navigation=festivalNavigationGeneration;
  if(!key||!festivalStudent())return;
  try{
   const response=await fetch(FESTIVAL_API+'/context',{credentials:'same-origin',cache:'no-store',headers:{'X-Momo-Identity':key}});
   if(token!==libraryOpen||navigation!==festivalNavigationGeneration||key!==window.festivalIdentity?.identity_key)return;
   if(response.status===409){discardIdentity();return;}
   if(!response.ok)throw Error();const current=await response.json();
   if(token!==libraryOpen||navigation!==festivalNavigationGeneration||key!==window.festivalIdentity?.identity_key)return;
   if(current.identity_key!==key||current.mode!=='student'){discardIdentity();return;}
   const path=FESTIVAL_API+'/reports'+(id?'/'+encodeURIComponent(id):'')+'?expected_identity='+encodeURIComponent(key);
   openDialog('내 탐색 결과 · 읽기 전용',`<iframe title="저장된 탐색 결과 · 읽기 전용" src="${esc(path)}" style="width:100%;height:70dvh;border:0;background:white"></iframe>`);
  }catch(e){if(token===libraryOpen&&navigation===festivalNavigationGeneration)toast('신원을 확인하지 못했어요. 다시 시도해 주세요.');}
 };
 function entries(){
  if(!festivalStudent()||!['greeting','intro','guide'].includes(view)||document.getElementById('saved-results-entry'))return;
  const newest=latest?`<button class="btn" onclick="momoOpenStoredResults('${esc(latest)}')">최신 저장 결과 바로 보기</button>`:'';
  document.getElementById('main').insertAdjacentHTML('afterbegin',`<section id="saved-results-entry" class="paper" style="padding:20px;margin-bottom:20px"><h2>새 탐험 또는 내 결과 보기</h2><p>새로 탐험은 아래 안내에서 시작해요. 완료한 결과는 응답을 다시 고르지 않고 읽을 수 있어요.</p><div class="actions">${newest}<button class="btn secondary" onclick="momoOpenStoredResults()">내 결과 보기</button></div>${historyStatus==='unavailable'?'<p role="status">저장 결과 목록을 확인하지 못했어요. 내 결과 보기에서 다시 확인해 주세요.</p>':''}</section>`);
 }
 render=function(focus=true){const currentKey=window.festivalIdentity?.identity_key;if(currentKey&&lastIdentityKey&&currentKey!==lastIdentityKey){festivalNavigationGeneration++;session=null;sampleSession=null;pendingImport=null;historyKey=null;latest=null;document.getElementById('print-root').innerHTML='';closeDialog();view='greeting';}if(currentKey)lastIdentityKey=currentKey;const value=baseRender(focus);if(festivalStudent())document.querySelectorAll('#main p').forEach(p=>{if(p.textContent==='능력을 판정하는 시험이 아니에요. 기록은 현재 페이지에만 있으니 쉬기 전에 파일로 저장해 주세요.')p.textContent='능력을 판정하는 시험이 아니에요. 완료한 응답과 선호는 서버 저장 성공을 확인해요. 진행 중 선택은 자동 저장하지 않으니 파일로 백업해 주세요.';});entries();const key=window.festivalIdentity?.identity_key;if(festivalStudent()&&key&&historyKey!==key){historyKey=key;latest=null;historyStatus='pending';fetch(FESTIVAL_API+'/reports.json',{credentials:'same-origin',cache:'no-store',headers:{'X-Momo-Identity':key}}).then(r=>{if(r.status===409&&window.festivalIdentity?.identity_key===key)discardIdentity();if(!r.ok)throw Error();return r.json();}).then(data=>{if(historyKey!==key||window.festivalIdentity?.identity_key!==key)return;latest=data.rows?.[0]?.attempt_id||null;historyStatus='ready';if(['greeting','intro','guide'].includes(view)){document.getElementById('saved-results-entry')?.remove();entries();}}).catch(()=>{if(historyKey!==key)return;historyStatus='unavailable';if(['greeting','intro','guide'].includes(view)){document.getElementById('saved-results-entry')?.remove();entries();}});}return value;};
 window.momoStartNewJourney=function(){if(session?.values.some(v=>v!==null)&&!confirm('현재 선택은 자동 저장되지 않아요. 기록 파일로 백업하지 않았다면 새 탐험을 시작할 때 잃게 돼요. 새로 시작할까요?'))return false;closeDialog();init();return true;};
 addEventListener('message',event=>{const frame=document.querySelector('#dialog iframe');if(event.origin!==location.origin||event.source!==frame?.contentWindow)return;if(event.data?.type==='momo-report-close')closeDialog();if(event.data?.type==='momo-report-new')window.momoStartNewJourney();});
 addEventListener('keydown',event=>{if(event.key!=='Escape'||document.querySelector('#dialog[open]'))return;if(parent!==window){event.preventDefault();festivalNavigationGeneration++;parent.postMessage({type:'momo-interest-close'},location.origin);}});
 render(false);
})();
