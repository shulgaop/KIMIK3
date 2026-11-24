# CODE_GUIDE.md — справочник функций

Генерируется из кода (`python3 scripts/make_code_guide.py` из route_app/) —
не править руками. Обязателен к обновлению в том же коммите, что и код
(AGENTS.md, раздел «Стандарты кода»).

## `scripts/atlas.py`
_project-atlas: persistent project memory for agent work on large corpora._

Константы: `OUT_DIR, ATLAS_JSON, ATLAS_MD, JOBS_DIR, RESULTS_DIR, SKIP_DIRS, SKIP_FILES, MAX_FILE_SIZE, CODE_EXTS, DOC_EXTS, SHEET_EXTS, IMG_EXTS, STOPWORDS, PART_NUM_RE, WORD_RE, PY_SYMBOL_RE, JS_SYMBOL_RE`

- `sha1_file(path)` — —
- `_docx_outline(path)` — Outline from .docx using only stdlib (docx is a zip of XML).
- `_xlsx_outline(path)` — —
- `_pdf_outline(path)` — —
- `_text_outline(path, ext)` — —
- `extract_file(path, rel)` — —
- `scan(root)` — —
- `build_clusters(files, min_shared, max_clusters)` — LLM-free clustering: files sharing >= min_shared keywords form a cluster.
- `render_atlas_md(root, files, clusters, jobs_summary)` — —
- `out_root(root)` — —
- `cmd_build(root)` — —
- `cmd_update(root)` — —
- `cmd_query(root, text)` — —
- `cmd_related(root, target)` — —
- `_job_path(root, job)` — —
- `cmd_manifest(root, job, targets)` — —
- `_set_status(root, job, file, status, note)` — —
- `cmd_status(root, job)` — —
- `jobs_summary(root)` — —
- `main()` — —

## `scripts/budget.py`
_budget.py — бюджет поездки кодом (обобщение budget.py проекта Япония)._

- `load_currency_module()` — —
- `compute(items, members, days, base)` — Итоги по валютам + конвертация в базовую по живому курсу.
- `to_markdown(rows, totals, base, converted, rate_note, members, days)` — —
- `main()` — —

## `scripts/build_gpx_from_osm.py`
_Сборка GPX из файла OSM API (/relation/<id>/full)._

Константы: `SKIP_ROLES`

- `parse_osm(path)` — Возвращает (узлы, линии, список way-участков отношения в порядке членов).
- `chain_segments(segments)` — Склеивает список сегментов в цепочку по совпадающим концам.
- `main()` — Точка входа: читает OSM XML, пишет GPX, печатает число точек.

## `scripts/check_links.py`
_check_links.py — проверка комплекта выдачи перед публикацией._

- `internal_links(folder)` — Все внутренние ссылки HTML-файлов → абсолютные пути целей.
- `http_links(folder)` — Все внешние http(s)-ссылки.
- `main()` — —

## `scripts/color_route_by_days.py`
_Скрипт для раскраски маршрута по дням в Google Earth._

Константы: `DAY_COLORS, GPX_NS, KML_NS`

- `parse_gpx(gpx_file)` — Парсит GPX-файл и возвращает список точек (lat, lon, ele, time).
- `group_by_day(points)` — Группирует точки по дням.
- `create_kml(days, output_file)` — Создаёт KML-файл с цветными линиями для каждого дня.
- `main()` — —

## `scripts/currency.py`
_currency.py — курсы любых национальных валют на дату запроса (F10)._

Константы: `API, FROM_DEFAULT`

- `fetch_rates(base)` — Курсы «1 <base> = X <любая валюта>» на сегодня. Бросает SystemExit при сбое.
- `build_rows(codes, from_list)` — Таблица: каждая целевая валюта против каждой опорной.
- `main()` — —

## `scripts/daylight.py`
_daylight.py — световой день и ночное небо для точек маршрута._

Константы: `NEW_MOON_EPOCH, SYNODIC, PHASES`

- `tz_offset(tzid, d, fallback_hours)` — —
- `sun_times(d, lat, lon)` — Рассвет/закат (UTC-минуты от полуночи) по формулам NOAA.
- `moon(d)` — Возраст Луны (сутки), фаза, освещённость диска.
- `fmt_utc(utc_min, offset)` — —
- `main()` — —

## `scripts/fetch_osm_gpx.py`
_Сборка GPX из OSM-отношения (Overpass API) для маршрута Японии._

