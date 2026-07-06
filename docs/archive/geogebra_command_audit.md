# Аудит команд построения AnimaGeo относительно GeoGebra

Дата аудита: 2026-05-03.

Актуализация: 2026-05-04. После проверки 147 реальных `.ggb` из
`examples/` реализованы GeoGebra-compatible aliases, parser lowering для
inline-выражений, `Point(Ray)`, `Point(Arc)`, `Point(Locus)`, минимальный
численный `Locus(Point, Point)`, расширенные измерения, часть недостающих
`Intersect`, `Incircle`, `Rotate(Vector, Angle, Point)` и
`IsogonalConjugation(Point,Point,Point,Point)`. Текущий аудит
`examples/**/*.ggb`: 147/147 загружаются без исключений и без
`Construction.command_diagnostics`.

Актуализация: 2026-07-05. Реализован `Trilinear(A,B,C,x,y,z)` →
`trilinear_pppiii` (точка по трилинейным координатам относительно
треугольника). Затем закрыт весь Tier A и Tier B плана «лёгких» команд
(см. ниже): `Slope`, `Direction`, `UnitVector`, `PerpendicularVector`,
`UnitPerpendicularVector`, `Dot`, `Cross`, `AffineRatio`, `CrossRatio`,
`Midpoint(Conic)`, `Conic(6 Numbers)`, `Ray(Point,Vector)`,
`Point(Point,Vector)`, `ClosestPoint`, `Dilate`, `Polar(Line,Conic)`.

Этот файл сравнивает текущие команды построения AnimaGeo с публичной
документацией GeoGebra. Область аудита: 2D-геометрия, коники, функции,
неявные кривые, векторы и базовые преобразования, то есть то, что влияет на
импорт `.ggb` и Python/DSL-построения. CAS, статистика, таблицы, 3D-тела и
скриптовые команды GeoGebra здесь не считаются целевым функционалом, кроме
случаев, когда они пересекаются с 2D-построениями.

## Источники GeoGebra

- Geometry Commands: https://geogebra.github.io/docs/manual/en/commands/Geometry_Commands/
- Conic Commands: https://geogebra.github.io/docs/manual/en/commands/Conic_Commands/
- Intersect: https://geogebra.github.io/docs/manual/en/commands/Intersect/
- Point: https://geogebra.github.io/docs/manual/en/commands/Point/
- Line, Segment, Ray, Polygon, Circle:
  - https://geogebra.github.io/docs/manual/en/commands/Line/
  - https://geogebra.github.io/docs/manual/en/commands/Segment/
  - https://geogebra.github.io/docs/manual/en/commands/Ray/
  - https://geogebra.github.io/docs/manual/en/commands/Polygon/
  - https://geogebra.github.io/docs/manual/en/commands/Circle/
- Arc/Sector family:
  - https://geogebra.github.io/docs/manual/en/commands/Arc/
  - https://geogebra.github.io/docs/manual/en/commands/CircularArc/
  - https://geogebra.github.io/docs/manual/en/commands/CircumcircularArc/
  - https://geogebra.github.io/docs/manual/en/commands/CircularSector/
  - https://geogebra.github.io/docs/manual/en/commands/CircumcircularSector/
  - https://geogebra.github.io/docs/manual/en/commands/Semicircle/
- Conics:
  - https://geogebra.github.io/docs/manual/en/commands/Conic/
  - https://geogebra.github.io/docs/manual/en/commands/Ellipse/
  - https://geogebra.github.io/docs/manual/en/commands/Hyperbola/
  - https://geogebra.github.io/docs/manual/en/commands/Parabola/
  - https://geogebra.github.io/docs/manual/en/commands/Polar/
  - https://geogebra.github.io/docs/manual/en/commands/Tangent/
- Measurement / logic examples:
  - https://geogebra.github.io/docs/manual/en/commands/Angle/
  - https://geogebra.github.io/docs/manual/en/commands/Area/
  - https://geogebra.github.io/docs/manual/en/commands/Distance/
  - https://geogebra.github.io/docs/manual/en/commands/Midpoint/
  - https://geogebra.github.io/docs/manual/en/commands/PerpendicularLine/
  - https://geogebra.github.io/docs/manual/en/commands/PerpendicularBisector/
  - https://geogebra.github.io/docs/manual/en/commands/AngleBisector/
- Transformation / vector command categories:
  - https://geogebra.github.io/docs/manual/en/commands/Transformation_Commands/
  - https://geogebra.github.io/docs/manual/en/commands/Vector_and_Matrix_Commands/

## Как устроены команды в AnimaGeo

Файл реализации: `animageo/geo/lib_commands.py`.

Команды диспетчеризуются по шаблону:

```text
GeoGebraName + типы входов -> snake_case_name + "_" + type_shortcuts
```

Например:

```text
Intersect(Conic, Line, int) -> intersect_Kli
Line(Point, Vector) -> line_pv
```

Сокращения типов:

| Сокращение | Тип |
|---|---|
| `p` | `Point` |
| `l` | `Line` |
| `r` | `Ray` |
| `s` | `Segment` |
| `c` | `Circle` |
| `C` | `Arc` |
| `S` | `CircleSector` |
| `a` | `Angle` |
| `v` | `Vector` |
| `P` | `Polygon` |
| `K` | `Conic` |
| `F` | `Function` |
| `I` | `ImplicitCurve` |
| `i` | `int` / `float` |
| `m` | `Measure` |
| `A` | `AngleSize` |
| `b` | `Boolean` |
| `T` | `str` |
| `L` | `LocusCurve` |

Важное следствие: совпадение с GeoGebra требует не только алгоритма, но и
точного имени команды после CamelCase -> snake_case. Если алгоритм есть под
другим именем, импорт `.ggb` с публичным GeoGebra-именем может не сработать.

## Чек-лист реализации новой GeoGebra-команды

Пошаговый список мест, которые нужно затронуть при добавлении новой
команды. Составлен по факту реализации `Trilinear` (2026-07-05); ориентир
для последующих команд. Разбит на «реализация», «авто-подхватывается —
проверить», «вручную» и «особые случаи».

### 0. Перед началом: определить сигнатуру и имя

- Взять публичную сигнатуру из GeoGebra manual (см. «Источники» ниже).
- Прогнать имя через правило `strCommand` (CamelCase → snake_case): каждая
  заглавная буква (кроме первой) даёт `_` + lower. Пример:
  `IsogonalConjugation` → `isogonal_conjugation`, `Trilinear` → `trilinear`.
  Это же имя должно приходить из `<command name="...">` в `.ggb`, иначе
  импорт не сработает — при расхождении нужен алиас.
- Определить dispatch-суффикс из типов входов по таблице сокращений выше
  (`p`, `l`, `K`, `i`, `m`, ...). Итоговое dispatch-имя:
  `snake_case_<shortcuts>` (напр. `trilinear_pppiii`).
