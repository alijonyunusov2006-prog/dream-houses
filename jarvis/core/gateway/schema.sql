-- JARVIS gateway: очередь задач и сообщений в Supabase (этап 3).
-- Отдельная схема, чтобы не пересекаться с CRM владельца в том же проекте Supabase.

create schema if not exists jarvis;

create table if not exists jarvis.messages (
  id            bigserial primary key,
  received_at   timestamptz not null default now(),
  chat_id       bigint      not null,
  telegram_id   bigint      not null,           -- message_id в Telegram
  kind          text        not null check (kind in ('text','voice','photo','document','command','callback')),
  text          text,
  file_id       text,                           -- Telegram file_id для голосовых/фото
  file_path     text,                           -- куда скачано локальным агентом
  transcript    text,                           -- расшифровка голосового
  handled       boolean     not null default false,
  unique (chat_id, telegram_id)                 -- защита от повторной обработки
);

create table if not exists jarvis.tasks (
  id            text primary key,               -- короткий id, например 'crm-2026-09-27-a'
  title         text        not null,
  project       text,
  priority      smallint    not null default 3 check (priority between 1 and 5),
  deadline      timestamptz,
  estimate_min  integer     not null default 30,
  depends_on    text[]      not null default '{}',
  resources     text[]      not null default '{}',
  state         text        not null default 'pending'
                check (state in ('pending','running','paused','blocked','done','failed','waiting_human')),
  progress      text,
  checkpoint    jsonb       not null default '{}'::jsonb,
  attempts      smallint    not null default 0,
  source_msg    bigint references jarvis.messages(id),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create table if not exists jarvis.events (
  id            bigserial primary key,
  ts            timestamptz not null default now(),
  task_id       text references jarvis.tasks(id),
  kind          text        not null,           -- 'report','question','approval_request','approval','error','heartbeat'
  payload       jsonb       not null default '{}'::jsonb
);

-- Пульс локального агента: шлюз отвечает «ПК недоступен», если пульс старше 2 минут.
create table if not exists jarvis.agent_heartbeat (
  agent_id      text primary key,
  last_seen     timestamptz not null default now(),
  info          jsonb       not null default '{}'::jsonb
);

create index if not exists tasks_state_idx on jarvis.tasks (state, priority, deadline);
create index if not exists messages_unhandled_idx on jarvis.messages (handled) where handled = false;
