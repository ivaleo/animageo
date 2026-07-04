# AnimaGeo Guide

Интерактивное руководство по AnimaGeo. Каждый пример можно редактировать
в браузере — локальный Python-сервер перерисовывает иллюстрацию.

## Запуск

```bash
cd /path/to/animageo
PYTHONPATH=. python3.13 docs/guide/server/serve.py
```

Откроется `http://127.0.0.1:8765/`. Гайд доступен по этому URL; для edit-run
цикла нужен запущенный сервер, но статическая версия читается и без него.

**Безопасность.** Эндпоинт `/render` исполняет произвольный Python
(`AnimaGeoScene.putCode()`). Сервер слушает только `127.0.0.1` — не
перенаправляйте его в сеть без sandbox'а.

## Структура

```
docs/guide/
├── index.html            Обзор + карта разделов + hero-пример
├── 01-introduction.html  §1 · Что такое AnimaGeo
├── ... (остальные главы в работе)
├── css/style.css         Базовые стили + стили интерактивных блоков
├── js/interactive.js     Edit-Run-Reset-Close логика, fetch → /render
├── server/
│   ├── serve.py          FastAPI: GET /, POST /render, static mounts
│   └── runner.py         render_example(spec) — чистая функция, SVG-текст
├── assets/               Сгенерированные SVG-примеры + диаграммы (generate_svg.py)
└── examples/             generate_svg.py + anim_scenes.py — источник примеров
```

## Как работает интерактив

Каждый редактируемый пример — блок `<div class="ex interactive">` с
атрибутом `data-example`, содержащим JSON-шаблон (все поля, кроме `code`).
Начальный код берётся из внутреннего `<pre><code>...</code></pre>`.

При клике **Edit** шаблон расширяется текстом из редактора и шлётся
POST-запросом на `/render`; сервер отвечает `image/svg+xml`, фронтенд
встраивает SVG в `<img>` через data-URL.

Рендер — в районе 30–150 мс на пример (manim Scene + Cairo SVG, без TeX
только для подписей). LRU-кэш хранит 128 последних рендеров.

## Зависимости

Нужны (сверх обычных animageo-зависимостей):

```
pip install fastapi uvicorn pydantic
```

Уже установлены в рабочем окружении (проверено: fastapi 0.135, uvicorn 0.44).

## Почему не Pyodide

animageo зависит от manim, Cairo, scipy и sympy — эти библиотеки либо
отсутствуют в Pyodide, либо работают через wheels, недоступные для
animageo-пайплайна. Локальный сервер — единственный реалистичный путь.
Когда гайд поедет в продакшен, перед ним можно поставить такой же
сервер-процесс.