- Понять **тип результата**: существующий элемент (`Point`/`Line`/`Circle`/
  `Conic`/`Vector`/...), скаляр (`Measure`/`AngleSize`/`Boolean`), строка
  или список. От этого зависит объём работ (см. п. 4).

### 1. Реализация — `animageo/geo/lib_commands.py`

- [ ] Написать `def <name>_<shortcuts>(...)` рядом с родственными командами.
- [ ] Числовые аргументы, которые могут прийти как именованное число
      (слайдер → `Measure`/`AngleSize`), коэрсить через `.value`
      (см. `_trilinear_scalar`: `float(getattr(v, 'value', v))`).
- [ ] Возвращать корректный тип: элемент через его класс (`Point(coords)`,
      `Line(...)`), скаляр через `Measure(value, dimension)` /
      `AngleSize(rad)` / `Boolean(...)`. `dimension`: 0 — безразмерный,
      1 — длина, 2 — площадь.
- [ ] Вырожденный/неопределённый вход → `return None` (как `incircle_ppp`,
      `isogonal_conjugation_pppp`): деление на ноль, нулевая площадь,
      точка на бесконечности. Не кидать исключение.
- [ ] Если числовой слот может быть и `i`, и `m` — зарегистрировать все
      комбинации, делегируя одной реализации (см. цикл после
      `trilinear_pppiii`). Реестр `COMMAND_REGISTRY` строится из globals
      модуля автоматически; helper-функции называть с `_` в начале, чтобы
      они не попали в реестр.
- [ ] Убедиться, что суффикс состоит только из валидных сокращений —
      `_build_command_registry()` логирует на DEBUG нераспознанные суффиксы.

### 2. Авто-подхватывается — только проверить (правки обычно не нужны)

- [ ] **DSL-фабрика.** `parsers/dsl/namespace.py::_discover_command_names`
      сканирует `lib_commands` и создаёт CamelCase-фабрику автоматически.
      Проверка: `'NewName' in namespace._DISCOVERED_COMMANDS` и короткий
      `dsl.run(c, "X = NewName(...)")`.
- [ ] **`COMMAND_REGISTRY`.** Строится при импорте — новая функция там
      сразу. Проверка: `'new_name_ppp' in COMMAND_REGISTRY`.
- [ ] **Импорт `.ggb`.** `ggb_parser.py` кладёт любой `<command>` как
      `Command` и гонит через общий dispatch — при точном совпадении имени
      работает без правок. Проверить на реальном `.ggb`, если есть.

### 3. Вручную — документация, стабы, тесты

- [ ] `docs/archive/geogebra_command_audit.md` — сменить статус в таблице
      (`MISSING` → `OK`/`PARTIAL`), при необходимости строку в приложении
      «текущие dispatch-команды» и запись «Актуализация: ДАТА» в шапке.
- [ ] `docs/roadmap.md` — строка в списке реализованного.
- [ ] `CHANGELOG.md` — пункт в секции `## [Unreleased] → Added`.
- [ ] `animageo/parsers/dsl/namespace.pyi` — типизированный стаб
      `def NewName(...) -> ReturnType: ...` в блоке по типу результата
      (стаб ручной и неполный; добавлять для часто используемых команд).
- [ ] `animageo/AI_USAGE_PROMPT.md` — упомянуть, если команда полезна
      AI-агентам (таблица helpers). Гайд валидируется прогонами
      context-free агентов — правки минимальные и точные, при накоплении
      изменений его нужно перевалидировать.
- [ ] `tests/test_commands.py` — юнит-тесты прямого вызова (нормальный
      случай + инварианты + вырожденный → `None` + коэрсия `Measure`).
- [ ] `tests/test_dsl_run.py` — один round-trip через `dsl.run`, доказывающий
      авто-обнаружение и dispatch.

### 4. Особые случаи (больше работы)

- **Строковый результат** (`Type`, `Name`, `Text`) — нужен объект `Text`/
  строковое моделирование результата; просто вернуть `str` из команды
  недостаточно для рендера/экспорта.
- **Список на входе/выходе** (`Barycenter`, `InteriorAngles`, `Polygon(List)`,
  `Conic(List)`) — **заблокировано отсутствием first-class типа `List`**.
  До появления `List` такие команды не делать (или только вариадическую
  форму, если она осмысленна).
- **Новый тип-результат** (напр. параметрическая `Curve`, `Polyline`,
  `Region`) — это не «команда», а тип: потребуется `_render_<type>` в
  `animageo.py`, эмиттер в `exporters/tikz/emitters.py`, creator в
  `exporters/jsxgraph/command_map.py`, запись в `style_map`, при
  path-точках — ветка в `geo/tparam.py`. Отдельная крупная задача.
- **Возвращает существующий рисуемый тип** — рендер (SVG/MP4), TikZ и
  JSXGraph работают автоматически (они идут от типа элемента, а не от
  команды). Дополнительно ничего не нужно.
- **Точка на пути** (результат — `Point`, привязанный к кривой): для
  анимации нужен `tparam`. Проекция координат на путь уже есть —
  `geo/tparam.py::tparam_from_point_and_path` и
  `Construction.tparam_from_coords`.

### 5. Проверка

- [ ] `python3.13 -m pytest tests/test_commands.py tests/test_dsl_run.py
      tests/test_dsl_factories.py -q` (python3.13 — интерпретатор с manim).
- [ ] Полный прогон перед коммитом: `python3.13 -m pytest tests/ -q`.

## Типы элементов AnimaGeo

Реализованные геометрические типы:

- `Point`
- `Line`
- `Ray`
- `Segment`
- `Angle`
- `Polygon`
- `Circle`
- `Arc`
- `CircleSector`
- `Vector`
- `Conic`
- `Function`
- `ImplicitCurve`
- `LocusCurve` — численно sampled locus/polyline для `Locus(Point, Point)`
- скалярные значения: `Measure`, `AngleSize`, `Boolean`, `int`, `float`

GeoGebra-типы, которые в текущем ядре AnimaGeo явно отсутствуют:

- 3D: `Plane`, `Quadric`, `Sphere`, `Polyhedron`, 3D `Curve`.
- Списки как геометрический тип результата (`List` точек, списки
  коэффициентов, списки объектов) почти не моделируются.
- `Polyline`, `Region`, `Spline`, `Interval`, `Path` как отдельные типы.
- Полный символический `Locus`/`LocusEquation`; сейчас есть только sampled
  `LocusCurve`.
- Матрицы и расширенные vector/matrix объекты, кроме простого `Vector`.

## Полный список Geometry Commands GeoGebra и статус

Статусы:

- `OK` - команда и основная 2D-сигнатура реализованы под тем же именем.
- `PARTIAL` - часть сигнатур реализована, либо есть ограничения по типам.
- `NAME_MISMATCH` - алгоритм есть, но имя отличается от публичной команды
  GeoGebra.
- `MISSING` - целевой реализации нет.
- `OUT_OF_SCOPE` - в основном не 2D-построение для текущей модели AnimaGeo.

