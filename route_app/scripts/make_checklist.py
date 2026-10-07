#!/usr/bin/env python3
"""make_checklist.py — генератор интерактивного чеклиста похода (F8).

По JSON-описанию производит один самодостаточный HTML-файл:
- ноль внешних зависимостей (инлайн CSS/JS, системные шрифты, кириллица);
- отметки сохраняются в localStorage браузера (работает офлайн);
- озвучка НЕОТМЕЧЕННЫХ пунктов через Web Speech API (голос браузера, ru-RU):
  кнопка 🔊 у раздела, «Читать всё», «Стоп»;
- счётчики по разделам и общий прогресс; @media print; мобильная вёрстка.

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
  :root{--paper:#b0c6b3;--ink:#111;--crim:#db3356;--card:#fdfdfb;--line:#7a947e}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--paper);color:var(--ink);font:16px/1.55 -apple-system,"Segoe UI",Roboto,sans-serif;padding:18px}
  .wrap{max-width:760px;margin:0 auto}
  h1{font-family:Georgia,serif;font-size:1.7rem;margin:8px 0 2px}
  .sub{font-size:.9rem;opacity:.85;margin-bottom:14px}
  .toolbar{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:2px solid var(--ink);display:flex;gap:8px;flex-wrap:wrap;z-index:5;margin-bottom:14px}
  button{font:600 .92rem/1 inherit;padding:9px 14px;border:2px solid var(--ink);background:var(--card);cursor:pointer;border-radius:6px}
  button:hover{background:var(--ink);color:var(--paper)}
  button.reading{background:var(--crim);border-color:var(--crim);color:#fff}
  .progress{font:600 .95rem/1 Georgia,serif;align-self:center;margin-left:auto}
  section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin-bottom:14px}
  h2{font-family:Georgia,serif;font-size:1.15rem;display:flex;align-items:center;gap:10px;margin-bottom:8px;cursor:pointer}
  h2 .speak{font-size:.8rem;padding:5px 10px;border-width:1px}
  h2 .cnt{margin-left:auto;font:600 .85rem/1 inherit;color:var(--crim)}
  ul{list-style:none}
  li{display:flex;gap:10px;padding:6px 2px;border-bottom:1px dashed var(--line);align-items:flex-start}
  li:last-child{border-bottom:none}
  input[type=checkbox]{width:20px;height:20px;margin-top:2px;accent-color:var(--crim);flex-shrink:0;cursor:pointer}
  label{cursor:pointer;flex:1}
  li.done label{text-decoration:line-through;opacity:.5}
  .note{font-size:.85rem;opacity:.8;margin-top:8px;font-style:italic}
  @media print{
    body{background:#fff}
    .toolbar{display:none}
    section{break-inside:avoid;border:1px solid #999}
  }
</style>
</head>
<body>
<div class="wrap">
<h1>%%TITLE%%</h1>
<p class="sub">%%SUBTITLE%%</p>

<div class="toolbar">
  <button id="readAll">&#x1F50A; Читать всё</button>
  <button id="stopRead">&#x23F9; Стоп</button>
  <button id="reset">&#x21BA; Сбросить отметки</button>
  <span class="progress" id="progress">0 / 0</span>
</div>

%%SECTIONS%%
</div>
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
<h2 onclick="speakSec(this)">{si} · {esc_html(sec["title"])} <button class="speak" onclick="event.stopPropagation();speakSec(this.parentElement)">&#x1F50A;</button><span class="cnt"></span></h2>
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