Константы: `OVERPASS`

- `fetch_relation(rel_id)` — Возвращает JSON Overpass с полной геометрией отношения (зеркала по очереди).
- `relation_to_points(data)` — Собирает точки всех way-участков отношения в один список (lat, lon).
- `write_gpx(points, path, name)` — Пишет точки в GPX 1.1 (trkpt lat/lon, ele=0 при отсутствии данных).
- `main()` — Точка входа: relation_id, выходной файл, имя трека из argv.

## `scripts/first_aid.py`
_first_aid.py — модуль «Аптечка»: чеклист медикаментов + напоминания о приёме._

Константы: `DISCLAIMER, BASE_ITEMS, CARE_ITEMS, ALTITUDE_ITEMS, DOCTOR_ITEMS, ALTITUDE_RULES`

- `build_checklist(max_ele)` — Чеклист аптечки в формате make_checklist.py.
- `build_reminders(points, start, end, tzid)` — События-напоминания (формат make_ics.py): ежедневный приём + старт профилактики.
- `main()` — —

## `scripts/gear.py`
_gear.py — весовой чеклист снаряжения по методике LighterPack (F12)._

Константы: `ORIENTERS`

- `load_items(path)` — —
- `totals(items, members)` — Итоги LighterPack. Всё в граммах; shared делится на членов команды.
- `to_markdown(items, t, members)` — —
- `main()` — —

## `scripts/gpx_analyze.py`
_gpx_analyze.py — разбор GPX-трека горного маршрута._

Константы: `NS, R`

- `haversine(lat1, lon1, lat2, lon2)` — —
- `azimuth(lat1, lon1, lat2, lon2)` — Истинный азимут из точки 1 в точку 2, градусы 0..360.
- `compass(deg)` — —
- `load_gpx(path)` — —
- `cumulative(trkpts)` — —
- `project(trkpts, dist, lat, lon)` — Ближайшая точка трека -> индекс, км от старта, высота, дистанция до неё (м).
- `leg_stats(trkpts, dist, i1, i2)` — Набор/сброс и азимут плеча между индексами трека.
- `window_gradients(trkpts, dist, window_m)` — Максимальный уклон скользящим окном (метров по треку). Возвращает градусы и где.
- `main()` — —

## `scripts/hike_report.py`
_============================================================_

Константы: `PHOTO_EXT, VIDEO_EXT, EPOCH_1904, DJI_TIMEZONE_OFFSET, OFFLINE_MAP, OFFLINE_MIN_ZOOM, OFFLINE_MAX_ZOOM, MAX_OFFLINE_TILES, OFFLINE_TILE_URL, GPX_TIMEZONE_OFFSET, TRACK_MAX_GAP_MIN, PLAN_INTERPOLATION, HAVE_RG, HAVE_PYOSMO, ISO6709_RE, DJI_NAME_RE, CORRECTIONS_FILE`

- `_dms_to_deg(dms, ref)` — Градусы/минуты/секунды из EXIF -> десятичные градусы.
- `photo_meta(path)` — Возвращает (lat, lon, dt) для фотографии.
- `video_meta(path)` — Возвращает (lat, lon, dt) для видео. Ищет атом ©xyz и время mvhd.
- `dt_from_filename(path)` — Дата/время съёмки из имени файла DJI: DJI_20260906095623_0004_D.MP4
- `parse_gpx(path)` — Читает GPX-файл ->
- `nearest_track_point(track, dt, max_gap_min)` — Ближайшая по времени точка трека к моменту dt (бинарный поиск).
- `dji_track(path)` — Извлекает GPS-трек из видео DJI через pyosmogps.
- `_deg2num(lat, lon, z)` — Координаты -> номер тайла (схема slippy map).
- `download_offline_tiles(records, folder)` — Скачивает тайлы (источник — OFFLINE_TILE_URL), покрывающие весь
- `coords_ok(lat, lon)` — —
- `thumbnail_b64(path, max_px)` — Маленькое превью фото в base64 для всплывающего окна на карте.
- `video_frame_b64(path, sec, max_px)` — Кадр-превью из видео через ffmpeg (ставится пакетом imageio-ffmpeg).
- `load_corrections(root)` — Читает файл ручных правок {файл: [lat, lon]}, скачанный с карты.
- `scan_folder(root)` — —
- `nearest_plan_idx(plan, lat, lon)` — Индекс ближайшей точки планового маршрута к (lat, lon).
- `build_plan_anchors(plan, track, pending_dts)` — Опорные точки [(время, индекс_на_плане)] для интерполяции:
- `interp_plan(plan, anchors, dt)` — Позиция на плановом маршруте для момента dt: линейная
- `ask_coord_mode()` — Спрашивает, откуда брать координаты для файлов.
- `ask_offline()` — Спрашивает, скачивать ли локальные тайлы для офлайн-карты.
- `ask_dji_mode()` — Интерактивный выбор способа обработки видео DJI.
- `main()` — —

