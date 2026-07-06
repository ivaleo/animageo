# Спека: анимация tparam-точек на конике / локусе / функции

**Дата:** 2026-07-03
**ТЗ:** `docs/archive/TZ-conic-locus-point-keyframe-animation.md` (кадры «замерзают» для точек на конике/локусе/функции)
**Ground truth:** https://animageo.ru/shared/tYwHUgEyock (точка `D` на эллипсе `c`), `.ggb` через `GET /api/shared/tYwHUgEyock/ggb`

## 1. Цель

Точки, привязанные к конике (эллипс/гипербола/парабола/круг-как-коника), локусу и функции `y = f(x)`, должны анимироваться в `play_keyframes` так же полноценно, как точки на окружности/отрезке/прямой/луче. Веб-сервис должен получить единый библиотечный API «координаты → tparam», убирающий его частичный дубль-конвертер.

## 2. Согласованные решения

| Вопрос | Решение |
|---|---|
| Объём путей | Коника + локус + **функция** (функция — net-new: инверсия, forward `point_F`, ветка в парсере) |
| API-контракт | **Оба**: публичный `Construction.tparam_from_coords(name, coords)` **и** приём `[x, y]` как значения `tparam_point` в кадре (вариант A на ядре B) |
| Размещение математики | Новый модуль `animageo/geo/tparam.py`; `ggb_parser` реэкспортирует хелперы (back-compat) |
| Локус-инверсия | Апгрейд до сегментной проекции с дробным параметром (соответствие GeoGebra `GeoLocus.pointChanged`) |

## 3. Соответствие GeoGebra (аудит исходников GGB, 2026-07-03)

Проверено по `GeoConicND.java`, `GeoLocus.java`, `GeoFunction.java`, `PathNormalizer.java` (master) и ground-truth `hex.ggb`:

- **GGB не хранит path parameter в XML** — только `<coords>`; при загрузке параметр восстанавливается проекцией (`pointChanged`). Наш импорт (пересчёт tparam из coords) = родная практика GGB. Coords — корректный interchange-формат.
- Circle: `atan2` — совпадает (у нас нормировка [0,2π), у GGB (−π,π] — внутреннее дело).
- Ellipse: `(a·cos t, b·sin t)` в осях — совпадает точно на кривой. Вне кривой GGB делает перпендикулярную проекцию (квартика), у нас — «масштабированный угол»; разница второго порядка возле кривой. **Документированное ограничение, не меняем.**
- Hyperbola: `(a·cosh s, b·sinh s)` — совпадает; ветка у GGB кодируется диапазоном t∈(−1,1)∪(1,3), у нас tuple `(±1, s)` — внутреннее дело.
- Parabola: GGB `x = p·t²/2, y = p·t`; у нас t = смещение вдоль perp-оси (масштаб отличается в p раз) — внутреннее дело, наружу не протекает.
- Function: параметр = **x** — конвенция идентична GGB.
- Locus: GGB — `closestPointIndex + frac` (проекция на сегменты); у нас была ближайшая вершина → **апгрейдим** (см. §4.1). Шкала у нас [0,1] против [0,N−1] у GGB — внутреннее дело.
- **Вне рамок:** двухаргументный `Point(path, λ)` не поддержан (`point_ci` нет). Если добавлять — λ у GGB **нормализованный** [0,1] через `PathNormalizer`, не внутренний tparam.

## 4. Дизайн

### 4.1. Новый модуль `animageo/geo/tparam.py`

Перенос из `ggb_parser.py` (с реэкспортом оттуда для back-compat, включая использование в repro ТЗ):
`get_tparam_from_point_and_{circle,line,segment,conic,locus}`.

Новое:
- `get_tparam_from_point_and_function(point, function) -> float` — `x = point.coords[0]` (естественный параметр; точка вне графика проецируется по x).
- `get_tparam_from_point_and_locus` — **апгрейд**: проекция на ближайший сегмент ломаной, параметр `(i + frac) / (N − 1)` ∈ [0,1]. Forward `LocusCurve.point_at` уже лерпит между вершинами → round-trip становится симметричным (устраняет «прыжок на вершину» при импорте).
- `tparam_from_point_and_path(point, path) -> float | tuple | None` — единый isinstance-диспетчер (Circle, Segment, Ray, Line, Conic, LocusCurve, Function). Для гиперболы возвращает tuple `(branch, t)`.

### 4.2. Forward `point_F` в `lib_commands.py`

`point_F(function, tparam=None) -> Point | None`: `Point([x, f(x)])`; `None`, если `f(x)` не конечна (вне области определения) — по образцу `point_L`. Диспатч `Point(Function)` подхватывается автоматически по конвенции имён.

### 4.3. Парсер `ggb_parser.py`

