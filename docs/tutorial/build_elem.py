# -*- coding: utf-8 -*-
import io
from gp import grid, ex

Q1, Q2, EL = '\u201c', '\u201d', '\u2026'

CSS = """
@page{
  size:A4; margin:16mm 15mm 15mm;
  @bottom-center{ content:counter(page); font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif;
                  font-size:8pt; color:#B6AE9E; }
}
@page cover{ margin:0; @bottom-center{ content:none; } }

*{ margin:0; padding:0; box-sizing:border-box; }
:root{
  --ink:#2B2A28; --navy:#2F4A7A; --gold:#C9963E; --cream:#FFF8EC;
  --sky:#5C93C4; --sky-pale:#E8F1F9; --leaf:#4FA37A; --leaf-pale:#E6F4EC;
  --coral:#E1705C; --coral-pale:#FCEAE5; --line:#E8E1D3; --muted:#8A8272;
}
body{
  font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif;
  color:var(--ink); font-size:10.4pt; line-height:1.85; background:#F3EEE3;
}
.sheet{ max-width:210mm; margin:0 auto; background:#fff; }
.page{ padding:0 4mm; }
b{ color:var(--navy); }
em{ font-style:normal; background:#FBE9BE; padding:0 1px; border-radius:2px; }

/* ===== 표지 ===== */
.bookcover{
  page:cover; position:relative; width:100%; height:297mm; overflow:hidden;
  background:var(--cream); break-after:page;
}
.bookcover .band{
  position:absolute; left:0; right:0; top:0; height:96mm; background:var(--navy);
  border-bottom-left-radius:34mm; border-bottom-right-radius:34mm;
}
.bookcover .cb{ position:absolute; left:24mm; right:24mm; }
.bookcover .brandline{ top:22mm; }
.bookcover .brandline .bn{
  font-family:'Noto Serif KR','Noto Serif CJK KR',serif; font-size:11pt; font-weight:900;
  color:#F2D48A; letter-spacing:4px;
}
.bookcover .brandline .bs{ display:block; margin-top:2mm; font-size:9pt; color:#B9C9E4; }
.bookcover .badge{
  position:absolute; right:24mm; top:21mm; background:#F2D48A; color:var(--navy);
  font-size:10pt; font-weight:700; padding:2mm 5mm; border-radius:9mm;
}
.bookcover .maintitle{
  top:52mm; font-family:'Noto Serif KR','Noto Serif CJK KR',serif;
  font-size:34pt; font-weight:900; color:#fff; letter-spacing:-1px;
}
.bookcover .maintitle .sub{
  display:block; margin-top:4mm; font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif;
  font-size:11pt; font-weight:400; color:#CFDCF0; letter-spacing:0;
}
.bookcover .gpwrap{ top:110mm; text-align:center; }
.bookcover .hello{
  top:143mm; background:#fff; border:1.4px solid var(--line); border-radius:7mm;
  padding:7mm 9mm; font-size:10.6pt; line-height:2; color:#4A463E;
}
.bookcover .hello .h1{
  display:block; font-family:'Noto Serif KR','Noto Serif CJK KR',serif;
  font-size:13pt; font-weight:900; color:var(--navy); margin-bottom:3mm;
}
.bookcover .plist{ top:196mm; }
.bookcover .pitem{
  background:#fff; border:1.4px solid var(--line); border-left:5mm solid var(--coral);
  border-radius:5mm; padding:3.4mm 6mm; margin-bottom:3mm;
}
.bookcover .pitem.b{ border-left-color:var(--sky); }
.bookcover .pitem.c{ border-left-color:var(--leaf); }
.bookcover .pitem .pn{ font-size:10pt; font-weight:900; color:var(--coral); margin-right:4mm; }
.bookcover .pitem.b .pn{ color:var(--sky); }
.bookcover .pitem.c .pn{ color:var(--leaf); }
.bookcover .pitem .pt{ font-size:12pt; font-weight:700; color:var(--navy); }
.bookcover .pitem .pd{ display:block; margin-top:1mm; font-size:9.2pt; color:var(--muted); }
.bookcover .cfoot{
  position:absolute; left:24mm; right:24mm; bottom:12mm; text-align:center;
  font-size:8.6pt; color:var(--muted);
}

/* ===== 여는 장 ===== */
.opening{ break-after:page; padding-top:2mm; }
.headline{
  font-family:'Noto Serif KR','Noto Serif CJK KR',serif; font-size:19pt; font-weight:900;
  color:var(--navy); letter-spacing:-.5px;
}
.headline .hk{ display:block; font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif;
  font-size:9.6pt; font-weight:700; color:var(--gold); letter-spacing:2px; margin-bottom:2mm; }
.para{ margin-top:5mm; font-size:10.4pt; line-height:2; color:#413E38; }
.threecard{ margin-top:6mm; }
.tc{
  border:1.4px solid var(--line); border-radius:6mm; padding:5mm 6mm; margin-bottom:3.5mm;
  background:var(--coral-pale); break-inside:avoid;
}
.tc.b{ background:var(--sky-pale); } .tc.c{ background:var(--leaf-pale); }
.tc .tct{ font-size:12pt; font-weight:900; color:var(--coral); }
.tc.b .tct{ color:var(--sky); } .tc.c .tct{ color:var(--leaf); }
.tc .tcd{ margin-top:2mm; font-size:10pt; line-height:1.9; color:#413E38; }

.bubble{
  margin-top:6mm; background:var(--cream); border:1.4px dashed var(--gold);
  border-radius:6mm; padding:5mm 6mm; font-size:10pt; line-height:1.95; color:#4A4438;
  break-inside:avoid;
}
.bubble .who{ display:block; font-weight:900; color:var(--gold); margin-bottom:1.5mm; font-size:10.4pt; }

/* ===== 간지 ===== */
.divider{ break-before:page; padding-top:2mm; }
.divider .dv{
  border-radius:8mm; padding:8mm 9mm; background:var(--coral-pale); border:1.6px solid #F2CFC6;
}
.divider .dv.b{ background:var(--sky-pale); border-color:#CFE2F1; }
.divider .dv.c{ background:var(--leaf-pale); border-color:#CCE7D9; }
.divider .dvn{ font-size:10pt; font-weight:900; color:var(--coral); letter-spacing:2px; }
.divider .dv.b .dvn{ color:var(--sky); } .divider .dv.c .dvn{ color:var(--leaf); }
.divider .dvt{
  margin-top:2mm; font-family:'Noto Serif KR','Noto Serif CJK KR',serif;
  font-size:20pt; font-weight:900; color:var(--navy);
}
.divider .dvs{ margin-top:4mm; font-size:10.2pt; line-height:2; color:#4A463E; }

/* ===== 절 ===== */
.sec{ break-before:page; padding-top:1mm; }
.sec.flow{ break-before:auto; margin-top:8mm; }
.sec-head{ margin-bottom:4mm; }
.sec-head .sn{
  display:inline-block; background:var(--coral); color:#fff; font-size:10pt; font-weight:900;
  border-radius:6mm; padding:1mm 4.5mm; margin-right:3mm;
}
.sec.b .sec-head .sn{ background:var(--sky); }
.sec.c .sec-head .sn{ background:var(--leaf); }
.sec-head .stt{ font-size:14.5pt; font-weight:900; color:var(--navy); }
.sec-head .sd{ display:block; margin-top:2.5mm; font-size:9.8pt; color:#5A554B; line-height:1.85; }

/* ===== 규정 카드 (1부) ===== */
.rule{
  border:1.4px solid var(--line); border-radius:6mm; padding:5mm 6mm; margin-bottom:4mm;
  break-inside:avoid; background:#fff;
}
.rule .rh{ margin-bottom:3mm; }
.rule .rn{
  display:inline-block; width:9mm; height:9mm; line-height:9mm; text-align:center;
  background:var(--coral); color:#fff; border-radius:50%; font-size:10pt; font-weight:900;
  margin-right:3.5mm;
}
.rule .rt{ font-size:13pt; font-weight:900; color:var(--navy); }
.rule .rsay{
  background:var(--cream); border-radius:4mm; padding:3.5mm 5mm; font-size:10.6pt;
  line-height:1.9; color:#413E38;
}
.rule .rsay b{ color:var(--coral); }
.rule .rwhy{ margin-top:3mm; font-size:9.8pt; line-height:1.85; color:#5A554B; }
.rule .rwhy .wq{ font-weight:900; color:var(--gold); margin-right:2mm; }
.exrow{ margin-top:4mm; }
.ex-one{ margin-bottom:3mm; }
.ex-one:last-child{ margin-bottom:0; }
.ex-tag{ font-size:9.4pt; font-weight:700; margin-bottom:1.6mm; }
.ex-tag.bad{ color:var(--coral); } .ex-tag.good{ color:var(--leaf); }
.ex-note{ margin-top:2mm; font-size:9.2pt; line-height:1.8; color:#5A554B; }
.try{
  margin-top:4mm; border-top:1.2px dashed var(--line); padding-top:3mm;
  font-size:9.4pt; color:var(--muted);
}
.try b{ color:var(--gold); }

/* ===== 원고지 ===== */
.gp{ border-top:.5mm solid var(--coral); border-left:.5mm solid var(--coral);
     display:inline-block; font-size:0; line-height:0; }
.gp.bad{ border-color:var(--coral); }
.gp.good{ border-color:var(--leaf); }
.gp.plain{ border-color:#C9BFA8; }
.gr{ white-space:nowrap; font-size:0; line-height:0; }
.gp span{
  display:inline-block; width:7.4mm; height:7.4mm; line-height:7.4mm;
  border-right:.25mm solid #EBCFC6; border-bottom:.25mm solid #EBCFC6;
  font-size:11pt; text-align:center; color:#2B2A28; vertical-align:top;
}
.gp.good span{ border-color:#C7E3D3; }
.gp.plain span{ border-color:#E4DBC7; }
.gp span.two{ font-size:7.4pt; letter-spacing:-.3pt; }
.gp span.bl{ text-align:left; line-height:6mm; padding-left:.8mm; }
.gp span.qo{ text-align:right; line-height:10mm; }
.gp span.qc{ text-align:left; line-height:10mm; }
.gp span.hl{ background:var(--leaf-pale); color:var(--leaf); font-weight:700; }
.gp.bad span.hl{ background:var(--coral-pale); color:var(--coral); }
.gp span.del{ text-decoration:line-through; color:var(--coral); }
.gp.navy{ border-color:#F2D48A; }
.gp.navy span{ border-color:rgba(242,212,138,.55); color:#fff; }
.gp.big span{ width:9mm; height:9mm; line-height:9mm; font-size:13pt; }

/* ===== 표 (2부) ===== */
table{ width:100%; border-collapse:separate; border-spacing:0; font-size:10pt; margin-top:3mm; }
thead th{
  background:var(--sky-pale); color:#4A6C8C; font-size:8.6pt; font-weight:700;
  text-align:left; padding:2.4mm 3mm;
}
thead th:first-child{ border-top-left-radius:3mm; }
thead th:last-child{ border-top-right-radius:3mm; }
tbody td{ padding:3mm; border-bottom:1px solid var(--line); vertical-align:top; line-height:1.75; }
tbody tr:nth-child(even) td{ background:#FBFCFE; }
tr{ break-inside:avoid; }
.k{ width:16%; font-weight:900; color:var(--navy); }
.bad2{ width:26%; color:var(--coral); }
.good2{ width:26%; color:var(--leaf); font-weight:500; }
.why2{ width:32%; color:#5A554B; font-size:9.4pt; }
.bad2:before{ content:'✕ '; font-weight:900; }
.good2:before{ content:'○ '; font-weight:900; }
.star{ color:var(--gold); }

/* ===== 생각 편 (3부) ===== */
.step{
  border:1.4px solid var(--line); border-left:5mm solid var(--leaf); border-radius:6mm;
  padding:5mm 6mm; margin-bottom:4mm; break-inside:avoid;
}
.step .stn{ font-size:10pt; font-weight:900; color:var(--leaf); }
.step .stt2{ margin-top:1mm; font-size:12.5pt; font-weight:900; color:var(--navy); }
.step .std{ margin-top:2.5mm; font-size:10pt; line-height:1.95; color:#413E38; }
.samp{ margin-top:3mm; background:var(--leaf-pale); border-radius:4mm; padding:3.5mm 5mm; font-size:9.8pt; line-height:1.9; }
.samp .l{ display:block; }
.samp .l b{ color:var(--leaf); }
.weak{ background:var(--coral-pale); }
.weak .l b{ color:var(--coral); }

/* ===== 부록 ===== */
.appendix{ break-before:page; padding-top:1mm; }
.check{ border:1.6px solid var(--line); border-radius:6mm; margin-top:4mm; overflow:hidden; break-inside:avoid; }
.check .ch{ background:var(--coral); color:#fff; padding:3mm 5mm; font-size:11.5pt; font-weight:900; }
.check.b .ch{ background:var(--sky); } .check.c .ch{ background:var(--leaf); }
.check .cb2{ padding:4mm 6mm 4mm 11mm; font-size:10pt; line-height:1.95; }
.check .cb2 li{ margin-bottom:1.5mm; }
.notice{
  margin-top:7mm; border:1.4px solid var(--line); border-radius:6mm; background:var(--cream);
  padding:5mm 6mm; font-size:9pt; line-height:1.9; color:#4A463E; break-inside:avoid;
}
.notice .nt{ display:block; font-size:10.4pt; font-weight:900; color:var(--navy); margin-bottom:2mm; }
.colophon{ margin-top:6mm; text-align:center; font-size:8.6pt; color:var(--muted); line-height:1.9; }
.colophon .cb3{ font-family:'Noto Serif KR','Noto Serif CJK KR',serif; font-weight:900;
                color:var(--navy); font-size:10pt; letter-spacing:1px; }

@media screen{
  body{ padding:8mm 0; }
  .sheet{ box-shadow:0 2px 18px rgba(0,0,0,.13); padding-bottom:10mm; }
  .page{ padding:0 10mm; }
}
"""