| GeoGebra command | Статус | AnimaGeo | Комментарий |
|---|---:|---|---|
| `AffineRatio` | OK | `affine_ratio_ppp` | λ: `C=A+λ(B−A)` для 3 коллинеарных точек. |
| `Angle` | PARTIAL | `angle_ppp`, `angle_size_ppp` | Есть угол по 3 точкам. Нет `Angle(Object)`, `Angle(Vector,Vector)`, `Angle(Line,Line)`, `Angle(Polygon)`, фиксированного угла `Point,Point,Angle`. |
| `AngleBisector` | PARTIAL | `angular_bisector_ll`, `angular_bisector_ppp`, `angular_bisector_ss` | Для двух прямых, двух сегментов, трех точек. |
| `Arc` | PARTIAL | `arc_cpp` | Только `Arc(Circle, Point, Point)`. Нет `Arc(Ellipse, ...)`, нет параметрических `Arc(Conic, t1, t2)`. |
| `Area` | PARTIAL | `area_P`, `area_K`, `area(*points)` | Площадь многоугольника, точек и circle/ellipse conic. |
| `AreCollinear` | OK | `are_collinear_ppp` | 3 точки. |
| `AreConcurrent` | PARTIAL | `are_concurrent_lll` | Только 3 прямые. Вспомогательная `are_concurrent()` для line/circle не зарегистрирована как dispatch-команда. |
| `AreConcyclic` | OK | `are_concyclic_pppp` | 4 точки. |
| `AreCongruent` | PARTIAL | `are_congruent_aa`, `are_congruent_ss` | Углы и сегменты. |
| `AreEqual` | PARTIAL | `are_equal_pp`, `are_equal_mm`, `are_equal_mi` | Также есть `equality_*` под другим именем. Нет общего покрытия всех GeoGebra-объектов. |
| `AreParallel` | PARTIAL | `are_parallel_ll`, `ls`, `sl`, `ss`, `rr` | Нет всех направлений с `Ray`/`Segment` симметрично, нет векторов. |
| `ArePerpendicular` | PARTIAL | `are_perpendicular_ll`, `lr`, `rl`, `ls`, `sl`, `ss` | Нет векторов и 3D. |
| `Barycenter` | MISSING | - | Нет весового барицентра. |
| `Centroid` | OK | `centroid_P` | Только `Polygon`. |
| `Circle` | PARTIAL | `circle_pi`, `pm`, `ps`, `pp`, `ppp` | Нет 3D/axis forms `Circle(Line,Point)`, `Circle(Point,Radius,Direction)`, `Circle(Point,Point,Direction)`. |
| `CircularArc` | OK | `circular_arc_ppp`, `circle_arc_ppp` | Public-name alias added. |
| `CircularSector` | OK | `circular_sector_ppp`, `circular_sector_ppA`, `circular_sector_ppi`, `circle_sector_*` | Public-name aliases added. |
| `CircumcircularArc` | OK | `circumcircular_arc_ppp`, `circumcircle_arc_ppp` | Public-name alias added. |
| `CircumcircularSector` | OK | `circumcircular_sector_ppp`, `circumcircle_sector_ppp` | Public-name alias added. |
| `Circumference` | MISSING | - | Нет длины окружности/эллипса как команды. |
| `ClosestPoint` | MISSING | - | Нет ближайшей точки. |
| `ClosestPointRegion` | MISSING | - | Нет регионов. |
| `ClosestPoint` | PARTIAL | `closest_point_lp/sp/rp/cp` | Ближайшая точка на line/segment/ray/circle. Нет conic/function/polygon. |
| `CrossRatio` | OK | `cross_ratio_pppp` | `AffineRatio(B,C,D)/AffineRatio(A,C,D)`. |
| `Cubic` | MISSING | - | Нет треугольной кубики. |
| `Difference` | MISSING | - | Нет булевой разности регионов. |
| `Dilate` | PARTIAL | `dilate_pi/pip`, `si/sip`, `ci/cip`, `Pi/Pip`, `li/lip` (+ `m`-фактор) | Гомотетия point/segment/circle/polygon/line от origin или центра. Нет conic/function/vector. |
| `Direction` | OK | `direction_l/s/r/v` | Направляющий вектор `(b,−a)` линии; для segment — длиной сегмента. |
| `Distance` | PARTIAL | `distance_pp`, `distance_pl/lp`, `distance_ps/sp`, `distance_pr/rp`, `distance_pc/cp`, `distance_pK/Kp`, `distance_ll` | Базовые 2D distances; conic distance пока только для circle-conic. |
| `Envelope` | MISSING | - | Нет команды. |
| `Incircle` | OK | `incircle_ppp` | Вписанная окружность треугольника. |
| `InteriorAngles` | MISSING | - | Нет команды. |
| `Intersect` | PARTIAL | см. отдельную матрицу ниже | Широкое покрытие 2D-кривых, но не все GeoGebra-сигнатуры. |
| `IntersectPath` | MISSING | - | Нет отдельной path-intersection команды. |
| `IsInRegion` | MISSING | - | Есть `contained_by_pc/pl`, но это не GeoGebra-имя и покрывает только точка-круг/точка-линия. |
| `IsTangent` | MISSING | - | Есть `touches_lc/cl/cc`, но GeoGebra-команда `IsTangent` не реализована. |
| `Length` | PARTIAL | `length_s`, `length_v`, `length_C`, `length_c` | Segment/vector/arc/circle. |
| `Line` | PARTIAL | `line_pp`, `line_pl`, `line_pv`, `line_pr`, `line_ps`, `line_s` | Основные 2D формы есть. `Line(Point,Ray/Segment)` работает как параллельная линия сверх GeoGebra. |
| `Locus` | PARTIAL | `locus_pp`, `LocusCurve` | Численный sampled locus для `Locus(Point, Point)`. |
| `LocusEquation` | MISSING | - | Нет символьного локуса. |
| `Midpoint` | PARTIAL | `midpoint_pp`, `midpoint_s` | Нет `Midpoint(Conic)` под этим именем; близкая команда `center_K`. |
| `PathParameter` | MISSING | - | `tparam` есть как внутреннее поле точки на пути, но команды нет. |
| `Perimeter` | PARTIAL | `perimeter_P` | Периметр многоугольника. |
| `PerpendicularBisector` | OK | `perpendicular_bisector_pp/s`, `line_bisector_pp/s` | Public-name aliases added. |
| `PerpendicularLine` | PARTIAL | `perpendicular_line_pl/pr/ps`, `orthogonal_line_pl/pr/ps` | Public-name aliases added. Нет `Point,Vector`, `Line,Line`, 3D context. |
| `Point` | PARTIAL | `point_`, `point_ii`, `point_c`, `point_l`, `point_r`, `point_s`, `point_C`, `point_S`, `point_L`, `point_K`, `point_pv` | Есть точки на circle/line/ray/segment/arc/sector/locus/conic и `Point(Point,Vector)`. Параметрические variants покрыты частично через `tparam`. |
| `PointIn` | MISSING | - | Нет точки внутри региона. |
| `Polygon` | PARTIAL | `polygon`, `polygon_ppi` | Есть по точкам и правильный многоугольник по двум точкам и числу. Нет `Polygon(List)`, нет direction form. |
| `Polyline` | MISSING | - | Нет типа polyline. |
| `Prove` | PARTIAL | `prove_b` | Просто возвращает boolean; не реализует GeoGebra symbolic prove полностью. |
| `ProveDetails` | MISSING | - | Нет. |
| `Radius` | PARTIAL | `radius_c`, `radius_K` | `Conic`-круг поддержан. |
| `RandomPointIn` | MISSING | - | Нет. |
| `Ray` | OK | `ray_pp`, `ray_pv` | Две точки и точка+вектор. |
| `RigidPolygon` | MISSING | - | Нет. |
| `Sector` | MISSING | - | GeoGebra `Sector(Conic,Point,Point)` / params не реализован. Есть `CircleSector*` под другим именем. |
| `Segment` | PARTIAL | `segment_pp`, `segment_pv` | Нет `Segment(Point,Length)` под GeoGebra-сигнатурой. |
| `Semicircle` | OK | `semicircle_pp` | 2 точки. |
| `Slope` | OK | `slope_l` | Наклон dy/dx прямой; вертикаль → undefined. |
| `Tangent` | PARTIAL | `tangent_pc/pci`, `tangent_pK/Kp`, `tangent_lK/Kl`, `tangent_pF/iF/mF`, `tangent_cc` | point-circle, point-conic, line-conic (параллельные), point/x-value-function (производная) и **circle-circle** (общие касательные). Нет point/implicit curve. |
| `TriangleCenter` | MISSING | - | Нет. |
| `TriangleCurve` | MISSING | - | Нет. |
| `Trilinear` | OK | `trilinear_pppiii` | Точка по трилинейным координатам `x:y:z` относительно треугольника (i/m-варианты слотов). |
| `Union` | MISSING | - | Нет регионов/объединения. |
| `Type` | MISSING | - | Нет GeoGebra `Type`. |
| `Vertex` | OK | `vertex_K` | Для коник. |

