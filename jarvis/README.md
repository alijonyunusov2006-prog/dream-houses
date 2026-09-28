# JARVIS

Персональный автономный ИИ-управляющий: голосовые задания → ТЗ и план → разработка через Claude Code →
проверка → отчёт в Telegram. Живёт в одной папке вместе со вторым мозгом (`brain/`, Obsidian).

- **План и архитектура:** [`PLAN.md`](PLAN.md) · **Аудит существующего:** [`AUDIT.md`](AUDIT.md) · **Конституция:** [`CLAUDE.md`](CLAUDE.md)
- **Установка базы OpenJarvis на Windows:** `Установить-Jarvis.bat` (подробности — [`docs/INSTALL-BASE.md`](docs/INSTALL-BASE.md))

## Что в папке

| Путь | Назначение |
|---|---|
| `brain/` | второй мозг: правила трёх уровней, вопросы, профиль, проекты, уроки, дневник |
| `AGENTS.md` | карта агентов: кто за что отвечает, навыки, правила совместной работы |
| `.claude/agents/` | роли: planner, developer, tester, archicad, 3d, crm, content, browser, secretary, sysadmin |
| `core/scripts/` | служебные скрипты (аудит диска и др.) |
| `.claude/settings.json` | хуки политики доступа и разрешения Claude Code |
| `skills/` | библиотека навыков (SKILL.md + tests + CHANGELOG) |
| `core/jarviscore/` | политика, планировщик, раннер `claude -p`, отчёты, хуки, `jv` CLI |
| `core/gateway/` | контракт облачной очереди (Supabase) — этап 3 |
| `config/` | `settings.toml`, `allowlist.toml`, `.env.example` |
| `docs/` | архитектура, решения (ADR), установка базы |
| `tests/` | тесты ядра |

## Быстрый старт (ПК с Windows)

```powershell
git clone <репозиторий> C:\jarvis
cd C:\jarvis
python -m pip install -e ".[dev]"
python -m pytest -q                    # тесты ядра
python -m jarviscore.cli check --command "shutdown /s"   # → ask
claude                                 # Claude Code читает CLAUDE.md, агенты и хуки
```

Obsidian → «Open folder as vault» → `C:\jarvis\brain`.

## Состояние
Этап 2 (каркас и тех-план). Ядро покрыто тестами; Telegram-шлюз, локальный агент и речь — этап 3.
Что реально работает, а что нет — всегда в `brain/30-projects/jarvis/статус.md`.