# ---------------------------------------------------------------- 1부 규정 (14)
RULES = [
 dict(no='1', title='한 칸에 한 글자만',
   say='글자 하나에 칸 하나예요. <b>두 글자를 한 칸에 몰아 쓰지 않아요.</b>',
   why='칸이 모자라 보여도 괜찮아요. 칸이 다 차면 다음 줄로 넘어가면 돼요.',
   bad=['!{환경}!{보호}는 중요해요.'], bad_cap='두 글자를 한 칸에 넣었어요',
   good=['환경보호는 중요해요.'], good_cap='글자 하나에 칸 하나예요',
   try_='공책에 쓰던 것처럼 글자를 붙여 쓰면 안 돼요. 칸을 하나씩 세면서 써 보세요.'),

 dict(no='2', title='문단이 시작되면 첫 칸을 비워요', star=True,
   say='새 문단을 시작할 때는 <b>첫 칸을 비우고 둘째 칸부터</b> 써요. 글의 맨 처음도 그래요.',
   why='첫 칸이 비어 있으면 읽는 사람이 "아, 여기서 이야기가 바뀌는구나" 하고 알아요.',
   n=13,
   bad=['!첫 칸부터 썼어요.'], bad_cap='첫 칸부터 글자를 썼어요',
   good=['!{ }첫 칸을 비웠어요.'], good_cap='첫 칸을 비우고 시작했어요',
   try_='다 쓰고 나서 왼쪽 첫 칸만 위에서 아래로 훑어보세요. 빠뜨린 곳이 금방 보여요.'),

 dict(no='3', title='문단 사이에 빈 줄은 없어요',
   say='문단이 바뀌어도 <b>줄을 통째로 비우지 않아요.</b> 줄만 바꾸고 첫 칸을 비우면 끝이에요.',
   why='빈 줄을 넣으면 쓸 수 있는 칸이 스무 개나 사라져요. 분량이 아까워요.',
   n=12,
   bad=['앞 문단이 끝났어요.', '', '!{ }다음 문단이에요.'], bad_cap='한 줄을 통째로 비웠어요',
   good=['앞 문단이 끝났어요.', '!{ }다음 문단이에요.'], good_cap='줄만 바꾸고 첫 칸을 비웠어요'),

 dict(no='4', title='띄어쓰기도 한 칸을 써요',
   say='낱말과 낱말 사이를 띄울 때도 <b>칸 하나를 비워요.</b> 그 빈 칸도 글자 수에 들어가요.',
   why='빈 칸을 아끼려고 붙여 쓰면 띄어쓰기를 틀린 것으로 봐요.',
   n=12,
   bad=['!{환경문}제는 심각해요.'], bad_cap='띄어야 할 자리를 붙여 썼어요',
   good=['환경!{ }문제는 심각해요.'], good_cap='띄는 자리는 한 칸 비워요'),

 dict(no='5', title='줄 끝에서 띄어야 할 때', star=True,
   say='줄이 꽉 차서 다음 줄로 넘어갈 때는 <b>다음 줄 첫 칸을 비우지 않아요.</b>',
   why='줄이 바뀐 것 자체가 이미 띄어쓰기예요. 여기서 또 비우면 새 문단으로 오해받아요.',
   n=6,
   bad=['환경 문제는', '!{ }심각해요.'], bad_cap='다음 줄 첫 칸을 또 비웠어요',
   good=['환경 문제는', '심각해요.'], good_cap='다음 줄 첫 칸부터 바로 써요'),

 dict(no='6', title='숫자는 한 칸에 두 개',
   say='아라비아 숫자는 <b>한 칸에 두 개</b>씩 넣어요. 2026년이면 20, 26으로 끊어요.',
   why='한글은 하나씩, 숫자는 둘씩. 이것만 기억하면 돼요.',
   n=8,
   bad=['!2!0!2!6년'], bad_cap='한 칸에 하나씩 넣었어요',
   good=['!{20}!{26}년'], good_cap='한 칸에 두 개씩 넣었어요'),

 dict(no='7', title='제목과 이름의 자리',
   say='제목은 <b>첫 줄 가운데</b>에 써요. 다음 줄에 학년과 이름을 쓰는데, <b>오른쪽 끝에서 두 칸을 남겨요.</b>',
   why='앞뒤로 남는 칸이 비슷하면 가운데예요. 한 칸쯤 차이 나도 괜찮아요.',
   n=16,
   good=['     규제의 조건', '       4학년 김서연'], good_cap='가운데 제목, 오른쪽 이름',
   note='답안지에 제목 쓰는 칸이 따로 있으면 원고지에는 안 써도 돼요.'),

 dict(no='8', title='제목 다음에는 한 줄을 비워요',
   say='이름을 쓴 다음 <b>한 줄을 비우고</b> 본문을 시작해요. 본문 첫 칸도 비우는 것, 잊지 마세요.',
   why='여기 한 줄만 예외예요. 문단 사이에는 빈 줄을 넣지 않아요.',
   n=16,
   good=['       4학년 김서연', '', '!{ }우리 반은 지난주에 일'], good_cap='한 줄 비우고 본문 시작'),

 dict(no='9', title='마침표와 쉼표의 자리', star=True,
   say='마침표(.)와 쉼표(,)는 <b>칸의 왼쪽 아래</b>에 작게 찍어요. 그래도 칸 하나를 다 써요.',
   why='가운데에 크게 쓰면 글자처럼 보여요. 작게, 왼쪽 아래에.',
   n=10,
   bad=['문제는 분명해요#.'], bad_cap='칸 가운데에 크게 찍었어요',
   good=['문제는 분명해요!.'], good_cap='칸 왼쪽 아래에 작게 찍었어요'),

 dict(no='10', title='마침표가 줄 첫 칸에 오면 안 돼요', star=True,
   say='마침표·쉼표·닫는 따옴표는 <b>줄 첫 칸에 올 수 없어요.</b> 앞 줄 마지막 글자와 <b>같은 칸에</b> 같이 써요.',
   why='시험에서 가장 많이 깎이는 실수예요. 줄 끝에 왔을 때 한 번만 확인하면 돼요.',
   n=7,
   bad=['해법은 달라요', '#.'], bad_cap='마침표가 다음 줄로 넘어갔어요',
   good=['해법은 달라!{요.}'], good_cap='마지막 글자와 같은 칸에 썼어요'),

 dict(no='11', title='부호 뒤에는 한 칸을 비워요',
   say='한 문단 안에서 문장을 이어 쓸 때는 <b>마침표 뒤에 한 칸을 비워요.</b>',
   why='줄이 바뀌는 자리라면 비우지 않아요. 5번 규정과 같은 이유예요.',
   n=14,
   bad=['분명해요.!그래서 달라요.'], bad_cap='마침표 뒤를 바로 붙였어요',
   good=['분명해요.!{ }그래서 달라요.'], good_cap='한 칸 비우고 이어 썼어요'),

 dict(no='12', title='물음표와 느낌표', star=False,
   say='물음표(?)와 느낌표(!)는 <b>칸 가운데</b>에 쓰고, <b>뒤에 한 칸을 비워요.</b>',
   why='마침표와 자리가 달라요. 물음표는 가운데, 마침표는 왼쪽 아래.',
   n=12,
   bad=['그럴까!{?}아니에요.'], bad_cap='뒤에 바로 이어 썼어요',
   good=['그럴까{?}!{ }아니에요.'], good_cap='뒤에 한 칸을 비웠어요'),

 dict(no='13', title='대화는 줄을 바꿔서', star=True,
   say='큰따옴표로 대화를 쓸 때는 <b>줄을 바꾸고, 첫 칸을 비운 뒤 둘째 칸</b>에서 시작해요.',
   why='대화가 눈에 확 들어와요. 대화가 끝나면 다시 줄을 바꿔요.',
   n=14,
   bad=['말씀하셨어요.!%s먼저 해라.%s' % (Q1, Q2)], bad_cap='앞 문장에 이어서 썼어요',
   good=['말씀하셨어요.', '!{ }!%s먼저 해라.%s' % (Q1, Q2)], good_cap='줄을 바꿔 둘째 칸부터'),

 dict(no='14', title='틀렸을 때는 두 줄을 그어요',
   say='틀린 글자는 지우개로 지우지 말고 <b>가로로 두 줄을 긋고</b>, 그 칸 위 여백에 고쳐 써요.',
   why='지우고 겹쳐 쓰면 무엇을 남기려는 건지 알아보기 어려워요.',
   n=14,
   good=['환경을 ~보~호~해~요.'], good_cap='두 줄을 긋고 위에 고쳐 써요',
   note='칸을 새로 밀지 않아요. 뒤 글자는 그대로 두면 돼요.'),
]

