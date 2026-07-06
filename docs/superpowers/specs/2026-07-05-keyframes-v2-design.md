# Keyframes v2 — анимация видимости, стилей и появления элементов

**Дата:** 2026-07-05
**Статус:** approved — решения ревью внесены (§8), готово к implementation-плану фазы 1
**Область:** ядро animageo (`keyframes.py`, `animageo.py`) + контракт с animageo_web

---

## 1. Постановка задачи

Сегодня keyframe-анимация интерполирует только **геометрическое состояние**
(координаты свободных точек, tparam, числа/углы/булевы) плюс голые списки
`show`/`hide`. Нельзя:

- задавать **эффект появления/скрытия** (нарисовать линию, проявить, вырастить)
  и его тайминг;
- анимировать **стили** элемента между кейфреймами (цвет, прозрачность,
  толщину, размер точки, тип штриха, форму точки);
- менять **подписи** (текст, видимость, цвет, размер шрифта);
- делать **акценты** (мигнуть точкой, обвести элемент);
- управлять **камерой** (пан/зум) по кейфреймам.

Веб-сервис animageo_web — основной потребитель: он снимает состояние
GeoGebra-апплета в кейфреймы, но сейчас захватывает только переменные,
свободные точки, булевы и видимость. Стили там существуют отдельно — как один
глобальный Style JSON на весь рендер (статичные overlay per_name/per_type).

## 2. Текущее состояние — ядро (факты)

### 2.1 Схема JSON v1

```json
{"keyframes": [
  {"t": 0, "values": {"A": [0,0], "x": 35}, "show": [...], "hide": [...], "easing": "smooth"}
]}
```

- `values` — только независимые элементы (`get_independents()`); семантика
  carry-forward: неупомянутое значение держится, интерполяция происходит в
  интервале, **завершающемся** кейфреймом, где значение упомянуто снова.
- `easing` — на кейфрейм (применяется ко входящему интервалу); 5 функций:
  `linear/smooth/in/out/in_out`.
- Интерполяторы: `point`, `tparam_circle` (циклический, с направлением),
  `tparam_linear`, `tparam_hyperbola` (ветка снапится на 0.5), `var`,
  `bool` (снап на 0.5).

### 2.2 Playback (`play_keyframes` → `_play_keyframe_interval`)

- Один sentinel-Mobject с updater'ом: на каждом кадре — применить значения →
  `geo.rebuild()` → `updateGeoElements(updates)` → `mobj.become(CreateMObject(elem))`.
  **Это ключевой факт: механизм per-frame rerender уже существует и стилевая
  анимация может ехать по той же трубе** — стили читаются `_build_render_ctx`
  через resolver при каждом `CreateMObject`.
- `show`/`hide` выполняются **до** интервала отдельными `self.play(...)` с
  захардкоженными `FadeIn`/`FadeOut` и `run_time=0.4`. Следствия:
  - итоговая длительность видео ≠ `t` последнего кейфрейма — каждый батч
    show/hide **добавляет** 0.4 с (show и hide ещё и последовательно);
  - эффект всегда Fade (у `Show()` есть mode `'Create'`, но из кейфреймов он
    недостижим);
  - во время эффекта геометрия стоит — нельзя совместить появление с движением.
- Интервал без интерполяторов → `self.wait(duration)` (updater не ставится).

### 2.3 Что уже есть рядом (строительные блоки)

| Механизм | Где | Что даёт для v2 |
|---|---|---|
| `setElementStyle(names, **props)` / `setVisible` | animageo.py | батчевые записи в `elem.style` + rerender — образец применения стиля |
| `Show(mode='Fade'/'Create')`, `ShowCreate` | animageo.py | прототип entrance-эффектов (Create для штрихов, FadeIn для заливок) |
| `Shade`/`Restore` + `_styles_back` | animageo.py | прототип emphasis/de-emphasis с backup стилей |
| Резолвер стилей (5 слоёв, `elem.style` всегда выигрывает) | style/resolver.py | точка записи анимированных значений; `visible` тоже резолвится через стиль (`_element_visible`) |
| Fast value labels (`ValueLabel`) | ui.py, labels.py | анимация числовых подписей уже решена; менять нельзя только произвольный `label_text` per-frame (перекомпиляция LaTeX) |
| Label placement snapshots (`keyframe_snapshots`) | label_placement.py | pre-pass по кейфреймам — потребует учёта стилей/видимости v2 |
| Условная видимость GGB (`<condition showObject>`) | ggb_parser.py | парсится только простой булев реф, статично — v2 даёт ручную альтернативу |

