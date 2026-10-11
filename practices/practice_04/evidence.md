# Подтверждения выполнения требований Practice 4

Документ собран из реальных журналов OpenCode: сессии экспортированы командой
`opencode session export <id>` (JSON, stdio-MCP и т.д. — только текст сессий;
экспорты проверены — **секретов/API-ключей в них нет**). Все цитаты ниже —
фрагменты tool-вызовов из экспортов; session ID реальны.

Сессии, использованные для подтверждений (экспортированы 11.10.2026):

| Session ID | Название |
|---|---|
| `ses_ed3cf898dffeCH8bv6G0nn7Mqc` | Проверка инструкций проекта из AGENTS.md |
| `ses_ed3c753c0ffeAv5waeJgYZ4n11` | Проверка skill test-driven-change в OpenCode |
| `ses_ed397a2a0ffeleuQDntCndIw45` | Проверка автосрабатывания Hook FAIL в OpenCode |
| `ses_ed38b5b3fffeL67Q24zw2OFZAC` | Practice 4: этап RED для is_subscribed (worktree) |

---

## 1. Применение инструкций AGENTS.md

- **Инструмент:** инструкции проекта OpenCode (`AGENTS.md`).
- **Что выполнено:** в сессии `ses_ed3cf898dffeCH8bv6G0nn7Mqc` агент прочитал
  `AGENTS.md`, `docs/requirements.md`, `docs/style-guide.md`, `service.py`,
  `tests/test_service.py`, `scripts/check.sh` и действовал по правилам
  (проверка после правок через `./scripts/check.sh`, тесты ранее реализации).
- **Фактический результат:** в сессии создания проекта
  `ses_ed46532f5ffetypNnJsDxd81lB` система подгрузила файл как активные
  инструкции: `system: "Instructions from: /…/practice_04/demo/AGENTS.md"`.
  Правила соблюдались в обеих Feature-сессиях (см. п. 2 и 6).
- **Источник:** `ses_ed3cf898dffeCH8bv6G0nn7Mqc`, `ses_ed46532f5ffetypNnJsDxd81lB`.

## 2. Вызов skill test-driven-change

- **Инструмент:** tool `skill` в OpenCode.
- **Что выполнено:** tool-вызов `skill` с входом `{"id": "test-driven-change"}`.
- **Фактический результат:** в ответ вернулось содержимое skill
  («A procedure for implementing a small Python feature through test-driven
  development…»); дальше агент вёл цикл RED → GREEN → VERIFY (см. п. 5).
- **Источник:** `ses_ed38b5b3fffeL67Q24zw2OFZAC` (вызов `skill` -> `<skill_content
  name="test-driven-change">`), также `ses_ed3cf898dffeCH8bv6G0nn7Mqc`,
  `ses_ed3c753c0ffeAv5waeJgYZ4n11`.

## 3. Успешный вызов MCP run_project_check

- **Инструмент:** собственный MCP-сервер `project-check-mcp`, tool
  `run_project_check`, вызванный через Code Mode (`execute`).
- **Что выполнено:** `tools["project-check-mcp"].run_project_check({ check: "tests" })`.
- **Фактический результат:**
  `{"check": "tests", "success": true, "exit_code": 0, "stderr": "…Ran 3 tests
  in 0.000s\n\nOK"}`.
- **Дополнительно:** автономный MCP-клиент `mcp/smoke_test.py` (полный
  handshake `initialize`, `tools/list` → `["run_project_check"]`,
  `tools/call check=tests`) завершился успешно, сервер запускался из чужого
  cwd (`demo/tests`) — зависимость от рабочего каталога отсутствует.
- **Источник:** `ses_ed3c753c0ffeAv5waeJgYZ4n11` (вызовы `execute` + вывод
  `python3 mcp/smoke_test.py`).

## 4. Ошибочный вызов MCP (check="deploy")

- **Инструмент:** тот же tool `run_project_check`.
- **Что выполнено:** `run_project_check({ check: "deploy" })`.
- **Фактический результат:**
  `{"check": "deploy", "success": false, "error": "Unsupported check: 'deploy'.
  Allowed values: \"tests\"."}` — ошибочный вход обработан, сервер не упал.
- **Источник:** `ses_ed3c753c0ffeAv5waeJgYZ4n11`.

## 5. Автоматическая проверка Hook: AUTO CHECK FAIL и PASS

- **Инструмент:** plugin `check-after-edit` (Hook в OpenCode).
- **FAIL (Feature B, этап RED):** правка `tests/test_service.py` →
  в результат tool-вызова добавлено `AUTO CHECK FAIL, exit code: 1, …,
  AttributeError: module 'service' has no attribute 'is_subscribed'`.
- **PASS (Feature B, этап GREEN):** правка `service.py` →
  `AUTO CHECK PASS, exit code: 0, …, test_is_subscribed_* … ok`.
- **FAIL/PASS (независимая проверка):** сессия `ses_ed397a2a0ffeleuQDntCndIw45`
  — временный `tests/test_hook_probe.py`: при создании с заведомо падающим
  тестом `AUTO CHECK FAIL` (exit code 1), после исправления `AUTO CHECK PASS`
  (exit code 0); probe-файл затем удалён из проекта.
- **Источники:** `ses_ed38b5b3fffeL67Q24zw2OFZAC`,
  `ses_ed397a2a0ffeleuQDntCndIw45`.

## 6. Feature B в отдельном worktree

- **Инструмент:** `git worktree` + отдельная ветка.
- **Что выполнено:** в сессии `ses_ed38b5b3fffeL67Q24zw2OFZAC` все правки шли
  по путям `/home/abuz228/ITMOv2-feature-b/practices/practice_04/demo/…`;
  команда `git rev-parse --show-toplevel && git branch --show-current &&
  git status --short && git worktree list` вернула:
  - `worktree: /home/abuz228/ITMOv2 → 8fe58f5 [practice_04]`
  - `worktree: /home/abuz228/ITMOv2-feature-b → 8fe58f5 [practice_04_feature_b]`
- **Фактический результат:** после объединения обе ветки указывают на
  `fce0954 "Implement feature B"`, `git worktree list` содержит оба worktree;
  полный прогон `./scripts/check.sh` — 17 тестов OK.
- **Источник:** `ses_ed38b5b3fffeL67Q24zw2OFZAC`; текущее состояние —
  `git branch --show-current` → `practice_04`, `git worktree list`.

---

## Что не подтверждается журналами (нужен скриншот)

- **Живая демонстрация ревьюеру** (как студент показывает применение
  инструментов на защите) — это не журнал; подтверждается демо.
- **Визуальное подтверждение Hook в TUI** — метка `AUTO CHECK …` есть в
  журналах, но если ревьюеру нужен интерфейс: скриншот ответа плагина после
  правки Python-файла (FAIL и PASS).
- **Вкладка `/mcps` или MCP-статус** — connection-status в интерфейсе;
  скриншот `opencode mcp list` или `/mcps` с сервером `project-check-mcp`.
- **Вызов skill в интерфейсе** — скриншот tool-вызова `skill` с
  `<skill_content name="test-driven-change">`.

Перечисленные выше пункты 1–6 подтверждаются самими сессиями; скриншоты нужны
только как вспомогательная иллюстрация для ревьюера.

## Как воспроизвести командами

```sh
cd practices/practice_04/demo
./scripts/check.sh                     # 17 тестов
opencode session list                  # список сессий проекта
opencode session export ses_ed38b5b3fffeL67Q24zw2OFZAC   # экспорт сессии
python3 mcp/smoke_test.py              # MCP: корректный и ошибочный вход
```