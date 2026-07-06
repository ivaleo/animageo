# AI Construction Lab

Экспериментальный стенд для второго этапа AI-пайплайна: запрос → AI-response
с `construction_dsl` → SVG → ручная оценка результата.

## Workflow

1. Просмотреть новые `feedback/*.json` и выделить только обобщаемые правила.
   Такие выводы нужно переносить в `../ai_construction_generation_context.md`;
   не встраивать пользовательский feedback в HTML-галерею или `library.json`.
2. Добавить или изменить кейсы в `cases.json`.
3. Сгенерировать SVG и HTML:

   ```bash
   PYTHONPATH=. python3 docs/ai_construction_lab/generate_gallery.py
   ```

4. Запустить локальный lab-сервер:

   ```bash
   PYTHONPATH=. python3.13 docs/ai_construction_lab/serve.py --port 8765
   ```

   Prompt-only генерация ручного кейса использует DeepSeek API по умолчанию.
   Ключ читается из окружения `DEEPSEEK_API_KEY`, `deepseek_api`,
   `DEEPSEEK_API` или `DEEPSEEK_KEY`. Сервер также автоматически читает
   `.env` из корня этого репозитория, `docs/ai_construction_lab/.env`,
   соседнего проекта `../animageo_web/.env`, `~/.animageo.env` и
   `~/.config/animageo/.env`. Другой путь можно задать через
   `ANIMAGEO_LAB_ENV`. Модель берется из `DEEPSEEK_CONSTRUCTION_MODEL`,
   затем `DEEPSEEK_MODEL`, затем `DEEPSEEK_STYLE_MODEL`, иначе используется
   `deepseek-v4-pro`.

5. Открыть `http://127.0.0.1:8765/` в браузере.
6. Для каждого результата поставить оценку, отметить проблемы и написать
   комментарий.
7. При необходимости раскрыть `Generate manual case` и ввести только prompt.
   Lab-сервер вызовет AI с `../ai_construction_generation_context.md`,
   отрендерит SVG, добавит кейс в `cases.json`, обновит
   `assets/library.json` и пересоберет `index.html`. В advanced-блоке можно
   вставить готовый AI-response JSON или только `construction_dsl`, чтобы
   протестировать рендер без вызова AI.
8. Нажать `Export feedback` в HTML. При открытии через lab-сервер JSON
   сохраняется сразу в `docs/ai_construction_lab/feedback/`.

Если открыть `index.html` напрямую как файл, браузер не может сам писать в
папку проекта. В этом режиме кнопка `Export feedback` работает как fallback:
скачивает JSON, который можно импортировать или положить в `feedback/`
вручную.

Браузерная страница хранит черновые оценки в `localStorage`. Это удобно для
ручной работы, но исходником для анализа считается экспортированный JSON.

## Что Считать Ошибкой

- AI использовал DSL для общей стилизации вместо style JSON.
- AI придумал несуществующую фабрику или имя элемента.
- Конструкция формально построилась, но математический смысл неверный.
- Скрытые вспомогательные элементы видны без причины.
- Запрос был неоднозначный, но в `notes` нет допущения.
- Требовалась patch-операция, а ответ пересобрал сцену с нуля.

## Структура

- `cases.json` — исходные prompt/response пары; текущий банк содержит 99
  экспериментальных кейса.
- `generate_gallery.py` — рендерит SVG и собирает статическую HTML-галерею.
- `serve.py` — локально обслуживает HTML, принимает `POST /feedback` и
  `POST /cases` для ручного добавления рендеримых кейсов.
- `assets/results/*.svg` — результат исполнения DSL.
- `assets/dsl/*.py` — извлеченный DSL по каждому кейсу.
- `assets/library.json` — машинная сводка последней генерации.
- `feedback/` — место для экспортов ручной оценки.