### 2.4 Анимируемая поверхность (полный реестр `elem.style`)

Из `_build_render_ctx` + `builtin.json`; почти 1:1 совпадает с
`OVERRIDE_KNOWN_KEYS` веб-редактора стилей — то есть веб уже умеет
*редактировать* эти ключи статично, v2 добавляет им ось времени.

| Категория | Ключи | Интерполяция |
|---|---|---|
| Числовые (px) | `stroke_width_px`, `size_px`, `font_size_px`, `arc_size_px`, `arc_shift_px`, `tick_length_px`, `tick_width_px`, `tick_shift_px`, `arrow_length_px`, `arrow_width_px`, `label_radial_offset_px` | lerp |
| Прозрачности | `stroke_opacity`, `fill_opacity` | lerp (0..1) |
| Цвета | `stroke`, `fill`, `label_color` | lerp в цветовом пространстве (§5.3) |
| 2D-оффсет | `label_offset_px` | покомпонентный lerp (уже есть `LabelOffsetInterpolator`) |
| Дискретные | `point_shape`, `stroke_linecap`, `tick_count`, `tick_style`, `angle_range`, `right_angle_marker`, `label_anchor`, `label_visible`, `label_mode`, `z_index`, `z_index_fill` | снап на eased-progress ≥ 0.5 |
| Полудискретные | `stroke_dash_ratio` (число или None=solid) | число↔число — lerp; None↔число — снап |
| Текст | `label_text` | дискретный swap (опц. crossfade позже) |
| Существование | `visible` | не свойство, а **событие** с эффектом входа/выхода (§5.4) |

## 3. Текущее состояние — animageo_web (факты)

- **Кейфрейм на вебе = снимок полного состояния апплета**
  (`GeogebraApplet.vue::captureState()`): `var_values`, `boolean_values`,
  `free_points` (только movable), `visibility.show/hide` (абсолютные списки из
  `getVisible()`). Стили **не** захватываются; стилевые геттеры апплета
  (`getColor`, `getLineStyle`, `getFilling`, `getPointStyle`, …) не вызываются.
- Timeline (Vue) хранится одним JSONB-блобом (`Animation.timeline`), Pydantic
  намеренно нестрогий (`timeline: dict`) — новые поля переживут persistence без
  миграций. **Версионирования схемы нет** — совместимость на толерантности к
  форме (`normalizeKeyframes` на фронте).
- Экспорт: `_convert_timeline_to_animageo` сливает значения в `values`,
  превращает абсолютную видимость в **инкрементальные** `show`/`hide`,
  мапит easing (у веба 17 типов, у ядра 5 — маппинг с потерями), генерирует
  Python-сцену, зовёт `manim render` сабпроцессом → `play_keyframes`.
- Стили: отдельная сущность Style (глобальный JSON на рендер); per-element
  статика — `overlay.per_name`; редактор уже имеет покомпонентные контролы для
  всех ключей реестра (`styleOptions.ts::OVERRIDE_KNOWN_KEYS`).
- Планов/заготовок под стилевую анимацию в animageo_web нет (проверены
  roadmap/TODO/docs).

**Вывод:** веб-модель — это модель «состояний» (state-diff): пользователь
готовит состояние сцены, жмёт «снять кейфрейм». Расширение на стили должно
сохранить эту ментальную модель, а не заставлять рисовать треки.

## 4. Prior art — что говорят зрелые системы

Полный отчёт с источниками — в приложении A. Выжимка, влияющая на решения:

1. **Пять классов свойств** (CSS Animated Properties): continuous numeric /
   color / discrete / text / visibility. Дискретные снапаются на
   eased-progress ≥ 0.5 (нормативное правило CSS; наш `bool` уже так делает).
2. **Цвет**: naive sRGB-lerp даёт грязно-серые середины и уход в фиолетовый;
   CSS Color 4 по умолчанию интерполирует в **Oklab**. Rectangular Oklab (не
   LCH) избегает NaN-hue на ахроматических цветах.
