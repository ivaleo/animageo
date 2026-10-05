# Рецепты условий v1 (карточки для помощника)

animageo 1.9.0a2 (план L3 §3.5, `animageo/native/recipes/v1/*.json`, контракт —
`docs/native/conditions.md` §4). Карточка на рецепт в формате карточек
знаний веба (`kind: recipe`): условие, получатель, что строится, фраза.
Порядок — по `priority`; получатель — переменная `X`, по умолчанию — точка с
наибольшим ключом порядка (последняя созданная). Места — скрытые
вспомогательные элементы (`role: aux`); получатель становится
`point.on_path` на месте (два условия — пересечение двух мест).

## on_object

```yaml
id: recipe/on_object
kind: recipe
title: Точка на объекте
terms: [точка на окружности, точка на отрезке, лежит на, принадлежит]
sections: [construction]
```

- Условие: `X ∈ W` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, W: path.
- Место: — (место — сам объект `W`); затем `X` — `point.on_path` на месте.
- Фраза: «{X} на {W}».
- Приоритет: 1.

## on_line

```yaml
id: recipe/on_line
kind: recipe
title: Точка на прямой через две точки
terms: [лежит на прямой, на одной прямой, коллинеарны]
sections: [construction]
```

- Условие: `X ∈ AB` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point.
- Место: `line.by_points`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на прямой {A}{B}».
- Приоритет: 2.

## length.value

```yaml
id: recipe/length.value
kind: recipe
title: Длина отрезка задана
terms: [длина равна, расстояние равно, отрезок длины]
sections: [construction]
```

- Условие: `|AX| = V` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, V: positive.
- Место: `circle.center_radius`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на окружности с центром {A} радиуса {V}: |{A}{X}| = {V}».
- Приоритет: 3.

## equal_length.vertex

```yaml
id: recipe/equal_length.vertex
kind: recipe
title: Равные отрезки с общим концом
terms: [равные отрезки, AB = AC, равнобедренный]
sections: [construction]
```

- Условие: `|AB| = |AX|` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point.
- Место: `circle.center_point`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на окружности с центром {A} через {B}: |{A}{B}| = |{A}{X}|».
- Приоритет: 4.

## equal_length.free

```yaml
id: recipe/equal_length.free
kind: recipe
title: Равные отрезки без общего конца
terms: [равные отрезки, AB = CD, отложить отрезок]
sections: [construction]
```

- Условие: `|AB| = |CX|` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point, C: point.
- Место: `segment.by_points`, `circle.center_segment`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на окружности с центром {C} радиуса |{A}{B}|».
- Приоритет: 5.

## parallel

```yaml
id: recipe/parallel
kind: recipe
title: Параллельность
terms: [параллельны, параллельная прямая, AB ∥ CD]
sections: [construction]
```

- Условие: `AB ∥ CX` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point, C: point.
- Место: `line.by_points`, `line.parallel`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на прямой через {C}, параллельной {A}{B}».
- Приоритет: 6.

## perpendicular

```yaml
id: recipe/perpendicular
kind: recipe
title: Перпендикулярность
terms: [перпендикулярны, перпендикуляр, AB ⟂ CD]
sections: [construction]
```

- Условие: `AB ⟂ CX` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point, C: point.
- Место: `line.by_points`, `line.perpendicular`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на прямой через {C}, перпендикулярной {A}{B}».
- Приоритет: 7.

## right_angle.vertex

```yaml
id: recipe/right_angle.vertex
kind: recipe
title: Прямой угол при получателе
terms: [прямой угол, угол 90°, окружность Фалеса]
sections: [construction]
```

- Условие: `∠AXB = 90°` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point.
- Место: `circle.diameter`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на окружности с диаметром {A}{B}: ∠{A}{X}{B} = 90°».
- Приоритет: 8.

## right_angle.side

```yaml
id: recipe/right_angle.side
kind: recipe
title: Прямой угол на стороне
terms: [прямой угол, угол 90°, перпендикуляр в точке]
sections: [construction]
```

- Условие: `∠ACX = 90°` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, C: point.
- Место: `line.by_points`, `line.perpendicular`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на перпендикуляре к {C}{A} в точке {C}: ∠{A}{C}{X} = 90°».
- Приоритет: 9.

## angle.value

```yaml
id: recipe/angle.value
kind: recipe
title: Угол задан в градусах
terms: [угол равен, угол в градусах, отложить угол]
sections: [construction]
```

- Условие: `∠ABX = D°` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point, D: angle_degrees.
- Место: `ray.at_angle`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на луче из {B}, повёрнутом от {B}{A} на {D}°».
- Приоритет: 10.

## angle.equal

```yaml
id: recipe/angle.equal
kind: recipe
title: Равные углы
terms: [равные углы, угол равен углу, отложить равный угол]
sections: [construction]
```

- Условие: `∠ABC = ∠DEX` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point, C: point, D: point, E: point.
- Место: `angle.by_points`, `measure.angle`, `number.expression`, `ray.at_angle`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на луче из {E}, повёрнутом от {E}{D} на ∠{A}{B}{C}».
- Приоритет: 11.

## tangent

```yaml
id: recipe/tangent
kind: recipe
title: Касательная
terms: [касается, касательная, касательная из точки]
sections: [construction]
```

- Условие: `PX касается W` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, P: point, W: circle.
- Место: `line.tangents_from_point`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на касательной из {P} к {W}».
- Приоритет: 12.

## equal_length.apex

```yaml
id: recipe/equal_length.apex
kind: recipe
title: Точка, равноудалённая от двух точек
terms: [равноудалена, XA = XB, серединный перпендикуляр]
sections: [construction]
```

- Условие: `|XA| = |XB|` (все формы: стороны и пары в любом порядке, угол наоборот).
- Получатель: `X`; требования: X: point, A: point, B: point.
- Место: `line.perpendicular_bisector`; затем `X` — `point.on_path` на месте.
- Фраза: «{X} на серединном перпендикуляре к {A}{B}: |{X}{A}| = |{X}{B}|».
- Приоритет: 13.

## Отказы

`unsupported_condition` (нет рецепта: варианты «оставить как проверку» и
«построить вручную»), `receiver_not_free`, `receiver_is_ancestor` (варианты
«сделать свободной» для участников-точек), `too_many_conditions` (у точки
уже два ограничения), `no_intersection_now` (два места сейчас не
пересекаются). Отказ документ не меняет.

## Формы фигур (`shape_conditions`)

Прямоугольный треугольник ABC — `∠ACB = 90°` (C); равнобедренный —
`|CA| = |CB|` (C); равносторонний — `|AB| = |AC|` и `|BA| = |BC|` (C);
параллелограмм ABCD — `AB ∥ DC`, `AD ∥ BC` (D); ромб — `|AB| = |BC|` (C) и
параллели для D; прямоугольник — `∠ABC = 90°` (C) и параллели; квадрат —
`∠ABC = 90°`, `|BC| = |AB|` (C) и параллели; трапеция — `AB ∥ DC` (D).