## Intersect: детальная матрица типов

GeoGebra описывает `Intersect(Object,Object)`, `Intersect(Object,Object,Index)`,
итерационный вариант с начальной точкой, интервальный вариант для двух функций
и параметрический вариант для кривых. В AnimaGeo реализован только
детерминированный 2D-dispatch по типам и, для ряда пар, индексный вариант.

| Пара типов | Без индекса | С индексом | Комментарий |
|---|---:|---:|---|
| `Line x Line` | OK | NO | `intersect_ll`; индексный вариант не нужен для одной точки. |
| `Line x Circle` / `Circle x Line` | OK | OK | `intersect_lc/cl`, `intersect_lci/cli`. |
| `Circle x Circle` | OK | OK | `intersect_cc`, `intersect_cci`. |
| `Circle x Ray` / `Ray x Circle` | OK | OK | Ограничивает точки лучом. |
| `Circle x Segment` / `Segment x Circle` | OK | OK | Ограничивает точки сегментом. |
| `Line x Ray` / `Ray x Line` | OK | NO | Одна точка с проверкой принадлежности лучу. |
| `Line x Segment` / `Segment x Line` | OK | NO | Одна точка с проверкой принадлежности сегменту. |
| `Ray x Ray` | OK | NO | Только пересечение опорных прямых, затем проверка обоих лучей. |
| `Ray x Segment` / `Segment x Ray` | OK | NO | Проверка принадлежности обоим объектам. |
| `Segment x Segment` | OK | NO | Проверка принадлежности обоим сегментам. |
| `Arc x Line` / `Line x Arc` | OK | OK | Фильтрует точки круга по дуге. |
| `Arc x Ray` / `Ray x Arc` | OK | OK | Фильтрует и по дуге, и по лучу. |
| `Arc x Segment` / `Segment x Arc` | OK | OK | Фильтрует и по дуге, и по сегменту. |
| `CircleSector x Line` / `Line x CircleSector` | OK | OK | Сектор превращается в дугу; пересечение с радиальными сторонами сектора не учитывается. |
| `Conic x Line` / `Line x Conic` | OK | OK | Квадратичная подстановка в матрицу коники. |
| `Conic x Conic` | OK | OK | Pencil method, до 4 точек. |
| `Conic x Circle` / `Circle x Conic` | OK | OK | Circle поднимается в conic matrix. |
| `Conic x Ray` / `Ray x Conic` | OK | OK | Conic-line + фильтр луча. |
| `Conic x Segment` / `Segment x Conic` | OK | OK | Conic-line + фильтр сегмента. |
| `Function x Line` / `Line x Function` | OK | OK | Символьная попытка + численный fallback. |
| `Function x Conic` / `Conic x Function` | OK | OK | 1D root finding. |
| `Function x Circle` / `Circle x Function` | OK | OK | Через circle-as-conic. |
| `Function x Function` | OK | OK | Корни `f1(x)-f2(x)`. |
| `ImplicitCurve x Line` / `Line x ImplicitCurve` | OK | OK | Подстановка параметра прямой. |
| `ImplicitCurve x Segment` / `Segment x ImplicitCurve` | OK | OK | Line-intersection + фильтр сегмента. |
| `ImplicitCurve x Ray` / `Ray x ImplicitCurve` | OK | OK | Line-intersection + фильтр луча. |
| `ImplicitCurve x Conic` / `Conic x ImplicitCurve` | OK | OK | Marching squares + численное уточнение. |
| `ImplicitCurve x Circle` / `Circle x ImplicitCurve` | OK | OK | Через circle-as-conic. |
| `ImplicitCurve x Function` / `Function x ImplicitCurve` | OK | OK | Две zero-level функции. |
| `ImplicitCurve x ImplicitCurve` | OK | OK | Две zero-level функции. |
| `Function x Segment/Ray` | OK | OK | `intersect_Fs/sF/Fsi/sFi`, `intersect_Fr/rF/Fri/rFi`. |
| `Arc x Circle`, `Arc x Arc`, `Arc x Conic` | OK | OK | `intersect_Cc/cC`, `intersect_CC`, `intersect_CK/KC` plus indexed variants. |
| `Polygon/Region` intersections | MISSING | MISSING | Нет polygon/path/region semantics. |
| `Curve x Curve` parametric | MISSING | MISSING | Нет типа параметрической `Curve`. |
| `Intersect(Object,Object,Initial Point)` | MISSING | MISSING | Нет итерационного варианта с начальной точкой. |
| `Intersect(Function,Function,start,end)` | MISSING | MISSING | Нет 4-аргументного интервального варианта. |

## Conic Commands GeoGebra и статус