3. **Три модели авторинга**: (1) state-кейфреймы (CSS/WAAPI, наш v1),
   (2) per-property треки (GSAP/Lottie/AE), (3) state-diff (PowerPoint Morph,
   Keynote Magic Move — «два слайда, переход выводится»). Индустриальный
   паттерн: **авторим состояния, компилируем в треки** (так делает и WAAPI, и
   Morph). Независимые треки на авторинг-уровне для геометрии вредны
   (рассинхрон читается как глюк).
4. **Visibility — не свойство, а событие с эффектом**. CSS пришлось вводить
   `@starting-style` + `transition-behavior: allow-discrete`, чтобы вообще
   анимировать появление. Правило гейтинга: во время entrance эффект владеет
   прозрачностью/прогрессом; стилевые треки элемента до первого появления
   держатся на значениях кейфрейма появления.
5. **Таксономия эффектов** (PowerPoint: Entrance/Emphasis/Exit; manim даёт
   геометрически-идиоматичные реализации): entrance — `Create` (прогрессивная
   отрисовка штриха — фирменный жест динамической геометрии), `Write` (текст),
   `DrawBorderThenFill` (полигоны), `FadeIn`, `GrowFromCenter/Point`,
   `GrowArrow`; exit — `Uncreate`, `FadeOut`, `ShrinkToCenter`; emphasis —
   `Indicate`, `Flash`, `Circumscribe`, `ShowPassingFlash` (одноразовые,
   самовосстанавливающиеся → живут в списке событий, не в состоянии).
6. **Easing на сегменте** (объявлен на стартовом кейфрейме сегмента у WAAPI; у
   нас — на конечном; главное — один уровень, без GSAP-овских трёх слоёв
   ease-композиции). Опциональный верхнеуровневый `defaults` (GSAP Timeline).
7. **GeoGebra**: её управляемое состояние (`setColor/setVisible/
   setLineThickness/setPointStyle/setLabelVisible/setCaption/setValue/
   ZoomIn/SetCoordSystem`) ≈ наш целевой реестр почти 1:1 — хорошо для
   захвата с апплета и для будущего JSXGraph-плеера. Чего у GGB нет — таймлайна;
   это и есть value-add animageo. Construction Protocol replay (пошаговый показ
   построения в порядке зависимостей) — самый ценный образовательный жест.
8. **Ловушки**: двойная анимация opacity (эффект входа × трек прозрачности) —
   решается композицией «трек пишет значение, эффект умножает»; текст не
   лерпится (swap / crossfade / matched morph); скрытые интервалы — hold, не
   gap; немонотонный easing может дважды переключить дискретное свойство
   (документировать).

## 5. Предложение: схема и семантика v2

### 5.1 Модель

**Остаёмся на state-кейфреймах** (авторинг = состояние сцены в момент t,
как сейчас и как в вебе), внутри компилируем в per-(element, key) треки с
hold-семантикой. Три альтернативы рассматривались:

- **A. Расширить state-кейфреймы (рекомендую).** Минимальный сдвиг ментальной
  модели, идеально ложится на веб-захват «снял состояние апплета», прямой
  апгрейд v1, легко генерится AI. Минус: нельзя задать разный тайминг двум
  свойствам внутри одного интервала (лечится добавлением кейфрейма).
- **B. Per-property треки (Lottie/GSAP).** Максимальная выразительность,
  но требует нового UI (multi-track editor), ломает захват состояний,
  рассинхрон треков для геометрии вреден. Не сейчас; внутренняя нормализация
  v2 оставляет дверь открытой.
- **C. Чистый state-diff (Morph):** «два состояния — переход выводится» — уже
  почти наш случай; но без явных эффектов входа/выхода и событий не хватает
  выразительности. Берём из него правило вывода переходов, добавляем явные
  `enter/exit/events`.

### 5.2 Схема JSON v2

```json
{
  "version": 2,
  "defaults": {
    "easing": "smooth",
    "enter": {"effect": "fade", "duration": 0.4},
    "exit":  {"effect": "fade", "duration": 0.4}
  },
  "keyframes": [
    {
      "t": 0,
      "values": {"A": [0, 0], "x": 35},
      "visible": {"c": false, "midline": false},
      "styles": {"a": {"stroke": "#1565c0", "stroke_width_px": 2}}
    },
    {
      "t": 2,
      "values": {"A": [4, 4]},
      "visible": {"c": true},
      "enter": {"c": {"effect": "create", "duration": 0.8, "at": 0.2}},
      "styles": {"a": {"stroke": "#d05456", "stroke_width_px": 4}},
      "easing": "smooth"
    },
    {
      "t": 4,
      "styles": {"a": {"stroke": null}},
      "events": [{"at": 0.5, "effect": "indicate", "targets": ["B"], "scale": 1.2}]
    }
  ]
}
```