# ---------------------------------------------------------------- 2부 문장 항목
S1 = [
 ('되 / 돼', '그렇게 하면 되', '그렇게 하면 돼', "'하'와 '해'를 넣어 봐요. '해'가 어울리면 <b>돼</b>예요.", True),
 ('안 / 않', '숙제를 않 했다', '숙제를 안 했다', "<b>안</b>은 앞에 따로 서요. <b>않</b>은 '-지' 뒤에만 와요.", True),
 ('-던 / -든', '어제 먹든 빵', '어제 먹던 빵', "지난 일이면 <b>던</b>, 고르는 말이면 <b>든</b>이에요.", False),
 ('-데 / -대', '친구가 춥데', '친구가 춥대', "내가 겪은 일은 <b>데</b>, 남에게 들은 말은 <b>대</b>예요.", False),
 ('다르다 / 틀리다', '내 생각과 틀려요', '내 생각과 달라요', "<b>틀리다</b>는 답이 아니라는 뜻이에요. 견줄 땐 <b>다르다</b>.", True),
 ('가르치다 / 가리키다', '손가락으로 가르쳤다', '손가락으로 가리켰다', "<b>가르치다</b>는 알려 주기, <b>가리키다</b>는 손으로 짚기.", False),
 ('바라다 / 바래다', '합격을 바래요', '합격을 바라요', "<b>바래다</b>는 색이 옅어지는 것이에요.", False),
 ('맞추다 / 맞히다', '정답을 맞췄어요', '정답을 맞혔어요', "정답은 <b>맞히다</b>, 서로 대 보는 건 <b>맞추다</b>.", False),
]
S2 = [
 ('며칠', '몇 일 걸려요', '며칠 걸려요', "'몇 일'이라고 쓰지 않아요. 언제나 <b>며칠</b>이에요.", True),
 ('역할', '역활을 맡았다', '역할을 맡았다', "'역활'은 없는 말이에요.", True),
 ('오랜만', '오랫만에 만났다', '오랜만에 만났다', "'오래간만'이 줄어든 말이라 <b>오랜만</b>이에요.", True),
 ('왠지 / 웬', '웬지 슬퍼요 / 왠 떡이야', '왠지 슬퍼요 / 웬 떡이야', "'왜인지'가 줄면 <b>왠지</b>, 나머지는 <b>웬</b>.", True),
 ('설레다', '설레임이 커요', '설렘이 커요', "기본형이 '설레다'라서 <b>설렘</b>이에요.", False),
 ('금세', '금새 끝났어요', '금세 끝났어요', "'금시에'가 줄어든 말이에요.", False),
 ('어떻게 / 어떡해', '나 어떻게? / 어떡해 하지?', '나 어떡해? / 어떻게 하지?', "<b>어떡해</b>는 '어떻게 해'가 줄어든 말이라 문장 끝에만 써요.", True),
 ('낫다 / 낳다', '감기가 낳았어요', '감기가 나았어요', "<b>낳다</b>는 아기를 낳을 때만 써요.", True),
]
S3 = [
 ('것', '해야할것 같아요', '해야 할 것 같아요', "<b>'것'은 언제나 앞말과 띄어요.</b>", True),
 ('수', '할수 있어요', '할 수 있어요', "'할 수 있다'는 세 덩어리예요.", True),
 ('지', '만난지 이틀', '만난 지 이틀', "시간이 얼마나 지났는지 말할 땐 띄어요.", True),
 ('데', '갈데가 없어요', '갈 데가 없어요', "'곳'으로 바꿔지면 띄어요.", True),
 ('만', '사흘만에 왔어요', '사흘 만에 왔어요', "시간이 지난 것이면 띄고, '오직'이면 붙여요.", True),
 ('명사 + 조사', '학교 에서 놀았다', '학교에서 놀았다', "은·는·이·가·을·를·에·에서는 모두 붙여요.", True),
 ('명사 + 하다', '공부 했어요', '공부했어요', "'-하다'는 앞말에 붙는 말이에요.", True),
 ('조사가 끼면 띄어요', '공부를했어요', '공부를 했어요', "사이에 '를'이 들어가면 <b>띄어요</b>.", True),
 ('한 번 / 한번', '한번 더 세어 보자(횟수)', '한 번 더 세어 보자', "'두 번'으로 바꿔 말이 되면 띄어요.", False),
 ('안 되다', '공부가 안된다', '공부가 안 된다', "그냥 아니라는 뜻이면 띄어요.", False),
]
S4 = [
 ('주어와 서술어', '내 꿈은 요리사가 되고 싶다', '내 꿈은 요리사가 되는 것이다', "가운데를 지우고 '꿈은 되고 싶다'를 읽어 보세요. 어색하죠?", True),
 ('이유를 말하는 문장', '그 까닭은 준비를 못 했다', '그 까닭은 준비를 못 했기 때문이다', "'까닭은'으로 시작했으면 '~기 때문이다'로 닫아요.", True),
 ('겹치는 말', '보여진다, 잊혀진다', '보인다, 잊힌다', "'-어지다'를 빼고 읽어도 뜻이 통하면 빼는 게 맞아요.", True),
 ('너무 긴 문장', '쉼표로 이어 붙인 네 줄짜리 문장', '두 문장으로 나누기', "소리 내어 읽다가 숨이 차면 그 자리에서 자르세요.", True),
 ('구어체', '진짜 되게 좋았어요', '정말 좋았어요', "말할 때 쓰는 말은 글에서 빼요.", False),
 ('같은 말 반복', '그리고 … 그리고 … 그리고', '그리고 / 또 / 게다가', "같은 이음말이 세 번 넘게 나오면 바꿔요.", False),
]

