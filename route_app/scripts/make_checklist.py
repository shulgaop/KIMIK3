#!/usr/bin/env python3
"""make_checklist.py — генератор интерактивного чеклиста похода (F8).

По JSON-описанию производит один самодостаточный HTML-файл:
- ноль внешних зависимостей (инлайн CSS/JS, системные шрифты, кириллица);
- отметки сохраняются в localStorage браузера (работает офлайн);
- озвучка НЕОТМЕЧЕННЫХ пунктов через Web Speech API (голос браузера, ru-RU):
  кнопка 🔊 у раздела, «Читать всё», «Стоп»;
- счётчики по разделам и общий прогресс; @media print; мобильная вёрстка;
- единая с гидом природная палитра, крупные touch-цели и заметный фокус.

Использование:
  python3 make_checklist.py checklist.json Чеклист.html

checklist.json:
{
  "title": "Чеклист · Фанские горы",
  "subtitle": "05–17 сентября 2026 · отметки сохраняются в этом браузере",
  "storage_key": "fannChecklist",
  "sections": [
    {"title": "Документы и билеты",
     "items": ["Загранпаспорт ...", "..."],
     "note": "необязательная сноска к разделу"}
  ]
}
"""
import argparse, json, sys

TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<style>
  :root{--paper:#f4f1e8;--ink:#172820;--muted:#617067;--forest:#153b32;--crim:#a64f35;--card:#fffdf8;--line:#d4ddd4;--soft:#e8efe7}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--paper);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  body,p,li{overflow-wrap:anywhere}
  button:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid #d57a57;outline-offset:3px}
  .site-header{background:var(--forest);color:#fff;border-bottom:3px solid #d2b48c}
  .site-header .shell{max-width:900px;margin:0 auto;padding:13px 24px;display:flex;align-items:center;justify-content:space-between;gap:16px}
  .brand{color:#fff;text-decoration:none;font:700 1.05rem Georgia,"Times New Roman",serif}
  .brand small{display:block;font: .62rem/1.4 -apple-system,"Segoe UI",sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#cddbd3;margin-top:3px}
  .top-link{color:#fff;font-size:.8rem;text-underline-offset:3px}
  .wrap{max-width:900px;margin:0 auto;padding:32px 24px 64px}
  h1{font:700 clamp(2rem,5vw,3rem)/1.1 Georgia,"Times New Roman",serif;letter-spacing:-.02em;margin:0 0 10px}
  .sub{font-size:.9rem;color:var(--muted);margin-bottom:20px;max-width:75ch}
  .toolbar{position:sticky;top:0;background:var(--paper);padding:12px 0;border-bottom:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap;z-index:5;margin-bottom:18px}
  button{font:650 .84rem/1.2 inherit;padding:10px 13px;border:1px solid var(--forest);background:var(--card);color:var(--forest);cursor:pointer;border-radius:7px;min-height:42px}
  button:hover{background:var(--forest);color:#fff}
  button.reading{background:var(--crim);border-color:var(--crim);color:#fff}
  .progress{font:650 .9rem/1 -apple-system,"Segoe UI",sans-serif;align-self:center;margin-left:auto;color:var(--forest);white-space:nowrap}
  section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:14px}
  h2{font:700 1.2rem/1.35 Georgia,"Times New Roman",serif;color:var(--forest);display:flex;align-items:center;gap:10px;margin-bottom:10px;cursor:pointer}
  h2 .speak{font: .8rem/1 -apple-system,"Segoe UI",sans-serif;padding:7px 9px;border:1px solid var(--line);background:var(--soft);min-width:38px;min-height:38px}
  h2 .cnt{margin-left:auto;font:650 .82rem/1 -apple-system,"Segoe UI",sans-serif;color:var(--crim);white-space:nowrap}
  ul{list-style:none}
  li{display:flex;gap:11px;padding:9px 2px;border-bottom:1px solid var(--line);align-items:flex-start}
  li:last-child{border-bottom:none}
  input[type=checkbox]{width:22px;height:22px;margin-top:2px;accent-color:var(--forest);flex-shrink:0;cursor:pointer}
  label{cursor:pointer;flex:1}
  li.done label{text-decoration:line-through;opacity:.55}
  .note{font-size:.84rem;color:var(--muted);margin-top:10px;font-style:italic}
  @media (max-width:600px){
    .site-header .shell{padding:11px 16px}
    .wrap{padding:26px 16px 48px}
    section{padding:16px 14px}
    h2{flex-wrap:wrap}
    .toolbar{position:static}
    .toolbar button{flex:1;min-height:44px}
    .progress{width:100%;text-align:right;padding:4px}
  }
  @media (prefers-reduced-motion:reduce){*{transition:none!important}}
  @media print{
    body{background:#fff;font-size:11pt}
    .site-header,.toolbar,.speak{display:none!important}
    .wrap{max-width:none;padding:0}
    section{break-inside:avoid;border:1px solid #999}
  }
</style>
</head>
<body>
<header class="site-header"><div class="shell">
  <a class="brand" href="#checklist">Trek Fourge<small>Подготовка к походу</small></a>
  <a class="top-link" href="#sections">К списку</a>
</div></header>
<main class="wrap" id="checklist">
<h1>%%TITLE%%</h1>
<p class="sub">%%SUBTITLE%%</p>

<div class="toolbar">
  <button id="readAll">&#x1F50A; Читать всё</button>
  <button id="stopRead">&#x23F9; Стоп</button>
  <button id="reset">&#x21BA; Сбросить отметки</button>
  <span class="progress" id="progress" role="status" aria-live="polite">0 / 0</span>
</div>

<div id="sections">
%%SECTIONS%%
</div>
</main>
<script>
const synth = window.speechSynthesis;
function secText(h2){
  const sec = h2.closest('section');
  let t = h2.childNodes[0].textContent.trim() + '. ';
  sec.querySelectorAll('label').forEach(l=>{ if(!l.closest('li').classList.contains('done')) t += l.textContent.trim() + '. '; });
  return t;
}
function speak(txt){
  synth.cancel();
  const u = new SpeechSynthesisUtterance(txt);
  u.lang = 'ru-RU'; u.rate = 0.95;
  synth.speak(u);
}
function speakSec(h2){ speak(secText(h2)); }
document.getElementById('readAll').onclick = ()=>{
  synth.cancel();
  const secs = [...document.querySelectorAll('section[data-sec]')];
  let i = 0;
  const btn = document.getElementById('readAll');
  btn.classList.add('reading'); btn.textContent = '\\u{1F50A} Читаю\\u{2026}';
  function next(){
    if(i >= secs.length){ btn.classList.remove('reading'); btn.textContent='\\u{1F50A} Читать всё'; return; }
    const u = new SpeechSynthesisUtterance(secText(secs[i].querySelector('h2')));
    u.lang='ru-RU'; u.rate=0.95; u.onend = ()=>{ i++; next(); };
    synth.speak(u);
  }
  next();
};
document.getElementById('stopRead').onclick = ()=>{
  synth.cancel();
  const btn = document.getElementById('readAll');
  btn.classList.remove('reading'); btn.textContent='\\u{1F50A} Читать всё';
};
const boxes = [...document.querySelectorAll('input[type=checkbox]')];
function refresh(){
  let done = 0;
  boxes.forEach(b=>{
    b.closest('li').classList.toggle('done', b.checked);
    if(b.checked) done++;
  });
  document.getElementById('progress').textContent = done + ' / ' + boxes.length;
  document.querySelectorAll('section[data-sec]').forEach(s=>{
    const bs = [...s.querySelectorAll('input[type=checkbox]')];
    const d = bs.filter(b=>b.checked).length;
    s.querySelector('.cnt').textContent = d + '/' + bs.length;
  });
  localStorage.setItem('%%STORAGE_KEY%%', JSON.stringify(boxes.map(b=>b.checked)));
}
boxes.forEach(b=>b.addEventListener('change', refresh));
try{
  const saved = JSON.parse(localStorage.getItem('%%STORAGE_KEY%%')||'[]');
  saved.forEach((v,i)=>{ if(boxes[i]) boxes[i].checked = v; });
}catch(e){}
refresh();
document.getElementById('reset').onclick = ()=>{ if(confirm('Сбросить все отметки?')){ boxes.forEach(b=>b.checked=false); refresh(); } };
</script>
</body>
</html>
"""


def esc_html(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_sections(sections):
    """HTML разделов: нумерация сквозная, id чекбоксов c1..cN."""
    out, n = [], 0
    for si, sec in enumerate(sections, start=1):
        items = []
        for text in sec["items"]:
            n += 1
            items.append(f'<li><input type="checkbox" id="c{n}">'
                         f'<label for="c{n}">{esc_html(text)}</label></li>')
        note = f'\n<p class="note">{esc_html(sec["note"])}</p>' if sec.get("note") else ""
        out.append(f"""<section data-sec>
<h2 onclick="speakSec(this)">{si} · {esc_html(sec["title"])} <button class="speak" aria-label="Прочитать раздел вслух" onclick="event.stopPropagation();speakSec(this.parentElement)">&#x1F50A;</button><span class="cnt"></span></h2>
<ul>
{chr(10).join(items)}
</ul>{note}
</section>""")
    return "\n\n".join(out), n


def validate(spec):
    if not spec.get("title"):
        sys.exit("В checklist.json нет title")
    if not spec.get("sections"):
        sys.exit("В checklist.json нет sections")
    for i, sec in enumerate(spec["sections"], start=1):
        if not sec.get("title") or not sec.get("items"):
            sys.exit(f"Раздел {i}: нужны title и непустой items")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("checklist", help="JSON с описанием чеклиста")
    ap.add_argument("out", help="выходной HTML-файл")
    ap.add_argument("--keep", help="дополнительно: txt для вставки в Google Keep "
                                   "(разделы ЗАГЛАВНЫМИ, пункты строками)")
    args = ap.parse_args()

    spec = json.load(open(args.checklist, encoding="utf-8"))
    validate(spec)

    if args.keep:
        lines = []
        for sec in spec["sections"]:
            lines.append(sec["title"].upper())
            lines += sec["items"]
            if sec.get("note"):
                lines.append(f"({sec['note']})")
            lines.append("")
        open(args.keep, "w", encoding="utf-8").write("\n".join(lines).strip() + "\n")
        print(f"✓ {args.keep}: для Google Keep", file=sys.stderr)

    sections_html, total = render_sections(spec["sections"])
    html = (TEMPLATE
            .replace("%%TITLE%%", esc_html(spec["title"]))
            .replace("%%SUBTITLE%%", esc_html(spec.get("subtitle", "")))
            .replace("%%STORAGE_KEY%%", spec.get("storage_key", "routegenChecklist"))
            .replace("%%SECTIONS%%", sections_html))
    open(args.out, "w", encoding="utf-8").write(html + "\n")
    print(f"✓ {args.out}: {len(spec['sections'])} разделов, {total} пунктов", file=sys.stderr)


if __name__ == "__main__":
    main()