| GeoGebra command | Статус | AnimaGeo | Комментарий |
|---|---:|---|---|
| `Axes(Conic)` | OK | `axes_K` | Возвращает major/minor axes; для параболы одну ось. |
| `Center(Conic)` | OK | `center_K` | Для параболы возвращает vertex по текущему комментарию кода; для GeoGebra это может отличаться от строгого "center". |
| `Center(Circle)` | OK | `center_c` | Отдельный `Circle`. |
| `Circle` | PARTIAL | см. Geometry table | 2D-сигнатуры частично. |
| `Circumference` | PARTIAL | `circumference_c`, `circumference_K` | Circle and ellipse approximation. |
| `Coefficients(Conic)` | OK | `coefficients_K` | Возвращает `[A,B,C,D,E,F]`. |
| `Conic(5 Points)` | OK | `conic_ppppp` | Через SVD. |
| `Conic(6 Numbers)` | OK | `conic_iiiiii` | Порядок GeoGebra: `a x² + d xy + b y² + e x + f y + c = 0`. |
| `Conic(List)` | MISSING | - | Нет list type. |
| `Conic("equation")` | EXTRA | `conic_T` | DSL-удобство AnimaGeo, не буквальная GeoGebra-сигнатура. |
| `ConjugateDiameter` | MISSING | - | Нет. |
| `Curvature` | MISSING | - | Нет. |
| `Directrix(Conic)` | OK | `directrix_K` | 1 line для параболы, 2 для ellipse/hyperbola. |
| `Eccentricity(Conic)` | OK | `eccentricity_K` | Circle/ellipse/hyperbola/parabola. |
| `Ellipse(Focus,Focus,Number/Segment/Point)` | OK | `ellipse_ppi`, `ellipse_ppm`, `ellipse_ppp` | Реализованы три формы. |
| `Focus(Conic)` | OK | `focus_K` | Возвращает 1 или 2 точки; circle -> center. |
| `Hyperbola(Focus,Focus,Number/Segment/Point)` | OK | `hyperbola_ppi`, `hyperbola_ppm`, `hyperbola_ppp` | Реализованы три формы. |
| `Incircle` | OK | `incircle_ppp` | Есть. |
| `LinearEccentricity(Conic)` | OK | `linear_eccentricity_K` | Circle/ellipse/hyperbola. |
| `MajorAxis(Conic)` | OK | `major_axis_K` | Для ellipse/hyperbola. |
| `Midpoint(Conic)` | OK | `midpoint_K` (alias `center_K`) | Публичное GeoGebra-имя добавлено как алиас центра коники. |
| `MinorAxis(Conic)` | OK | `minor_axis_K` | Для ellipse/hyperbola. |
| `OsculatingCircle` | MISSING | - | Нет. |
| `Parabola(Point,Line)` | OK | `parabola_pl` | Также есть `parabola_ps`, `parabola_pr` как расширение. |
| `Parameter` | MISSING | - | Нет. |
| `PathParameter` | MISSING | - | Только внутренний `Element.tparam`. |
| `Perimeter` | PARTIAL | `perimeter_P` | Polygon perimeter. |
| `Polar(Point,Conic)` | OK | `polar_pK`, `polar_Kp` | Есть point-conic. |
| `Polar(Line,Conic)` | OK | `polar_lK`, `polar_Kl` | Полюс прямой: `M⁻¹·ℓ`. |
| `Radius(Conic)` | PARTIAL | `radius_c`, `radius_K` | `Conic`-круг поддержан. |
| `Sector(Conic,...)` | MISSING | - | Нет GeoGebra `Sector`. |
| `SemiMajorAxisLength(Conic)` | OK | `semi_major_axis_length_K` | Circle/ellipse/hyperbola. |
| `SemiMinorAxisLength(Conic)` | OK | `semi_minor_axis_length_K` | Circle/ellipse/hyperbola. |
| `Semicircle(Point,Point)` | OK | `semicircle_pp` | Есть. |
| `Tangent(Point,Conic)` | OK | `tangent_pK`, `tangent_Kp` | Есть point-conic. |
| `Tangent(Line,Conic)` | OK | `tangent_lK`, `tangent_Kl` | Касательные к конике, параллельные прямой (дуальная коника `ℓᵀ·adj(M)·ℓ=0`). |
| `Tangent(Circle,Circle)` | OK | `tangent_cc` | Общие касательные (до 4: внешние через внешний центр гомотетии, внутренние через внутренний). |
| `Type(Conic)` | MISSING | - | `Conic.type` есть как поле, но команды нет. |
| `Vertex(Conic)` | OK | `vertex_K` | Ellipse 4, hyperbola 2, parabola 1. |

## Function / ImplicitCurve

GeoGebra имеет большой раздел Functions and Calculus Commands. В AnimaGeo
цель уже: отрисовка и пересечения функций/неявных кривых, а не CAS.

Реализовано:

- `Function("expression")` через `function_T`.
- `ImplicitCurve("equation")` через `implicit_curve_T`.
- Парсер `.ggb` читает `expression type="function"` в `Function.from_string`.
- Парсер `.ggb` читает `expression type="implicitpoly"` в `ImplicitCurve.from_string`.
- Пересечения:
  - `Function` с `Line`, `Conic`, `Circle`, `Function`.
  - `ImplicitCurve` с `Line`, `Segment`, `Ray`, `Conic`, `Circle`, `Function`, `ImplicitCurve`.
- `Tangent(Point, Function)` / `Tangent(x-value, Function)` → `tangent_pF` /
  `tangent_iF` / `tangent_mF`: касательная в точке `x₀` через производную
  (sympy `diff` + lambdify).

Не реализовано относительно GeoGebra:

- `Function(List)`.
- `Function(Function,start,end)` как отдельная команда с ограничением домена.
- `Curve(...)` как параметрическая кривая.
- `Root`, `Roots`, `Extremum`, `Derivative`, `Integral`, `Asymptote`,
  `Polynomial`, `Spline`, `Curvature`, `OsculatingCircle` и остальная CAS /
  calculus группа.
- Итерационные варианты `Intersect` для кривых с initial point/parameters.

## Transformation Commands

GeoGebra public names: `Reflect`, `Rotate`, `Translate`, `Dilate`, `Shear`,
`Stretch`.

| GeoGebra command | Статус | AnimaGeo | Комментарий |
|---|---:|---|---|
| `Reflect` | PARTIAL | `reflect_*`, `mirror_*` | Public-name aliases added. Покрыты point/line/circle by point/line/circle/segment частично. |
| `Rotate` | PARTIAL | `rotate_pap`, `rotate_pAp`, `rotate_pip`, `rotate_vAp`, `rotate_vap`, `rotate_lAp` | Point/vector/line вокруг point. Нет segment/circle/polygon/conic/function. |
| `Translate` | PARTIAL | `translate_pv`, `translate_sv`, `translate_cv` | Point, Segment, Circle by Vector. Нет line/vector/polygon/conic/function. |
| `Dilate` | PARTIAL | `dilate_pi/pip`, `si/sip`, `ci/cip`, `Pi/Pip`, `li/lip` (+ `m`-фактор) | Гомотетия point/segment/circle/polygon/line. Нет conic/function/vector. |
| `Shear` | MISSING | - | Нет. |
| `Stretch` | MISSING | - | Нет. |