TABLES = [
 ('1', '소리가 비슷해서 헷갈리는 말', '읽을 때는 비슷한데 뜻이 달라요. 자주 나오는 것부터 익혀요.', S1),
 ('2', '자주 틀리는 맞춤법', '많이 쓰는 말인데 거의 다 틀리는 것들이에요.', S2),
 ('3', '띄어쓰기', "'것·수·지·데·만' 다섯 글자만 알아도 절반은 맞아요.", S3),
 ('4', '문장 다듬기', '맞춤법은 맞는데 어딘가 이상한 문장을 고쳐요.', S4),
]

# ---------------------------------------------------------------- 3부
STEPS = [
 dict(n='1단계', t='주장에는 이유를 붙여요',
   d='"나는 이렇게 생각해요"로 끝나면 아직 반쪽이에요. 바로 뒤에 <b>이유 한 문장</b>을 붙이면 글이 됩니다.',
   weak=['<b>약한 글</b> 급식에 채소를 더 넣으면 좋겠다.'],
   good=['<b>좋은 글</b> 급식에 채소를 더 넣으면 좋겠다. 우리 반 친구들이 점심을 먹고 나서도 자주 배고파하는데, 채소 반찬이 있으면 먹을 것이 늘어나기 때문이다.']),
 dict(n='2단계', t='이유에는 예를 붙여요',
   d='이유만 있으면 "정말 그럴까?" 하는 생각이 들어요. <b>실제로 있었던 일</b>을 하나 붙이면 훨씬 힘이 세져요.',
   weak=['<b>약한 예</b> 다들 그렇게 생각한다.'],
   good=['<b>좋은 예</b> 지난주 우리 반에서 남긴 반찬을 세어 보니 열 명 중 여섯 명이 채소 반찬을 남겼다.']),
 dict(n='3단계', t='반대 생각을 먼저 말해요',
   d='반대하는 사람의 말을 <b>먼저 인정하고</b> 답하면, 읽는 사람이 내 글을 훨씬 믿게 돼요.',
   weak=['<b>약한 글</b> 반대하는 사람은 잘 몰라서 그래요.'],
   good=['<b>좋은 글</b> 채소를 싫어하는 친구도 있다. 그 말도 맞다. 다만 조리 방법을 바꾸면 남기는 양이 줄어든다는 조사도 있다.']),
 dict(n='4단계', t='"왜?"를 세 번 물어요',
   d='자기 글에서 가장 힘센 문장을 고르고, 그 뒤에 <b>"왜?"</b>를 붙여 보세요. 답이 글 안에 없으면 아직 더 파야 해요.',
   weak=['<b>1단계</b> 채소를 먹어야 한다. → 왜? … 답이 없음'],
   good=['<b>3단계</b> 채소를 먹어야 한다. → 왜? 몸에 좋아서. → 왜 몸에 좋지? 자라는 데 필요한 영양소가 들어 있어서. → 그럼 어떻게 하면 잘 먹을까? 조리 방법을 바꾸면 된다.']),
]