## `scripts/import_audioguide.py`
_import_audioguide.py — импорт готового аудиогида (mp3) и привязка к точкам 🎧._

- `norm(s)` — Нормализация имени для сопоставления: мелкие буквы, только слова.
- `main()` — —

## `scripts/llm.py`
_llm.py — LLM-слой через OpenRouter (F4: генерация гида и др.)._

Константы: `API, CONFIG, PROVIDERS, FREE_PREFERENCE, ROUTE_TYPES, GUIDE_SYSTEM, AUDIO_SYSTEM`

- `load_config()` — Конфиг: {"provider": ..., "keys": {провайдер: ключ}, "models": {...}}.
- `save_config(cfg)` — —
- `get_provider(cli)` — —
- `get_key(cli_key, provider)` — —
- `_post(url, payload, key, provider, timeout)` — —
- `chat(messages, model, key, provider, max_tokens, temperature)` — Один запрос к провайдеру с ретраями на сетевые сбои.
- `candidate_models(preferred, key, provider)` — Очередь моделей: явно заданная (без фолбэка) или цепочка бесплатных
- `list_free_models(key)` — Живой список бесплатных моделей OpenRouter (ключ не нужен).
- `default_model(key)` — Самая предпочтительная из доступных бесплатных моделей.
- `build_guide_context(project)` — Контекст генерации из файлов проекта + обучающих материалов.
- `chat_with_fallback(messages, explicit_model, key, provider, max_tokens)` — Запрос с перебором бесплатных моделей (провайдеры бывают перегружены).
- `generate_guide(project, model, key, provider, out_name)` — Генерация MD-гида проекта → выходные/Гид.md. Возвращает путь.
- `generate_audio_texts(project, model, key, provider, out_name)` — Тексты аудиогида (формат tts_audioguide.py) → выходные/аудиотексты.json.
- `main()` — —

## `scripts/make_checklist.py`
_make_checklist.py — генератор интерактивного чеклиста похода (F8)._

Константы: `TEMPLATE`

- `esc_html(text)` — —
- `render_sections(sections)` — HTML разделов: нумерация сквозная, id чекбоксов c1..cN.
- `validate(spec)` — —
- `main()` — —

## `scripts/make_guide_html.py`
_make_guide_html.py — офлайн HTML-версия путеводителя из Гид.md._

Константы: `CSS`

- `load_gpx_analyze()` — —
- `profile_svg(gpx_path, points_path, width, height)` — SVG-профиль высот: линия трека + точки программы с подписями.
- `photos_by_day(project)` — Фото по дням из выходные/фото_карта.json (photo_sort) и фотометки.json
- `inject_photos(md_text, by_day)` — После заголовков «##/### День N …» вставить ряд превью фото дня (raw HTML).
- `build_html(md_text, title, svg)` — Собрать автономный HTML: заголовок, содержание, профиль, текст и таблицы.
- `main()` — —

## `scripts/make_ics.py`
_make_ics.py — генерация ICS-календаря похода для импорта в Google Календарь._

- `esc(text)` — —
- `make_event(ev)` — —
- `main()` — —

## `scripts/make_kml.py`
_make_kml.py — генерация KML для Google Earth из GPX + жёсткая валидация._

Константы: `NS, KML_HEADER, KML_FOOTER, DAY_COLORS`

- `load_track(path)` — —
- `cumdist(pts)` — —
- `style_block(sid, color)` — —
- `build(pts, dist, splits_km, marks)` — —
- `validate(path, bbox)` — XML валиден; все координаты (точки и линии) в bbox; styleUrl↔id.
- `main()` — —