Семантика:

- **`styles`** — целевое состояние стиля к моменту `t`; carry-forward как у
  `values`; интерполяция в интервале, завершающемся этим кейфреймом; вид
  интерполяции — по реестру (§2.4). `null` = «вернуться к базовому значению»
  (снять override: интерполируем к резолвленному base, в конце удаляем ключ из
  `elem.style`).
- **`visible`** — абсолютная карта состояний видимости на кейфрейме (веб уже
  хранит абсолютные снимки — конвертеру станет проще, чем с инкрементальными
  списками). `show`/`hide` остаются как сахар (v1-совместимость):
  `"show": ["x"]` ≡ `"visible": {"x": true}`.
- **`enter` / `exit`** — эффекты переходов видимости, играются **внутри**
  интервала (по умолчанию с его начала): `effect`, `duration`, `at` (сдвиг от
  начала интервала, сек). Эффекты: `fade`, `create` (прогрессивная отрисовка),
  `grow` (от центра/вершины), `write` (подписи/тексты), `none` (мгновенно);
  exit: `fade`, `uncreate`, `shrink`, `none`. Дефолты — из `defaults`, в
  перспективе per-type (create для штрихов, write для текста).
- **`events`** — одноразовые самовосстанавливающиеся акценты:
  `indicate` (пульс масштаба+цвета), `flash`, `circumscribe`,
  `passing_flash`. Не трогают состояние треков.
- **`easing`** — как в v1 (на входящий интервал); расширить набор функций до
  веб-набора (17), чтобы маппинг стал без потерь. Опционально позже:
  per-element/per-key override.
- **Тайминг**: длительность видео = `t` последнего кейфрейма, точно. Никаких
  вставных 0.4 с. Появление можно совмещать с движением.

**Совместимость:** файл без `"version": 2` играется по старому пути
byte-identical (включая легаси-тайминг show/hide), но с **DeprecationWarning**
(лог-предупреждение с подсказкой миграции). Это защищает существующие анимации
веб-сервиса до миграции конвертера; после перевода конвертера на v2 (фаза 4)
легаси-путь остаётся на один-два минорных релиза и затем удаляется.

### 5.3 Интерполяция

- Единый реестр `ANIMATABLE_STYLE_KEYS: {key -> kind}`
  (`scalar` / `opacity` / `color` / `offset2` / `discrete` / `text`) — один
  источник правды для ядра, валидации, веба и документации.
- **Цвет:** lerp в **Oklab** по умолчанию (чистая numpy-конверсия, ~30 строк,
  без зависимостей), опция `rendering.color_interpolation: "srgb"` для
  желающих. Rectangular Oklab — без hue-NaN на серых.
- **Дискретные:** снап на eased-progress ≥ 0.5 — единое правило (как CSS),
  задокументировать поведение при немонотонном easing.
- **`z_index`:** дискретный снап + особый путь применения — `become()` не
  переносит z_index; нужен явный `set_z_index` после become (и сейчас это
  скрытая мина: смена z_index между кадрами через become молча не применится).

### 5.4 Движок playback

Всё едет через существующий sentinel-updater (принцип единственного писателя):

1. `_build_intervals` дополнительно строит `style_interps`
   (StyleInterpolator(name, key, kind, start, end)) из carry-forward стилевого
   состояния. **Базовые значения** (для ключей, впервые упомянутых, и для
   `null`-revert) снимаются в `play_keyframes` через
   `resolver.resolve(scene, elem, key)` до старта (from_json остаётся без
   scene — парсинг/валидация отдельно, привязка базы — на стороне сцены).
2. `on_frame`: значения → rebuild → **стили в `elem.style`** (снап-ключи — по
   правилу 0.5) → touched-имена в `updates` → `updateGeoElements` (become).
3. **Эффекты входа/выхода/событий — post-become адаптеры**: после
   `updateGeoElements` по активным эффектам считается локальная alpha и
   модифицируется свежий mobject: fade — умножение прозрачностей семейства;
   create/uncreate — `pointwise_become_partial(full, 0, alpha)` (эквивалент
   manim `Create`); grow/shrink — scale вокруг центра/точки; indicate — пульс
   scale+цвет. Умножение поверх become **автоматически решает** конфликт
   «FadeIn против анимируемого fill_opacity» (эффект × трек, не два писателя).
   `elem.visible` переключается в начале enter / в конце exit; add/remove
   mobject — там же.