def rule_html(r):
    star = ' <span class="star">★</span>' if r.get('star') else ''
    h = ['<div class="rule">']
    h.append('<div class="rh"><span class="rn">%s</span><span class="rt">%s%s</span></div>'
             % (r['no'], r['title'], star))
    h.append('<div class="rsay">%s</div>' % r['say'])
    h.append('<div class="rwhy"><span class="wq">왜 그럴까요?</span>%s</div>' % r['why'])
    h.append('<div class="exrow">%s</div>' % ex(
        bad=r.get('bad'), good=r.get('good'), bad_cap=r.get('bad_cap', ''),
        good_cap=r.get('good_cap', ''), n=r.get('n'), note=r.get('note', '')))
    if r.get('try_'):
        h.append('<div class="try"><b>기억해요</b> &nbsp;%s</div>' % r['try_'])
    h.append('</div>')
    return ''.join(h)


def table_html(rows):
    h = ['<table><thead><tr><th class="k">무엇</th><th class="bad2" style="color:#4A6C8C">이렇게 쓰면 안 돼요</th>'
         '<th class="good2" style="color:#4A6C8C">이렇게 써요</th><th class="why2" style="color:#4A6C8C">왜 그럴까요</th></tr></thead><tbody>']
    for k, b, g, w, st in rows:
        h.append('<tr><td class="k">%s%s</td><td class="bad2">%s</td><td class="good2">%s</td>'
                 '<td class="why2">%s</td></tr>'
                 % (k, ' <span class="star">★</span>' if st else '', b, g, w))
    h.append('</tbody></table>')
    return ''.join(h)


