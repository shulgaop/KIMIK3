#!/usr/bin/env python3
"""read_program.py — чтение программы похода из свободного текста (F1).

Вход: PDF, DOCX, TXT/MD — описание маршрута в свободной форме.
(Старый бинарный .doc не поддерживается — пересохраните как .docx.)

Что делает кодом:
- извлекает весь текст (PDF — pypdf; DOCX — stdlib: zipfile + XML);
- эвристиками находит: координаты (десятичные пары), высоты (…м), даты
  (дд.мм.гггг, дд.мм, «12 сентября»), дни («День 3», «Д3»), километраж (…км);
- собирает ЧЕРНОВИК points.json из строк, где есть высота и/или координаты
  (имя — текст строки до числа). Черновик ОБЯЗАТЕЛЬНО проверяет человек
  в мастере перед использованием — эвристика не заменяет смысловой разбор.

Использование:
  python3 read_program.py программа.pdf
  python3 read_program.py программа.docx --out-text программа.txt --out-points points_draft.json

Вывод: JSON-отчёт в stdout (сводка — в stderr).
"""
import argparse, json, re, sys, zipfile
import xml.etree.ElementTree as ET

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]

RE_COORD = re.compile(r"(?<![\d.])(3[0-9]|4[0-2])\.\d{1,5}\s*[,;]\s*(6[0-9]|7[0-5])\.\d{1,5}(?![\d.])")
RE_ELE = re.compile(r"(?<![\d.,])([2-9]\d{2}|[1-5]\d{3})\s*(?:м|m)\b")
RE_DATE_FULL = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
RE_DATE_SHORT = re.compile(r"\b(\d{1,2})\.(\d{1,2})(?!\.\d)\b")
RE_DATE_WORD = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?", re.I)
RE_DAY = re.compile(r"\b(?:день|д)\s*\.?\s*(\d{1,2})\b", re.I)
RE_KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*км")


def extract_text(path):
    """Текст документа по расширению. Бросает SystemExit с понятным сообщением."""
    ext = path.rsplit(".", 1)[-1].lower()
    if ext in ("txt", "md"):
        return open(path, encoding="utf-8", errors="replace").read()
    if ext == "docx":
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile):
            sys.exit("⚠️  Не похоже на DOCX (нет word/document.xml). Старый .doc — пересохраните как .docx")
        root = ET.fromstring(xml)
        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paras = []
        for p in root.iter(w + "p"):
            paras.append("".join(t.text or "" for t in p.iter(w + "t")))
        return "\n".join(paras)
    if ext == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("⚠️  Для PDF нужен pypdf: pip install pypdf")
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == "doc":
        sys.exit("⚠️  Бинарный .doc не читается — пересохраните в Word как .docx")
    sys.exit(f"⚠️  Неподдерживаемый формат: .{ext} (нужны pdf, docx, txt, md)")


def find_points(lines):
    """Черновик точек: строки с высотой и/или координатами. Имя — текст до числа."""
    points, seen = [], set()
    for ln in lines:
        ln = ln.strip()
        if len(ln) < 5:
            continue
        coord = RE_COORD.search(ln)
        ele = RE_ELE.search(ln)
        if not (coord or ele):
            continue
        cut = min(x.start() for x in (coord, ele) if x)
        name = re.sub(r"[\s,;:—–(\[«\"'-]+$", "", ln[:cut]).strip()
        name = re.sub(r"^(?:день|д)\s*\.?\s*\d{1,2}\s*[.:)]?\s*", "", name, flags=re.I)  # «День 3.»
        name = re.sub(r"^\d{1,2}\s*(?:день|д)?[.:)]?\s*", "", name, flags=re.I)          # «3.»
        if len(name) < 3 or len(name) > 80:
            name = name[:80] if len(name) > 80 else ""
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        p = {"name": name, "source_line": ln[:150]}
        if coord:
            lat_s, lon_s = re.split(r"[,;]", coord.group(0))
            p["lat"], p["lon"] = float(lat_s), float(lon_s)
        if ele:
            p["ele"] = int(ele.group(1))
        p["confidence"] = "high" if (coord and ele) else "low"
        points.append(p)
    return points


def find_dates(text):
    """Все упоминания дат, нормализованные в ISO, где год известен."""
    found = []
    for d, m, y in RE_DATE_FULL.findall(text):
        found.append(f"{y}-{int(m):02d}-{int(d):02d}")
    for m in RE_DATE_WORD.finditer(text):
        d, mon, y = m.group(1), MONTHS.index(m.group(2).lower()) + 1, m.group(3)
        found.append(f"{y or '????'}-{mon:02d}-{int(d):02d}")
    # короткие дд.мм — только как отдельный список, без угадывания года
    short = sorted({f"{int(m):02d}-{int(d):02d}" for d, m in RE_DATE_SHORT.findall(text)
                    if int(m) <= 12 and int(d) <= 31})
    return sorted(set(found)), short


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("program", help="PDF/DOCX/TXT/MD с описанием маршрута")
    ap.add_argument("--out-text", help="куда записать извлечённый текст")
    ap.add_argument("--out-points", help="куда записать черновик points.json")
    args = ap.parse_args()

    text = extract_text(args.program)
    if len(text.strip()) < 50:
        sys.exit("⚠️  Текста почти нет — возможно, это скан (нужен OCR, не входит в MVP)")
    lines = [l for l in text.splitlines() if l.strip()]

    points = find_points(lines)
    dates_iso, dates_short = find_dates(text)
    days = sorted({int(d) for d in RE_DAY.findall(text) if 1 <= int(d) <= 30})
    kms = [float(k.replace(",", ".")) for k in RE_KM.findall(text)]

    report = {
        "source": args.program,
        "chars": len(text),
        "points_draft": points,
        "dates_iso": dates_iso,
        "dates_short_no_year": dates_short,
        "days_mentioned": days,
        "km_mentions": kms,
        "warnings": [],
    }
    if points and all(p["confidence"] == "low" for p in points):
        report["warnings"].append("координаты в тексте не найдены — точки только по высотам, "
                                  "проверьте и дополните вручную")
    if not days:
        report["warnings"].append("маркеры дней («День N») не найдены — структуру дней "
                                  "задайте вручную")
    if not dates_iso:
        report["warnings"].append("даты с годом не найдены — укажите даты в мастере")

    if args.out_text:
        open(args.out_text, "w", encoding="utf-8").write(text)
    if args.out_points:
        clean = [{k: v for k, v in p.items() if k != "source_line"} for p in points]
        open(args.out_points, "w", encoding="utf-8").write(
            json.dumps(clean, ensure_ascii=False, indent=1) + "\n")

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n✓ Текст: {len(text)} символов; точек в черновике: {len(points)} "
          f"(точных: {sum(1 for p in points if p['confidence'] == 'high')}); "
          f"дней: {len(days)}; дат: {len(dates_iso)}", file=sys.stderr)
    for w in report["warnings"]:
        print(f"⚠️  {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