## Vector / Matrix Commands

Реализовано в ядре:

- `Vector(Point,Point)` -> `vector_pp`.
- `Vector(Point)` -> `vector_p`.
- `Vector(Number,Number)` -> `vector_ii`.
- `Vector(Vector,Number)` -> `vector_vi` как масштабирование до модуля.
- Арифметика векторов/точек: `Add`, `Sub`, `Mult`, `Div`, `USub`.

Добавлено (2026-07): `Direction(Line/Segment/Ray/Vector)` → `direction_*`,
`UnitVector(...)` → `unit_vector_*`, `PerpendicularVector(...)` →
`perpendicular_vector_*`, `UnitPerpendicularVector(...)` →
`unit_perpendicular_vector_*`, `Dot(Vector,Vector)` → `dot_vv`,
`Cross(Vector,Vector)` → `cross_vv` (2D-скаляр).

GeoGebra-команды из Vector and Matrix Commands, которых нет:

- `ApplyMatrix`, matrix commands (`Determinant`, `Transpose`, `Invert`,
  `SVD`, etc.).

## Parser `.ggb`: что реально импортируется

Файл: `animageo/parsers/ggb_parser.py`.

Поддержано:

- Распаковка `.ggb` и чтение `geogebra.xml`.
- `element type="point"` -> `Point`.
- `element type="numeric"` -> `Var(float)`.
- `element type="angle"` -> `Var(AngleSize)`.
- `element type="conic"` -> `Conic.from_ggb_matrix`.
- `element type="line"` -> `Line` из `coords`.
- `expression type="function"` -> `Function.from_string`.
- `expression type="implicitpoly"` -> `ImplicitCurve.from_string`.
- Любой `<command name="...">` добавляется как `Command` и затем проходит
  общий dispatch.
- Для `Point(Object)` из `.ggb` сохраняется `tparam` для `Circle`, `Line`,
  `Ray`, `Segment`, `Arc`, `LocusCurve`, `Conic`, если точку удалось связать
  с locus/path.
- Inline-входы GeoGebra (`Line[A,B]`, `Distance[A,B]`, `(0,0)`,
  `Vector[(t,0)]`, выражения с градусами) проходят через exec DSL lowering.
- Диагностика unsupported-команд сохраняется в `Construction.command_diagnostics`.

Ограничения:

- Для неизвестных расхождений manual/XML все еще нужны aliases.
- `Point(Object,Parameter)` покрыт не для всех типов через отдельные
  `point_*i` / `point_*m` dispatch-варианты.
- Списки, регионы, polyline, parametric curve и 3D-типы не имеют отдельной
  модели. `Locus` есть только как sampled `LocusCurve`.

## Главные разрывы относительно ориентира GeoGebra

После актуализации 2026-05-04 закрыты: public-name aliases для
`Circular*`/`Circumcircular*`/`Perpendicular*`/`Reflect`, parser lowering
inline GeoGebra expressions, `Point(Ray)`, `Point(Arc)`, `Point(Locus)`,
sampled `Locus(Point,Point)`, базовые `Length`/`Perimeter`/`Circumference`/
`Radius(Conic)`/`Area(Conic)`, small `Intersect` gaps для Function-Rays/
Segments и Arc-Circle/Arc/Conic, `Incircle`, `Rotate(Vector,Angle,Point)`,
`IsogonalConjugation`.

Оставшиеся существенные разрывы:

1. Имена команд, которые стоит привести к публичным GeoGebra-именам или
   добавить как алиасы: базовые aliases закрыты; новые нужно добавлять по
   мере появления XML/manual расхождений.

2. Самые заметные недостающие построения:
   - `PathParameter` как публичная команда.
   - Символьный `LocusEquation` и точный `Locus`; текущий `Locus` численный.
   - `ClosestPoint`, расширенный `Distance(Point,Object)`.
   - `Length`, `Perimeter`, `Circumference`.
   - `Tangent(Line,Conic)`, `Tangent(Circle,Circle)`,
     `Tangent(Point,Function)`, `Tangent(Point,ImplicitCurve)`.
   - `Polar(Line,Conic)`.
   - `Point(Object,Parameter)` полным набором типов, `Point(Point,Vector)`.
   - `Segment(Point,Length)`, `Ray(Point,Vector)`.
   - `Midpoint(Conic)` under GeoGebra names.

3. Типы, которые блокируют большой пласт GeoGebra:
   - `List` as first-class output/input.
   - `Polyline`.
   - `Region`.
   - `Locus`.
   - `Parametric Curve`.
   - 3D `Plane`/`Quadric`.

4. `Intersect` покрыт лучше остальных сложных команд, но все еще неполон:
   - нет parametric `Curve`;
   - нет iterative initial point / parameter variants;
   - нет function interval variant;
   - нет polygon/path/region semantics.

## Рекомендуемый порядок доработки

1. GeoGebra-compatible aliases без изменения алгоритмов — выполнено для:
   `CircularArc`, `CircularSector`, `CircumcircularArc`,
   `CircumcircularSector`, `PerpendicularBisector`, `PerpendicularLine`,
   `Reflect`.

2. Закрыть оставшиеся маленькие 2D-сигнатуры, которые дадут выигрыш при импорте:
   `point_r`, `point_ci/li/si/ri/Ki`, `point_pv`, `ray_pv`,
   `segment_pi/pm`, `midpoint_K`, `radius_K`, `area_K`, `length_s`,
   `distance_pl/ps/pc/pK/pF/pI`.

3. Расширить conic tools:
   `polar_lK`, `tangent_lK`, `tangent_cc`, `incircle_ppp`,
   `circumference_K`, `perimeter_P`.

4. Тяжелые типы:
   `Locus`, `Polyline`, `Curve`, `List`, `Region`.

5. После этого расширять `Intersect` на новые типы и варианты с начальной
   точкой/параметрами.

## Повторный аудит 2026-07-05 и план «лёгких» команд

Сверка таблиц выше с живым реестром (`list_commands()`): 377 dispatch-имён,
88 различных команд-баз.

### Расхождения в этом документе (staleness — учитывать при чтении)

- `Circumference` в Geometry-таблице помечена `MISSING`, но фактически
  реализована (`circumference_c`, `circumference_K`) — см. Conic-таблицу.
  Реальный статус: `PARTIAL` (окружность + аппроксимация эллипса).
- Приложение «текущие dispatch-команды» датировано 2026-05 и НЕ отражает:
  `incircle_ppp`, `isogonal_conjugation_pppp`, `trilinear_ppp*`,
  `circumference_*`, `perimeter_P`, `length_v/c/C`, весь набор `distance_*`,
  `semi_*_axis_length_K`, indexed `intersect_*` и др. Считать приложение
  ориентировочным; источник истины — `list_commands()`.

### Подтверждённо отсутствуют (проверено по реестру)