COVER = """
<section class="bookcover">
  <div class="band"></div>
  <div class="cb brandline"><span class="bn">모모의 책장</span>
    <span class="bs">읽고 쓰는 힘을 기르는 첫 책</span></div>
  <div class="badge">초등 3~6학년</div>
  <div class="cb maintitle">문장과 생각
    <span class="sub">원고지 쓰는 법부터 생각을 세우는 법까지</span></div>
  <div class="cb gpwrap">%s</div>

  <div class="cb hello">
    <span class="h1">이 책은 이렇게 생겼어요</span>
    글씨를 잘 쓰는 방법을 알려 주는 책이 아니에요. <b>어디에 무엇을 놓는지</b>,
    <b>어떤 말이 맞는지</b>, <b>생각을 어떻게 이어 붙이는지</b>를 알려 주는 책이에요.
    한 번에 다 읽지 않아도 돼요. 필요할 때 그 쪽만 펴 보세요.
  </div>

  <div class="cb plist">
    <div class="pitem"><span class="pn">1부</span><span class="pt">원고지 사용법</span>
      <span class="pd">규칙 하나에 원고지 그림 하나 — 14가지</span></div>
    <div class="pitem b"><span class="pn">2부</span><span class="pt">문장 바로 쓰기</span>
      <span class="pd">자주 틀리는 말 32가지</span></div>
    <div class="pitem c"><span class="pn">3부</span><span class="pt">생각 정립하기</span>
      <span class="pd">주장에 힘을 붙이는 네 단계</span></div>
  </div>

  <div class="cfoot">모모의 책장 · 수강생 본인의 학습용 &nbsp;|&nbsp; © 모모의 책장</div>
</section>
""" % grid(['   문장과 생각'], n=12, tone='plain', extra='big')