## `scripts/make_report.py`
_make_report.py — отчёт о пройденном походе (по образцу отчётов о категорийных_

Константы: `R, GPX_NS`

- `hav(lat1, lon1, lat2, lon2)` — —
- `load_recorded_track(gpx_path, tz_hours)` — Точки трека с временем и высотой → [(local_date, lat, lon, ele, dt_local)].
- `day_stats(pts)` — Статистика одного дня по его точкам трека.
- `split_days(track)` — Группировка точек по локальной дате → [(день N, дата, точки)].
- `split_description(text)` — Описание → {номер дня: текст}; без маркера — в «общие».
- `load_notes(path)` — Дописки: абзац «день N: …» → к дню; иначе — в общие.
- `build_report_md(title, days, desc_blocks, notes, weather_fact, track_days)` — Сборка MD-отчёта: титул, сводка, дни (статистика + события), погода, выводы.
- `weather_fact_md(project_out)` — Таблица фактической погоды из погода.json (режим fact), если есть.
- `main()` — —

## `scripts/make_status.py`
_make_status.py — снимок проекта СТАТУС_<Маршрут>.md (F9)._

Константы: `OUT_DIRS, SKIP_DIRS, MARK_RE`

- `scan(project)` — Все файлы проекта: отн. путь -> {size, mtime, sha1}.
- `is_output(rel)` — —
- `human_size(n)` — —
- `load_prev(status_path)` — Данные прошлого снимка: файлы + сохраняемые разделы.
- `diff(prev, cur)` — —
- `main()` — —

## `scripts/photo_marks.py`
_photo_marks.py — фотометки: привязка фото и видео к точкам аудиогида._

Константы: `PHOTO_EXT, RE_DJI, KML_HEADER, KML_FOOTER`

- `xesc(text)` — —
- `load_audio_points(gpx_path)` — Точки аудиогида из GPX: wpt с именем «🎧 NN …».
- `media_datetime(path, exif_dt)` — Время съёмки: EXIF, для видео DJI — из имени файла.
- `build_kml(audio_pts, marks, photos_dir_name)` — KML: слой точек аудиогида + фотометки, сгруппированные по трекам.
- `main()` — —

## `scripts/photo_sort.py`
_photo_sort.py — сортировка фотографий похода по точкам и дням маршрута._

Константы: `R, GPX_NS, PHOTO_EXT`

- `haversine(lat1, lon1, lat2, lon2)` — —
- `read_exif(path)` — GPS и время съёмки из EXIF. Возвращает {lat, lon, dt} с None-полями.
- `load_track_times(gpx_path)` — Точки трека с таймстемпами: [(datetime, lat, lon)], по времени.
- `interp_track(track, dt)` — Позиция на треке в момент dt (интерполяция между соседними точками).
- `nearest_point(points, lat, lon)` — Ближайшая точка маршрута: (индекс, дистанция м).
- `day_number(dt, start)` — День похода по дате съёмки (день 1 = дата старта); None, если вне дат.
- `build_html(report, title)` — Офлайн HTML-отчёт: оболочка Trek Fourge, группы, сетка фото и печать A4.
- `main()` — —

## `scripts/read_program.py`
_read_program.py — чтение программы похода из свободного текста (F1)._

Константы: `MONTHS, RE_COORD, RE_ELE, RE_DATE_FULL, RE_DATE_SHORT, RE_DATE_WORD, RE_DAY, RE_KM`

- `extract_text(path)` — Текст документа по расширению. Бросает SystemExit с понятным сообщением.
- `find_points(lines)` — Черновик точек: строки с высотой и/или координатами. Имя — текст до числа.
- `find_dates(text)` — Все упоминания дат, нормализованные в ISO, где год известен.
- `main()` — —

## `scripts/research.py`
_research.py — сбор фактов по маршруту из открытых источников (без ключей)._

Константы: `UA, WIKI_LANGS, OVERPASS_MIRRORS`

- `get_json(url, timeout)` — —
- `wiki_search(query, lang, limit)` — Поиск статей Википедии: [(title, pageid)].
- `wiki_extract(title, lang, limit)` — Вступление статьи (plain text) + URL.
- `wiki_geosearch(lat, lon, lang, radius, limit)` — Статьи Википедии в радиусе от координат (озёра, пики, сёла рядом).
- `overpass_pois(south, north, west, east)` — Инфраструктура из OSM: родники/вода, хижины, сёла, магазины в bbox.
- `collect_facts(points, region, use_overpass, bbox)` — Собрать факты по всем точкам: поиск + геопоиск Википедии, POI из OSM.
- `to_markdown(facts)` — Дайджест фактов для LLM: по точкам + инфраструктура + источники.
- `main()` — —

## `scripts/sources.py`
_sources.py — реестр источников проекта SOURCES.md (по протоколу проекта Япония)._

Константы: `STATUSES`

- `collect(project)` — Записи реестра: файлы входных + URL источников фактов.
- `load_manual(project)` — Ручные строки прошлого SOURCES.md (статусы «ожидается» и др.) — переносим.
- `main()` — —

## `scripts/test_regression.py`
_test_regression.py — регрессия на эталоне «Фанские горы» (без pytest)._

Константы: `BASE, EX, GPX`

- `check(name, cond, detail)` — —
- `run(script)` — —
- `main()` — —

## `scripts/tts_audioguide.py`
_tts_audioguide.py — генерация аудиогида mp3 через edge-tts с контролем качества._

- `async gen_one(text, voice, rate, path, retries)` — —
- `probe_duration(path)` — Длительность mp3 через ffprobe; None, если ffprobe не установлен.
- `async main()` — —

## `scripts/weather.py`
_weather.py — погодный движок (F3) для точек маршрута._

Константы: `LAPSE_C_PER_100M, FORECAST_DAYS, API_FORECAST, API_ARCHIVE, DAILY_COMMON`

- `fetch(api, lat, lon, start, end, extra)` — Запрос daily-параметров Open-Meteo. Возвращает разобранный JSON.
- `lapse_correct(t, ele_point, ele_grid)` — Пересчёт температуры на высоту точки градиентом −0,6 °C/100 м.
- `compass(deg)` — —
- `mode_for(start, end, today)` — Режим по датам: fact — весь интервал в прошлом; forecast — старт внутри
- `days_from_daily(daily, ele_point, ele_grid, with_prob)` — Список дней из daily-блока API с поправкой температур на высоту.
- `point_fact(p, start, end)` — Факт (реанализ ERA5) за прошедшие даты.
- `point_forecast(p, start, end, today)` — Прогноз; дни за пределами горизонта API отсутствуют (partial=True).
- `point_climate(p, start, end, today, years)` — Климатические нормы ERA5 по тем же календарным датам за `years` прошлых лет.
- `recheck_date(start, today)` — Когда прогноз станет доступен: старт минус горизонт прогноза.
- `to_markdown(report)` — Блок «Погода» для MD-гида: таблица по каждой точке.
- `main()` — —

## `webapp.py`
_webapp.py — веб-интерфейс мастера генерации маршрутов (ТЗ, v2)._

Константы: `BASE, SCRIPTS, PROJECTS, LEARN, RULES_FILE, EXAMPLES_FILE, DEFAULT_ROUTE_CONFIG, STEPS, MEDIA_EXT, DEFAULT_RULES`

- `GET /` → `index()`
- `GET /api/projects` → `list_projects()`
- `POST /api/projects` → `create_project()`
- `GET /api/projects/{name}/config` → `get_config()`
- `PUT /api/projects/{name}/config` → `put_config()`
- `POST /api/projects/{name}/upload` → `upload()`
- `GET /api/projects/{name}/files` → `files()`
- `GET /api/projects/{name}/read` → `read_file()`
- `POST /api/projects/{name}/run/{step}` → `run_step()`
- `POST /api/projects/{name}/note` → `add_note()`
- `GET /api/browse` → `browse()`
- `GET /api/projects/{name}/download` → `download()`
- `GET /api/projects/{name}/zip` → `zip_project()`
- `GET /api/llm` → `llm_get()`
- `PUT /api/llm` → `llm_put()`
- `GET /api/llm/models` → `llm_models()`
- `GET /api/learn` → `learn_get()`
- `PUT /api/learn/rules` → `learn_rules()`
- `POST /api/learn/examples` → `learn_example_add()`
- `DELETE /api/learn/examples/{idx}` → `learn_example_del()`
- `route_config(d)` — Конфиг маршрута проекта: route.json поверх значений по умолчанию.
- `safe_name(name)` — Имя проекта/файла: без слэшей и служебных символов, кириллица разрешена.
- `project_dir(name)` — —
- `run_script(args, cwd, timeout, stdin_text, env_extra)` — Запуск скрипта из scripts/ с UTF-8-окружением; возвращает (ok, stdout, stderr).
- `update_status(proj)` — F9-контракт: СТАТУС обновляется после каждого изменения выдачи.
- `load_script_module(name)` — Импорт модуля из scripts/ по имени без .py (скрипты — не пакет, поэтому так).
- `track_bbox(gpx_path, margin)` — Bbox трека (S, N, W, E) с полем margin градусов — для валидации KML.
- `index()` — —
- `list_projects()` — —
- `create_project(payload)` — —
- `get_config(name)` — —
- `put_config(name, payload)` — —
- `upload(name, payload)` — Сохранить входной файл: {"filename", "text"} для текста или
- `files(name)` — —
- `read_file(name, path)` — —
- `step_program(d, params)` — F1: прочитать программу (PDF/DOCX/TXT), извлечь текст и черновик точек.
- `step_analyze(d, params)` — —
- `step_weather(d, params)` — —
- `step_kml(d, params)` — —
- `step_ics(d, params)` — —
- `step_checklist(d, params)` — —
- `step_status(d, params)` — —
- `watch_and_planned(d)` — Треки проекта: записанный с часов (приоритет для времени) и плановый.
- `step_photos(d, params)` — Сортировка фото по точкам/дням маршрута (EXIF GPS или время на треке).
- `step_marks(d, params)` — Фотометки: привязка фото/видео к точкам аудиогида 🎧 (GPX проекта).
- `step_photos_all(d, params)` — Всё про фото одной кнопкой: сортировка → фотометки → гео-отчёт с картой.
- `run_hike_report(d, folder, params)` — Запуск hike_report.py с настройками модуля «Фотоотчёт»:
- `step_report_map(d, params)` — Только гео-фото-отчёт с картой (hike_report) с настройками модуля.
- `step_guide(d, params)` — F4: генерация MD-гида через выбранного LLM-провайдера (настройки шага).
- `step_research(d, params)` — Сбор фактов по маршруту (Википедия + OSM) → Факты.md для LLM-гида.
- `step_guide_html(d, params)` — HTML-версия Гид.md (офлайн, профиль высот, печать).
- `step_audio_texts(d, params)` — Тексты аудиогида через LLM (числа прописью) → аудиотексты.json.
- `step_tts(d, params)` — Озвучка аудиотекстов (edge-tts) → выходные/Аудиогид/*.mp3 + zip.
- `step_daylight(d, params)` — Световой день и ночное небо: рассвет/закат (NOAA), фаза Луны.
- `step_first_aid(d, params)` — Аптечка: чеклист (HTML + Keep) и ICS-напоминания о приёме.
- `step_currency(d, params)` — Курсы валют стран маршрута (F10) → Деньги.md.
- `step_report(d, params)` — Отчёт о пройденном походе: записанный трек + описание + дописки.
- `step_gear(d, params)` — F12: весовой чеклист снаряжения (LighterPack) → Снаряжение.md.
- `step_sources(d, params)` — Реестр источников SOURCES.md (входные + источники фактов).
- `step_audio_import(d, params)` — Импорт готового аудиогида (mp3-папка) с привязкой к точкам 🎧 по именам.
- `step_publish(d, params)` — Публикация выдачи на GitHub Pages: app/guides/<проект>/ + git push.
- `step_osm_gpx(d, params)` — GPX-трек из OSM-отношения (Overpass), если у пользователя нет трека.
- `step_budget(d, params)` — Бюджет поездки кодом (бюджет.json) → Бюджет.md; курсы через currency.py.
- `step_check_links(d, params)` — Проверка внутренних ссылок выдачи перед публикацией.
- `run_step(name, step, payload)` — —
- `add_note(name, payload)` — Дописка к отчёту: свободный текст И/ИЛИ файл-вложение (PDF/DOCX/TXT —
- `browse(path)` — Проводник по папкам компьютера для выбора директории с фото.
- `download(name, path)` — —
- `zip_project(name)` — —
- `_llm_mod()` — Модуль llm.py (OpenRouter) — ленивый импорт, чтобы без ключа мастер работал.
- `llm_get()` — —
- `llm_put(payload)` — —
- `llm_models(provider)` — Модели провайдера: OpenRouter — живой список free; Kimi/Claude — дефолт.
- `read_examples()` — —
- `learn_get()` — —
- `learn_rules(payload)` — —
- `learn_example_add(payload)` — Пример = эталонная пара «вход → фрагмент выдачи» (few-shot для F4).
- `learn_example_del(idx)` — —
- `lan_ip()` — Локальный IP для доступа с телефона (та же Wi-Fi сеть).
- `main()` — —