В детект пути точки-на-пути (ветки `tparam_locus`, стр. ~509–519) добавить `Function` через новый диспетчер `tparam_from_point_and_path` (заменяет isinstance-цепочку целиком).

### 4.4. Классификация `construction.py::get_independents`

Расширить цикл constraint (стр. 472–483):
- `Conic` → `'circle' | 'ellipse' | 'hyperbola' | 'parabola'` по `conic.type` (деген. типы → `'unknown'`, как раньше);
- `LocusCurve` → `'locus'`; `Function` → `'function'`.

Объект пути в dict **не** кладём (JSON-сериализуемость сохраняется). Для гиперболы `'tparam'` в dict — tuple `(branch, t)` как есть (JSON: массив из двух чисел).

### 4.5. Публичный `Construction.tparam_from_coords(name, coords) -> float | tuple | None`

Находит команду точки (`commandByElementName`), первый вход-путь среди инпутов, зовёт диспетчер. `None` + warning, если точка не tparam_point или путь не распознан. Это API для веба (замена его конвертера) и внутренний механизм кадров `[x,y]`.

### 4.6. Интерполяция `keyframes.py`

- `_parse_value(name, raw_value, info, construction=None)`:
  - `tparam_point` принимает **и** `{"tparam": …, "direction": …}` (back-compat), **и** `[x, y]` → `construction.tparam_from_coords(name, [x,y])`; без `construction` при `[x,y]` — `ValueError` с понятным текстом;
  - выбор kind по constraint: `'circle' | 'ellipse'` → `tparam_circle` (циклический, wrap 2π, `direction` работает); `'hyperbola'` → `tparam_hyperbola`; остальное (`segment/ray/line/parabola/locus/function/unknown`) → `tparam_linear`.
- `Interpolator`: новый kind `tparam_hyperbola` — branch снапится (start branch до t=0.5, потом end branch; на практике смена ветки в интервале — документированный вырожденный случай), скалярная часть лерпится.
- `_build_intervals(keyframes, element_info, construction=None)`: прокинуть construction в оба вызова `_parse_value`; guard «значение не изменилось» (`np.isclose`, стр. ~426) — special-case для tuple-значений гиперболы.
- `apply_parsed_value`: kind `tparam_hyperbola` → `update_tparam` (tuple проходит в `point_K` как есть — уже поддержано).
- `KeyframeSequence.from_json`: передать construction в `_build_intervals`.

### 4.7. Snapshot-проходы `animageo.py`

- `_snapshot_independents` (стр. ~1231): убрать `float(info['tparam'])` — падает на tuple гиперболы; передавать как есть (tuple → `{"tparam": [branch, t]}`).
- Все три call-site `_parse_value` (~1253, ~1323, ~1352): передать `self.geo`.

## 5. Семантика интерполяции (итог)

| Путь | tparam | kind | wrap |
|---|---|---|---|
| circle, ellipse | угол ∈ [0,2π) | `tparam_circle` | 2π, кратчайшая дуга / `direction` |
| parabola | скаляр | `tparam_linear` | — |
| hyperbola | `(branch, t)` | `tparam_hyperbola` | branch снап, t лерп |
| line, ray, segment | скаляр | `tparam_linear` | — |
| function | x | `tparam_linear` | — |
| locus | `(i+frac)/(N−1)` ∈ [0,1] | `tparam_linear` | — (замкнутый локус — вне рамок) |

## 6. Критерии приёмки (из ТЗ §5 + аудит)

1. `get_independents()["D"]` для точки на эллипсе → `constraint='ellipse'`, валидный `tparam`.
2. `play_keyframes` на `hex.ggb` с кадрами `[x,y]` для `D` даёт движущееся видео: `D` едет по эллипсу, производная геометрия пересчитывается.
3. Регресс-тесты: эллипс и локус анимируются между двумя кадрами; для эллипса интерполяция циклическая (кратчайшая дуга, wrap через 2π).
4. Circle/line/segment/ray — без регрессий (существующие тесты зелёные).
5. `tparam_from_coords` покрыт тестами для всех типов пути.
6. Локус: точка на середине сегмента ломаной после импорта остаётся на месте (не прыгает на вершину).

## 7. Вне рамок

- Циклический wrap замкнутого локуса (линейная интерполяция).
- Смена ветки гиперболы внутри интервала (снап на середине; вырожденный переход документируем).
- Пересечение сингулярности функции внутри интервала (точка исчезает, где f(x) не определена).
- Двухаргументный `Point(path, λ)` (нормализованная семантика GGB — задокументирована в §3).
- Изменения на стороне animageo-web (отдельная задача: заменить конвертер на `tparam_from_coords` / `[x,y]`-кадры).