OPENING = """
<section class="opening page">
  <div class="headline"><span class="hk">이 책을 여는 법</span>글을 볼 때 필요한 눈은 세 개예요</div>

  <div class="para">
    글을 다 쓰고 나면 선생님이 여기저기 표시를 해 주죠. 처음에는 그 표시가 다 똑같아 보여요.
    그런데 잘 보면 표시는 <b>딱 세 종류</b>밖에 없어요. 이 셋을 구분할 줄 알면, 다음부터는
    같은 표시를 받지 않게 돼요.
  </div>

  <div class="threecard">
    <div class="tc"><div class="tct">1부 · 원고지</div>
      <div class="tcd">칸을 어떻게 쓰는지에 대한 <b>약속</b>이에요. 글 내용이 아무리 좋아도
      칸을 안 지키면 점수가 깎여요. 대신 약속만 알면 그날로 해결돼요. 그래서 맨 앞에 두었어요.</div></div>
    <div class="tc b"><div class="tct">2부 · 문장</div>
      <div class="tcd">맞는 말과 <b>틀린 말</b>을 가려요. 답이 하나로 정해져 있어서
      알면 바로 고칠 수 있어요. 글을 다 쓰고 나서 훑어보는 곳이에요.</div></div>
    <div class="tc c"><div class="tct">3부 · 생각</div>
      <div class="tcd">맞고 틀림이 아니라 <b>약하고 강함</b>이에요. 맞춤법이 하나도 안 틀린 글도
      생각이 약하면 힘이 없어요. 글을 쓰기 <b>전에</b> 읽는 곳이에요.</div></div>
  </div>

  <div class="bubble">
    <span class="who">모모쌤의 한마디</span>
    이 책을 처음부터 끝까지 읽지 않아도 돼요. 원고지를 받으면 1부, 글을 다 쓰고 나면 2부,
    무슨 말을 쓸지 막막하면 3부를 펴세요. <em>★ 표시</em>는 어른들도 자주 틀리는 것이니
    시간이 없으면 그것만 봐도 충분해요.
  </div>
</section>
"""

PART1 = """
<div class="divider page">
  <div class="dv">
    <div class="dvn">1부</div>
    <div class="dvt">원고지 사용법</div>
    <div class="dvs">
      원고지는 어려운 규칙이 아니라 <b>칸을 쓰는 약속</b>이에요. 그래서 설명을 읽는 것보다
      <em>칸에 들어간 모습을 직접 보는 편</em>이 훨씬 빨라요.<br>
      그래서 이 부는 <b>규칙 하나에 원고지 그림 하나</b>를 붙였어요. 규칙을 읽고, 바로 아래에서
      틀린 모습(✕)과 맞는 모습(○)을 함께 보세요. 눈으로 한 번 보면 잘 잊히지 않아요.
    </div>
  </div>
</div>

<div class="sec page" style="break-before:auto; margin-top:8mm;">
  <div class="sec-head"><span class="sn">1부</span><span class="stt">칸을 지키는 열네 가지 약속</span>
    <span class="sd">★ 표시는 시험에서 가장 많이 깎이는 곳이에요.</span></div>
  %s
</div>
""" % ''.join(rule_html(r) for r in RULES)

secs = []
for n, t, d, rows in TABLES:
    secs.append('<div class="sec b page"><div class="sec-head"><span class="sn">%s</span>'
                '<span class="stt">%s</span><span class="sd">%s</span></div>%s</div>'
                % (n, t, d, table_html(rows)))

PART2 = """
<div class="divider page">
  <div class="dv b">
    <div class="dvn">2부</div>
    <div class="dvt">문장 바로 쓰기</div>
    <div class="dvs">
      여기 나오는 말들은 <b>답이 하나</b>예요. 맞거나 틀리거나 둘 중 하나라서, 알면 바로 고칠 수 있어요.<br>
      글을 다 쓰고 나서 훑어보는 곳이에요. 한 번에 외우려고 하지 말고,
      <em>내 글에서 그 말을 찾아보는</em> 방식으로 써 보세요.
    </div>
  </div>
</div>
""" + ''.join(secs)