4. Интервалы только со стилями/эффектами тоже получают updater (сейчас там
   `wait()`).
5. `keyframe_snapshots` (label placement pre-pass): применять на каждом
   кейфрейме не только values+show/hide, но и `styles`+`visible` — иначе
   раскладка посчитается для неправильных bbox (font_size, видимость,
   arc_size влияют на препятствия).
6. `label_text` — дискретный swap (один rerender, bbox-кэш), **никогда** не
   per-frame (перекомпиляция LaTeX ~130–280 мс/кадр). Crossfade — опцией позже.

### 5.5 Новые API ядра

| API | Назначение |
|---|---|
| `get_element_states()` | per-element: тип, `visible`, резолвленные значения ключей реестра, label-инфо — симметрично `get_independent_elements()`, для веб-редактора состояний и вычисления диффов |
| `apply_keyframes_at(seq, t)` | статически применить состояние на момент t (превью кадра на плейхеде сервером, SVG) |
| `reveal_construction(lag=0.3, ...)` | макро: сгенерировать v2-кейфреймы появления всех элементов в топологическом порядке зависимостей (Kahn-уровни уже есть) с per-type эффектами — «replay построения» как у GGB Construction Protocol. Самая дешёвая и самая различающая образовательная фича |
| `@camera` (псевдо-элемент, фаза 5) | `values: {"@camera": {"center": [x,y], "width": w}}` — числовые треки камеры; документировать взаимодействие с `fitView` |

### 5.6 Интеграция с animageo_web (справочно — реализация на стороне animageo_web, вне scope этого проекта)

- Timeline JSON: `"version": 2`, per-keyframe `styles`
  (Record<name, props>), опц. `enter/exit/events`; фронтовый
  `normalizeKeyframes` бэкфиллит старые анимации; Pydantic-passthrough уже
  толерантен. **Ввести поле версии — закрыть найденный gap отсутствия
  версионирования.**
- `_convert_timeline_to_animageo`: прокидывать `styles`/`visible`/`enter`
  прямо (абсолютная видимость вместо инкрементальных списков), выровнять
  easing-набор.
- UI: инспектор «состояние элемента на кейфрейме» из готовых контролов
  style-editor'а (`OVERRIDE_KNOWN_KEYS` ≈ реестр §2.4). Захват стилей с
  апплета возможен (незадействованные `getColor/getLineStyle/getFilling/...`),
  но рекомендую авторинг стилевых изменений в таймлайн-инспекторе (стили —
  осознанное решение автора анимации, а не побочный снимок апплета; captureState
  оставить только для геометрии/видимости). Открытый вопрос §8.
- Endpoint на `get_element_states()` — заполнение инспектора и диффы.

## 6. Полная карта «что может меняться между кейфреймами»

Сводная приоритизация (P1 = ядро запроса, P3 = будущее):

| # | Что | Приоритет | Механизм |
|---|---|---|---|
| 1 | Геометрия (points/tparam/vars/bool) | есть (v1) | interpolators |
| 2 | Видимость + эффекты входа/выхода (fade/create/grow/write) | **P1** | события + адаптеры |
| 3 | Цвета stroke/fill/label_color | **P1** | color-lerp (Oklab) |
| 4 | Прозрачности, толщины, размеры, шрифт | **P1** | scalar-lerp |
| 5 | Тип штриха, форма точки, linecap, anchor, tick_count, angle_range | **P1** | discrete snap |
| 6 | Подписи: label_visible / label_text / label_mode | **P2** | discrete + swap |
| 7 | Акценты: indicate/flash/circumscribe/passing_flash | отложено — последняя фаза | events |
| 8 | z_index (порядок наложения) | P2 | discrete + явный set_z_index |
| 9 | Reveal construction (стаггер по зависимостям) | **P2** (дёшево, ценно) | макро-генератор кейфреймов |
| 10 | Камера: центр/зум | P3 | `@camera` |
| 11 | Crossfade/morph текста подписей, per-key easing | P3 | later |
| 12 | Динамические цвета/условная видимость как выражения (GGB Dynamic Colors) | вне scope | отдельная тема (live-выражения, не таймлайн) |

## 7. План реализации (фазы)