`slope`, `direction`, `unit_vector`, `perpendicular_vector`,
`unit_perpendicular_vector`, `dot`, `cross`, `affine_ratio`, `cross_ratio`,
`closest_point`, `dilate`, `stretch`, `shear`, `barycenter`, `type`,
`conic_iiiiii`, `midpoint_K`, `ray_pv`, `point_pv`, `segment_pi/pm`,
`polar_lK`, `tangent_lK`, `tangent_cc`, `tangent_pF`, `triangle_center`,
`triangle_curve`.

### План: очередь «лёгких» команд

Критерий «лёгкой»: результат — существующий тип (`Point`/`Line`/`Vector`/
`Measure`/`Conic`), алгоритм на существующей математике, без новых типов и
без списков. Каждая ≈ 5–20 строк + тесты. Порядок — по возрастанию усилий.

> **Статус 2026-07-05: Tier A и Tier B РЕАЛИЗОВАНЫ** (см. `lib_commands.py`,
> блок «Tier A / Tier B GeoGebra commands», и тесты
> `tests/test_commands.py::TestVectorScalarCommands` /
> `::TestClosestPointDilatePolar`). Таблицы ниже оставлены как справка по
> сигнатурам; следующая цель — Tier C.

**Tier A — тривиальные (скаляр/вектор/точка, чистая формула). — ГОТОВО**

| # | Команда | Dispatch | Результат | Суть |
|--:|---|---|---|---|
| A1 | `Slope(Line)` | `slope_l` | `Measure(0)` | `dir[1]/dir[0]`; вертикаль → `None` |
| A2 | `Direction(Line/Segment/Ray/Vector)` | `direction_l/s/r/v` | `Vector` | направляющий вектор |
| A3 | `UnitVector(Vector/Line/Segment/Ray)` | `unit_vector_v/l/s/r` | `Vector` | `dir/‖dir‖` |
| A4 | `PerpendicularVector(...)` | `perpendicular_vector_l/s/v` | `Vector` | `(−dy, dx)` |
| A5 | `UnitPerpendicularVector(...)` | `unit_perpendicular_vector_*` | `Vector` | нормированный перпендикуляр |
| A6 | `Dot(Vector,Vector)`, `Cross(Vector,Vector)` | `dot_vv`, `cross_vv` | `Measure(0)` | `v1·v2`, 2D-скаляр `v1×v2` |
| A7 | `AffineRatio(A,B,C)` | `affine_ratio_ppp` | `Measure(0)` | λ: `C=A+λ(B−A)` |
| A8 | `CrossRatio(A,B,C,D)` | `cross_ratio_pppp` | `Measure(0)` | `(AC/BC)/(AD/BD)` со знаком |
| A9 | `Midpoint(Conic)` | `midpoint_K` = alias `center_K` | `Point` | закрывает `NAME_MISMATCH` |
| A10 | `Conic(6 Numbers)` | `conic_iiiiii` | `Conic` | уже есть `Conic.from_coeffs` |
| A11 | `Ray(Point,Vector)`, `Point(Point,Vector)` | `ray_pv`, `point_pv` | `Ray`/`Point` | `p.coords + v.direction` |

**Tier B — лёгкие-средние (используют готовую математику ядра). — ГОТОВО**

| # | Команда | Dispatch | Результат | Суть |
|--:|---|---|---|---|
| B1 | `ClosestPoint(Path, Point)` | `closest_point_lp/sp/rp/cp/Kp` | `Point` | проекция через `tparam.tparam_from_point_and_path`, затем точка на пути |
| B2 | `Dilate(Object, r [, center])` | `dilate_pip`/`dilate_pii` (+ l/s/c/P/K) | тип входа | гомотетия `center + r·(X−center)`; для точки тривиально |
| B3 | `Polar(Line, Conic)` | `polar_lK` | `Point` (полюс) | `pole = M⁻¹·lineCoeffs`, нормировать; закрывает Conic-`MISSING` |

**Tier C — отложить (нужны БД/списки/строки/бо́льший объём).**

- `TriangleCenter(A,B,C,n)` — база Кимберлинга X(n); несколько центров легко,
  полная БД — много. Можно начать с частичной таблицы популярных `n`.
- `Tangent(Line,Conic)` (параллельные касательные), `Tangent(Circle,Circle)`
  (общие касательные), `Tangent(Point,Function)` (через производную) — средне.
- `Stretch`, `Shear` — аффинные преобразования, средне.
- `Barycenter`, `InteriorAngles`, `Polygon(List)`, `Conic(List)` —
  **заблокировано отсутствием типа `List`**.
- `Type(Conic)` — **заблокировано строковым результатом** (`Conic.type` есть
  как поле, но нужен `Text`/строковый вывод).

**Итог:** Tier A и Tier B закрыты (2026-07-05). Tier C — семейство `Tangent`
закрыто: `Tangent(Line,Conic)` → `tangent_lK/Kl` (дуальная коника),
`Tangent(Point/x,Function)` → `tangent_pF/iF/mF` (производная),
`Tangent(Circle,Circle)` → `tangent_cc` (общие касательные через центры
гомотетии) — **ГОТОВО**. Осталось в Tier C: `Dilate` для conic/function,
`ClosestPoint` для conic/function, `Stretch`/`Shear`; `TriangleCenter`,
`Barycenter`, `Type` — после появления БД Кимберлинга / типа `List` /
строкового вывода соответственно.

## Приложение: текущие dispatch-команды AnimaGeo

Список сгруппирован по GeoGebra-имени, без внутренних helper-функций.