steps_html = ''.join(
    '<div class="step"><div class="stn">%s</div><div class="stt2">%s</div>'
    '<div class="std">%s</div>'
    '<div class="samp weak"><span class="l">%s</span></div>'
    '<div class="samp"><span class="l">%s</span></div></div>'
    % (s['n'], s['t'], s['d'], s['weak'][0], s['good'][0]) for s in STEPS)

PART3 = """
<div class="divider page">
  <div class="dv c">
    <div class="dvn">3부</div>
    <div class="dvt">생각 정립하기</div>
    <div class="dvs">
      1부와 2부는 <b>틀린 것을 없애는</b> 일이었어요. 3부는 <b>약한 것을 강하게 만드는</b> 일이에요.<br>
      여기에는 맞고 틀림이 없어요. 그래서 맞춤법 검사기도 잡아 주지 못해요.
      대신 <em>단계가 있어요.</em> 한 단계씩 올라가면 글이 눈에 띄게 세집니다.
    </div>
  </div>
</div>

<div class="sec c page" style="break-before:auto; margin-top:8mm;">
  <div class="sec-head"><span class="sn">3부</span><span class="stt">주장에 힘을 붙이는 네 단계</span>
    <span class="sd">같은 이야기가 단계마다 어떻게 달라지는지 견주어 보세요.</span></div>
  %s
  <div class="bubble">
    <span class="who">모모쌤의 한마디</span>
    네 단계를 한 번에 다 하려고 하면 글이 무거워져요. 오늘은 <b>1단계와 2단계</b>만,
    다음에는 <b>3단계</b>를 붙여 보세요. 4단계는 글을 다 쓴 뒤에 스스로 물어보는 방법이에요.
  </div>
</div>
""" % steps_html

APPENDIX = """
<section class="appendix page">
  <div class="headline"><span class="hk">부록</span>내기 전에 딱 세 가지만 확인해요</div>
  <div class="para">이 쪽만 오려서 책상에 붙여 두세요. 다 쓰고 나서 순서대로 훑으면 돼요.</div>

  <div class="check">
    <div class="ch">1부 · 원고지 — 30초</div>
    <ol class="cb2">
      <li>문단마다 <b>첫 칸</b>을 비웠나요? 왼쪽만 위에서 아래로 훑어보세요.</li>
      <li>마침표가 <b>줄 첫 칸</b>에 앉아 있지 않나요?</li>
      <li>문단 사이를 <b>통째로 비우지</b> 않았나요?</li>
      <li>숫자를 <b>한 칸에 두 개</b>씩 넣었나요?</li>
      <li>대화는 <b>줄을 바꿔</b> 둘째 칸에서 시작했나요?</li>
    </ol>
  </div>

  <div class="check b">
    <div class="ch">2부 · 문장 — 1분</div>
    <ol class="cb2">
      <li><b>소리 내어</b> 읽어 보세요. 숨이 차는 문장은 너무 긴 거예요.</li>
      <li>가장 긴 문장에서 <b>주어와 서술어만</b> 남겨 읽어 보세요.</li>
      <li><b>'것·수·지·데·만'</b> 다섯 글자를 찾아 앞이 띄어졌는지 보세요.</li>
      <li><b>'하다' 앞</b>을 보세요. 조사가 없으면 붙이고, 있으면 띄워요.</li>
      <li><b>'진짜, 되게, 엄청'</b> 같은 말이 남아 있지 않나요?</li>
    </ol>
  </div>

  <div class="check c">
    <div class="ch">3부 · 생각 — 2분</div>
    <ol class="cb2">
      <li>내 주장 뒤에 <b>이유</b>가 한 문장 붙어 있나요?</li>
      <li>그 이유 뒤에 <b>실제로 있었던 일</b>이 하나 있나요?</li>
      <li>반대하는 사람의 말을 <b>한 번이라도</b> 적었나요?</li>
      <li>가장 힘센 문장 뒤에 <b>"왜?"</b>를 붙여 보세요. 답이 글 안에 있나요?</li>
    </ol>
  </div>

  <div class="notice">
    <span class="nt">저작권 및 이용에 관한 안내</span>
    이 자료의 저작권은 <b>모모의 책장</b>에 있습니다. 수강생 본인의 학습 목적으로만 이용할 수 있으며,
    복제·배포·전송, 블로그·카페·SNS 무단 게재, 학원·과외 등에서의 상업적 활용,
    촬영본·스캔본을 포함한 제3자 전달을 금합니다.
    무단 전재 및 재배포 시 저작권법에 따라 민형사상 책임을 물을 수 있습니다.
  </div>

  <div class="colophon">
    <span class="cb3">모모의 책장 · 문장과 생각 (초등판)</span><br>
    1부 원고지 사용법 14 · 2부 문장 바로 쓰기 32 · 3부 생각 정립하기 4단계 · 부록 점검표<br>
    © 모모의 책장. All rights reserved.
  </div>
</section>
"""

HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>문장과 생각 (초등판) — 모모의 책장</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&family=Noto+Serif+KR:wght@600;900&display=swap" rel="stylesheet">
<style>%s</style></head>
<body><div class="sheet">%s%s%s%s%s%s</div></body></html>
""" % (CSS, COVER, OPENING, PART1, PART2, PART3, APPENDIX)

io.open('/home/claude/elem.html', 'w', encoding='utf-8').write(HTML)
print('written', len(HTML))