1. **Стилевые треки (ядро).** Реестр ключей; парсинг `styles` в v2; Style-
   интерполяторы (scalar/color/discrete/offset2); снятие базовых значений через
   resolver; `null`-revert; интервалы-только-стили через updater; Oklab-lerp.
   Тайминг не трогаем. Тесты: parse/validate, carry-forward, снап-правило,
   revert, snapshot-совместимость v1.
2. **Видимость v2 (тайминг + эффекты).** `visible`-карты; точная длительность
   (без вставных 0.4 с); адаптеры `fade`/`none`; затем `create`/`grow`/
   `uncreate`/`shrink`; гейтинг «эффект умножает поверх трека»; `elem.visible` +
   add/remove в нужных точках. v1-путь сохраняется byte-identical.
3. **Подписи + reveal.** `label_text` swap; style-aware pre-pass label
   placement; `write` для текстов. Плюс `reveal_construction` (дёшев после
   фазы 2).
4. **Ядро веб-контракта.** `get_element_states()`; расширение easing-набора
   ядра до веб-перечня. Сама веб-интеграция (конвертер
   `_convert_timeline_to_animageo`, версия timeline, TS-типы, инспектор,
   endpoint) решается **на стороне animageo_web** и в scope этого проекта не
   входит — §5.6 остаётся справочным контрактом для той работы.
5. **Камера + расширения.** `@camera` — сознательно после веб-контракта:
   из-за pixel-invariant sizing анимация камеры = по-кадровый пересчёт
   `ptUnit`/viewport и rebuild всей сцены (семантика GGB `ZoomIn`, а не сдвиг
   manim-кадра — иначе поплывут пиксельные размеры точек/шрифтов/толщин);
   отдельный перф-риск, ортогонален трекам — можно вытянуть вперёд или делать
   параллельно, но не блокировать им доставку стилей/видимости в веб. Далее:
   crossfade текста; per-key easing; `apply_keyframes_at` превью.
6. **События (`events`) — в самом конце, после всех остальных фаз.** Решение
   ревью: перед реализацией — отдельная пауза на анализ взаимодействий
   (адаптеры поверх become × эффекты входа/выхода × label tracker — не ломает
   ли что-то ещё). События — **не часть интерполируемого состояния**
   (одноразовые, самовосстанавливающиеся), поэтому тестируются отдельным
   контрактом: ключевой инвариант — «кадр после завершения события
   byte-identical кадру той же анимации без события» (покадровое сравнение),
   юнит-тесты адаптеров (alpha=0 и alpha=1 → identity), запрет записи в
   `elem.style` из адаптеров.

## 8. Риски и открытые вопросы

**Риски:**

- `become()` не переносит z_index — при анимации z нужен явный путь; проверить
  на manim 0.20/0.21.
- Производительность: per-frame `CreateMObject` для стилевых элементов — та же
  цена, что сегодня у геометрии (become-путь); LaTeX кэшируется по тексту;
  замерить плотные сцены (бенчмарк из label placement уже есть, ~28 мс/кадр).
- Fade-адаптер должен корректно умножать прозрачности всего семейства
  (Tex/ValueLabel-группы, полигоны с раздельными fill/stroke sub-mobjects).
- Pre-pass label placement подорожает ×(стили на кейфреймах) — приемлемо, но
  проверить.

**Решения ревью (2026-07-05):**

1. **Дефолтный entrance — `fade`** для всех типов; per-type идиоматика
   (create/write) — опционально через `defaults.enter_by_type`, не дефолт.
2. **Цветовое пространство — Oklab** по умолчанию;
   `rendering.color_interpolation: "srgb"` как escape hatch.
3. **Легаси-тайминг v1 депрекейтим**: без `version: 2` играется byte-identical,
   но с DeprecationWarning; удаление через 1–2 минорных релиза после миграции
   веб-конвертера (фаза 4).
4. **`events` — отложены в самый конец** (после фаз 1–5; уточнение ревью):
   это отдельная сущность (одноразовые эффекты, не состояние), перед
   реализацией нужна пауза и анализ, не ломает ли она остальное; тестовый
   контракт и инвариант самовосстановления — §7 п.6.
5. **Камера — фаза 5** (решение за исполнителем, принято): после ядра
   веб-контракта; ортогональна — можно тянуть параллельно (обоснование в §7
   п.5).