| Command | Реализованные dispatch-сигнатуры |
|---|---|
| `Abs` | `abs_i`, `abs_m` |
| `Add` | `add_ii`, `add_mi`, `add_mm`, `add_ms`, `add_pp`, `add_pv`, `add_ss`, `add_vp`, `add_vv` |
| `Angle` | `angle_ppp` |
| `AngleSize` | `angle_size_A`, `angle_size_i`, `angle_size_ppp` |
| `AngularBisector` | `angular_bisector_ll`, `angular_bisector_ppp`, `angular_bisector_ss` |
| `Arc` | `arc_cpp` |
| `Area` | `area_P` |
| `AreCollinear` | `are_collinear_ppp` |
| `AreComplementary` | `are_complementary_aa` |
| `AreConcurrent` | `are_concurrent_lll` |
| `AreConcyclic` | `are_concyclic_pppp` |
| `AreCongruent` | `are_congruent_aa`, `are_congruent_ss` |
| `AreEqual` | `are_equal_mi`, `are_equal_mm`, `are_equal_pp` |
| `AreParallel` | `are_parallel_ll`, `are_parallel_ls`, `are_parallel_rr`, `are_parallel_sl`, `are_parallel_ss` |
| `ArePerpendicular` | `are_perpendicular_ll`, `are_perpendicular_lr`, `are_perpendicular_ls`, `are_perpendicular_rl`, `are_perpendicular_sl`, `are_perpendicular_ss` |
| `Assign` | `assign_i`, `assign_p`, `assign_v` |
| `Axes` | `axes_K` |
| `Center` | `center_K`, `center_c` |
| `Centroid` | `centroid_P` |
| `Circle` | `circle_pi`, `circle_pm`, `circle_pp`, `circle_ppp`, `circle_ps` |
| `CircleArc` | `circle_arc_ppp` |
| `CircleSector` | `circle_sector_ppA`, `circle_sector_ppi`, `circle_sector_ppp` |
| `CircumcircleArc` | `circumcircle_arc_ppp` |
| `CircumcircleSector` | `circumcircle_sector_ppp` |
| `Coefficients` | `coefficients_K` |
| `Conic` | `conic_T`, `conic_ppppp` |
| `ContainedBy` | `contained_by_pc`, `contained_by_pl` |
| `Cos` | `cos_i` |
| `Ctan` | `ctan_i` |
| `Directrix` | `directrix_K` |
| `Distance` | `distance_pp` |
| `Div` | `div_Ai`, `div_ii`, `div_mi`, `div_mm`, `div_ms`, `div_pi`, `div_si`, `div_sm`, `div_ss`, `div_vi` |
| `Eccentricity` | `eccentricity_K` |
| `Ellipse` | `ellipse_ppi`, `ellipse_ppm`, `ellipse_ppp` |
| `Equality` | `equality_PP`, `equality_Pm`, `equality_aa`, `equality_mi`, `equality_mm`, `equality_ms`, `equality_pp`, `equality_si`, `equality_sm`, `equality_ss` |
| `Focus` | `focus_K` |
| `Function` | `function_T` |
| `Hyperbola` | `hyperbola_ppi`, `hyperbola_ppm`, `hyperbola_ppp` |
| `ImplicitCurve` | `implicit_curve_T` |
| `Intersect` | `intersect_Cl`, `intersect_Cli`, `intersect_Cr`, `intersect_Cri`, `intersect_Cs`, `intersect_Csi`, `intersect_FF`, `intersect_FFi`, `intersect_FI`, `intersect_FIi`, `intersect_FK`, `intersect_FKi`, `intersect_Fc`, `intersect_Fci`, `intersect_Fl`, `intersect_Fli`, `intersect_IF`, `intersect_IFi`, `intersect_II`, `intersect_IIi`, `intersect_IK`, `intersect_IKi`, `intersect_Ic`, `intersect_Ici`, `intersect_Il`, `intersect_Ili`, `intersect_Ir`, `intersect_Iri`, `intersect_Is`, `intersect_Isi`, `intersect_KF`, `intersect_KFi`, `intersect_KI`, `intersect_KIi`, `intersect_KK`, `intersect_KKi`, `intersect_Kc`, `intersect_Kci`, `intersect_Kl`, `intersect_Kli`, `intersect_Kr`, `intersect_Kri`, `intersect_Ks`, `intersect_Ksi`, `intersect_Sl`, `intersect_Sli`, `intersect_cF`, `intersect_cFi`, `intersect_cI`, `intersect_cIi`, `intersect_cK`, `intersect_cKi`, `intersect_cc`, `intersect_cci`, `intersect_cl`, `intersect_cli`, `intersect_cr`, `intersect_cri`, `intersect_cs`, `intersect_csi`, `intersect_lC`, `intersect_lCi`, `intersect_lF`, `intersect_lFi`, `intersect_lI`, `intersect_lIi`, `intersect_lK`, `intersect_lKi`, `intersect_lS`, `intersect_lSi`, `intersect_lc`, `intersect_lci`, `intersect_ll`, `intersect_lr`, `intersect_ls`, `intersect_rC`, `intersect_rCi`, `intersect_rI`, `intersect_rIi`, `intersect_rK`, `intersect_rKi`, `intersect_rc`, `intersect_rci`, `intersect_rl`, `intersect_rr`, `intersect_rs`, `intersect_sC`, `intersect_sCi`, `intersect_sI`, `intersect_sIi`, `intersect_sK`, `intersect_sKi`, `intersect_sc`, `intersect_sci`, `intersect_sl`, `intersect_sr`, `intersect_ss` |
| `Line` | `line_pl`, `line_pp`, `line_pr`, `line_ps`, `line_pv`, `line_s` |
| `LineBisector` | `line_bisector_pp`, `line_bisector_s` |
| `LinearEccentricity` | `linear_eccentricity_K` |
| `MajorAxis` | `major_axis_K` |
| `Midpoint` | `midpoint_pp`, `midpoint_s` |
| `MinorAxis` | `minor_axis_K` |
| `Mirror` | `mirror_cc`, `mirror_cl`, `mirror_cp`, `mirror_ll`, `mirror_lp`, `mirror_ls`, `mirror_pc`, `mirror_pl`, `mirror_pp`, `mirror_ps` |
| `Mult` | `mult_Ai`, `mult_iA`, `mult_ii`, `mult_im`, `mult_ip`, `mult_is`, `mult_iv`, `mult_mi`, `mult_mm`, `mult_ms`, `mult_pi`, `mult_sm`, `mult_ss`, `mult_vi` |
| `OrthogonalLine` | `orthogonal_line_pl`, `orthogonal_line_pr`, `orthogonal_line_ps` |
| `Parabola` | `parabola_pl`, `parabola_pr`, `parabola_ps` |
| `Point` | `point_K`, `point_c`, `point_ii`, `point_l`, `point_s` |
| `Polar` | `polar_Kp`, `polar_pK`, `polar_pc` |
| `Polygon` | `polygon`, `polygon_ppi` |
| `Pow` | `pow_ii`, `pow_mi`, `pow_si` |
| `Prove` | `prove_b` |
| `Radius` | `radius_c` |
| `Ray` | `ray_pp` |
| `Rotate` | `rotate_lAp`, `rotate_pAp`, `rotate_pap`, `rotate_pip`, `rotate_vAp` |
| `Segment` | `segment_pp`, `segment_pv` |
| `SemiMajorAxisLength` | `semi_major_axis_length_K` |
| `SemiMinorAxisLength` | `semi_minor_axis_length_K` |
| `Semicircle` | `semicircle_pp` |
| `Sin` | `sin_i` |
| `Sqrt` | `sqrt_i` |
| `Sub` | `sub_AA`, `sub_Aa`, `sub_aA`, `sub_ii`, `sub_mm`, `sub_ms`, `sub_pp`, `sub_pv`, `sub_sm`, `sub_ss`, `sub_vv` |
| `Tan` | `tan_i` |
| `Tangent` | `tangent_Kp`, `tangent_pK`, `tangent_pc`, `tangent_pci` |
| `Touches` | `touches_cc`, `touches_cl`, `touches_lc` |
| `Translate` | `translate_cv`, `translate_pv`, `translate_sv` |
| `USub` | `u_sub_A`, `u_sub_a`, `u_sub_i`, `u_sub_m`, `u_sub_p`, `u_sub_v` |
| `Value` | `value_A` |
| `Vector` | `vector_ii`, `vector_p`, `vector_pp`, `vector_vi` |
| `Vertex` | `vertex_K` |
