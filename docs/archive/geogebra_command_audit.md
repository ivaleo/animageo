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
| `AffineRatio` | MISSING | - | Нет команды. |
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
| `CrossRatio` | MISSING | - | Нет команды. |
| `Cubic` | MISSING | - | Нет треугольной кубики. |
| `Difference` | MISSING | - | Нет булевой разности регионов. |
| `Direction` | MISSING | - | Нет команды направления. |
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
| `Point` | PARTIAL | `point_`, `point_ii`, `point_c`, `point_l`, `point_r`, `point_s`, `point_C`, `point_S`, `point_L`, `point_K` | Есть точки на circle/line/ray/segment/arc/sector/locus/conic. Нет `Point(Point,Vector)`; параметрические variants покрыты частично через `tparam`. |
| `PointIn` | MISSING | - | Нет точки внутри региона. |
| `Polygon` | PARTIAL | `polygon`, `polygon_ppi` | Есть по точкам и правильный многоугольник по двум точкам и числу. Нет `Polygon(List)`, нет direction form. |
| `Polyline` | MISSING | - | Нет типа polyline. |
| `Prove` | PARTIAL | `prove_b` | Просто возвращает boolean; не реализует GeoGebra symbolic prove полностью. |
| `ProveDetails` | MISSING | - | Нет. |
| `Radius` | PARTIAL | `radius_c`, `radius_K` | `Conic`-круг поддержан. |
| `RandomPointIn` | MISSING | - | Нет. |
| `Ray` | PARTIAL | `ray_pp` | Нет `Ray(Point,Vector)`, хотя docs GeoGebra это поддерживает. |
| `RigidPolygon` | MISSING | - | Нет. |
| `Sector` | MISSING | - | GeoGebra `Sector(Conic,Point,Point)` / params не реализован. Есть `CircleSector*` под другим именем. |
| `Segment` | PARTIAL | `segment_pp`, `segment_pv` | Нет `Segment(Point,Length)` под GeoGebra-сигнатурой. |
| `Semicircle` | OK | `semicircle_pp` | 2 точки. |
| `Slope` | MISSING | - | Нет команды. |
| `Tangent` | PARTIAL | `tangent_pc`, `tangent_pci`, `tangent_pK`, `tangent_Kp` | Есть point-circle и point-conic. Нет point/function, x/function, line/conic, circle/circle, point/implicit curve. |
| `TriangleCenter` | MISSING | - | Нет. |
| `TriangleCurve` | MISSING | - | Нет. |
| `Trilinear` | MISSING | - | Нет. |
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
| `Conic(6 Numbers)` | MISSING | - | Нет dispatch `conic_iiiiii`. |
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
| `Midpoint(Conic)` | NAME_MISMATCH | `center_K` | GeoGebra использует `Midpoint`; AnimaGeo не имеет `midpoint_K`. |
| `MinorAxis(Conic)` | OK | `minor_axis_K` | Для ellipse/hyperbola. |
| `OsculatingCircle` | MISSING | - | Нет. |
| `Parabola(Point,Line)` | OK | `parabola_pl` | Также есть `parabola_ps`, `parabola_pr` как расширение. |
| `Parameter` | MISSING | - | Нет. |
| `PathParameter` | MISSING | - | Только внутренний `Element.tparam`. |
| `Perimeter` | PARTIAL | `perimeter_P` | Polygon perimeter. |
| `Polar(Point,Conic)` | OK | `polar_pK`, `polar_Kp` | Есть point-conic. |
| `Polar(Line,Conic)` | MISSING | - | GeoGebra возвращает pole point; не реализовано. |
| `Radius(Conic)` | PARTIAL | `radius_c`, `radius_K` | `Conic`-круг поддержан. |
| `Sector(Conic,...)` | MISSING | - | Нет GeoGebra `Sector`. |
| `SemiMajorAxisLength(Conic)` | OK | `semi_major_axis_length_K` | Circle/ellipse/hyperbola. |
| `SemiMinorAxisLength(Conic)` | OK | `semi_minor_axis_length_K` | Circle/ellipse/hyperbola. |
| `Semicircle(Point,Point)` | OK | `semicircle_pp` | Есть. |
| `Tangent(Point,Conic)` | OK | `tangent_pK`, `tangent_Kp` | Есть point-conic. |
| `Tangent(Line,Conic)` | MISSING | - | Нет параллельных касательных к конике. |
| `Tangent(Circle,Circle)` | MISSING | - | Нет общих касательных двух окружностей. |
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
| `Dilate` | MISSING | - | Нет. |
| `Shear` | MISSING | - | Нет. |
| `Stretch` | MISSING | - | Нет. |

## Vector / Matrix Commands

Реализовано в ядре:

- `Vector(Point,Point)` -> `vector_pp`.
- `Vector(Point)` -> `vector_p`.
- `Vector(Number,Number)` -> `vector_ii`.
- `Vector(Vector,Number)` -> `vector_vi` как масштабирование до модуля.
- Арифметика векторов/точек: `Add`, `Sub`, `Mult`, `Div`, `USub`.

GeoGebra-команды из Vector and Matrix Commands, которых нет:

- `ApplyMatrix`, `Direction`, `Length`, `PerpendicularVector`,
  `UnitPerpendicularVector`, `UnitVector`, `Dot`, `Cross`, matrix commands
  (`Determinant`, `Transpose`, `Invert`, `SVD`, etc.).

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