6. **Веб-UI — вне scope, решается на стороне animageo_web** (уточнение
   ревью). Ядро предоставляет только контракт: схему v2,
   `get_element_states()`, расширенный easing-набор. §5.6 — справочные
   рекомендации для будущей работы в animageo_web (в т.ч. предложение
   авторить стили в таймлайн-инспекторе, а не захватывать с апплета).

**Технические открытые пункты (решаются в ходе реализации, не блокируют):**

- Зафиксировать перечень 17 easing веба и добавить недостающие функции в ядро
  (фаза 4, выравнивание конвертера).

---

## Приложение A. Отчёт по prior art (полный)

### A.1 Таксономия анимируемых свойств

| Категория | Семантика интерполяции | Источник |
|---|---|---|
| Continuous numeric | lerp покомпонентно; углы — циклически/кратчайшей дугой | [MDN Animatable properties](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_animated_properties) |
| Color | lerp в выбранном пространстве; CSS Color 4 default — **Oklab** (нет серой мёртвой зоны, нет ухода blue→purple); OKLCH — когда важен контроль дуги hue | [MDN color-interpolation-method](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color-interpolation-method), [Evil Martians OKLCH](https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl) |
| Discrete/enum | снап start→end на eased-progress ≥ 0.5 (норматив CSS; SMIL `calcMode="discrete"`) | [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_animated_properties), [CSS-Tricks SMIL](https://css-tricks.com/guide-svg-animations-smil/) |
| Text | не интерполируется: (1) swap, (2) matched morph (manim `TransformMatchingTex`, Keynote by-word), (3) per-glyph reveal (`Write`) | [Manim animations](https://docs.manim.community/en/stable/reference_index/animations.html) |
| Visibility | событие+эффект, не свойство; CSS: `@starting-style` + `transition-behavior: allow-discrete` | [Chrome entry/exit](https://developer.chrome.com/blog/entry-exit-animations/) |
| Progress/trim | 0..1 «сколько пути нарисовано» — Lottie Trim Paths, SVG dashoffset, manim `Create` | [LottieFiles Trim Path](https://lottiefiles.com/tutorials/lottie-creator/use-trim-path-to-create-stunning-curve-animations-QEeHUuBGBhG) |
| Camera | обычный объект с числовыми свойствами (manim `camera.frame`) | Manim MovingCameraScene |

### A.2 Три модели авторинга

- **WAAPI/CSS** — список кейфреймов, значения по свойствам, `easing` на
  сегменте (объявлен на стартовом кейфрейме); недостающие значения
  синтезируются из статического стиля; внутренняя нормализация — per-property
  ([MDN Keyframe Formats](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API/Keyframe_Formats)).
- **GSAP/anime.js/Lottie/AE** — каждый property — свой трек со своим таймингом
  и per-keyframe безье-тангентами; timeline = контейнер твинов с наследуемыми
  `defaults`; stagger — первоклассный примитив
  ([GSAP Timeline](https://gsap.com/docs/v3/GSAP/Timeline/),
  [Lottie spec](https://lottie.github.io/lottie-spec/1.0/specs/properties/)).
- **Morph/Magic Move/Framer variants** — два полных состояния, переход
  выводится; несматченные объекты — auto fade-in/out; текст матчится по
  object/word/character
  ([Microsoft Morph](https://support.microsoft.com/en-us/office/use-the-morph-transition-in-powerpoint-8dd1c7b2-b935-44f5-a74c-741d8d9244ea),
  [Keynote Magic Move](https://keynote.skydocu.com/en/animate-your-slides/add-a-magic-move-transition/)).

### A.3 Таксономия эффектов (геометрически-идиоматичное — manim)

- Entrance: `Create`, `Write`/`AddTextLetterByLetter`, `DrawBorderThenFill`,
  `FadeIn`(±shift/scale), `GrowFromCenter/Point/Edge`, `GrowArrow`,
  `SpinInFromNothing`, `ShowIncreasingSubsets`.
- Exit: `Uncreate`, `Unwrite`, `FadeOut`(±shift), `ShrinkToCenter`.
- Emphasis (самовосстанавливающиеся): `Indicate`, `Flash`, `Circumscribe`,
  `FocusOn`, `Wiggle`, `ApplyWave`, `ShowPassingFlash`
  ([indication module](https://docs.manim.community/en/stable/reference/manim.animation.indication.html)).
- Композиция: `AnimationGroup` / `Succession` / `LaggedStart(lag_ratio)`.
- Transform-семейство: `Transform` vs `ReplacementTransform` (чистая передача
  идентичности), `TransformMatchingShapes/Tex`, `FadeTransform`.

### A.4 GeoGebra

Slider-анимация (speed, Oscillating/Increasing/Decreasing), Dynamic Colors
(R/G/B/opacity как live-выражения), Condition to Show Object, скриптовые
`SetColor/SetDynamicColor/SetVisibleInView/SetLineThickness/SetLineStyle/
SetLineOpacity/SetPointSize/SetPointStyle/SetCaption/SetValue/StartAnimation/
ZoomIn/ZoomOut`; Apps JS API зеркалит (`setVisible/setColor/setFilling/
setLineStyle/setLineThickness/setPointStyle/setPointSize/setLabelVisible/
setCaption/setValue/setCoordSystem`). Таймлайна нет — value-add animageo.
Construction Protocol + Navigation Bar — канонический progressive reveal
([Apps API](https://geogebra.github.io/docs/reference/en/GeoGebra_Apps_API/),
[Construction Protocol](https://geogebra.github.io/docs/manual/en/Construction_Protocol/)).

### A.5 Ловушки (полный список)

1. sRGB-lerp цветов — грязные середины; Oklab default (CSS Color 4).
2. Дискретный снап — контракт (0.5 eased), не ad-hoc; немонотонный easing
   может переключить дважды — документировать.
3. Easing-скоуп: один уровень (сегмент) + опц. per-property; не копировать
   GSAP-овскую трёхслойную композицию.
4. Появление mid-timeline требует «starting style»; entrance гейтит треки
   (иначе классический баг двойной анимации opacity).
5. Exit→re-enter: скрытые интервалы — hold, не gap.
6. Transform vs ReplacementTransform: идентичность construction-элемента
   должна переживать замену mobject.
7. Текст никогда не лерпится; числовой случай уже решён (`ValueLabel` ≈ manim
   `ChangeDecimalToValue`).
8. Стили × зависимая геометрия: label placement должен видеть
   *интерполированный* стиль (per-frame tracker уже есть).
9. Рассинхрон независимых треков читается как глюк — synchronized
   whole-keyframe default.
10. Прогрессивная отрисовка требует детерминированной параметризации пути
    (направление отрисовки per-type — задокументировать; сэмплеры уже дают).

### A.6 Ключевые источники

- MDN: [Animatable properties](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_animated_properties) · [WAAPI Keyframe Formats](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API/Keyframe_Formats) · [color-interpolation-method](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color-interpolation-method)
- [Chrome: entry/exit animations](https://developer.chrome.com/blog/entry-exit-animations/) · [Evil Martians: OKLCH](https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl)
- [GSAP Timeline](https://gsap.com/docs/v3/GSAP/Timeline/) · [GSAP keyframes](https://gsap.com/resources/keyframes/) · [anime.js keyframes](https://animejs.com/documentation/animation/keyframes/) · [Motion transitions](https://motion.dev/docs/react-transitions)
- Manim: [animations index](https://docs.manim.community/en/stable/reference_index/animations.html) · [indication](https://docs.manim.community/en/stable/reference/manim.animation.indication.html) · [rate_functions](https://docs.manim.community/en/stable/reference/manim.utils.rate_functions.html) · [LaggedStart](https://docs.manim.community/en/stable/reference/manim.animation.composition.LaggedStart.html)
- GeoGebra: [Animation](https://wiki.geogebra.org/en/Animation) · [Dynamic Colors](https://wiki.geogebra.org/en/Dynamic_Colors) · [Scripting Commands](https://geogebra.github.io/docs/manual/en/commands/Scripting_Commands/) · [Apps API](https://geogebra.github.io/docs/reference/en/GeoGebra_Apps_API/) · [Construction Protocol](https://geogebra.github.io/docs/manual/en/Construction_Protocol/)
- [Microsoft Morph](https://support.microsoft.com/en-us/office/use-the-morph-transition-in-powerpoint-8dd1c7b2-b935-44f5-a74c-741d8d9244ea) · [Keynote Magic Move](https://keynote.skydocu.com/en/animate-your-slides/add-a-magic-move-transition/) · [Lottie spec](https://lottie.github.io/lottie-spec/1.0/specs/properties/) · [CSS-Tricks SMIL](https://css-tricks.com/guide-svg-animations-smil/)
