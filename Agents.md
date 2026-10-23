# PiBot 2.0 — Agent Documentation

Complete technical reference for AI agents working on this repository. This document covers architecture, file structure, database schema, handler system, configuration, and all conventions needed to safely modify the codebase.

---

## 1. Project Overview

PiBot is a Telegram bot for BDSM community management with virtual economy, gamification, item shop, combat system, and punishment mechanics. It runs on Railway with PostgreSQL for persistent storage.

**Key facts:**
- **Framework:** `python-telegram-bot==22.5` (PTB). Uses `telegram.Update`, `telegram.ext.Application`, `CommandHandler`, `CallbackQueryHandler`, `MessageHandler`.
- **NOT aiogram.** Old docs/comments may reference aiogram — that is incorrect. The bot uses PTB exclusively.
- **Database:** PostgreSQL via `psycopg2-binary`. Connection pooling with `SimpleConnectionPool(1, 10)`.
- **Deployment:** Railway. `Procfile` runs `worker: python main.py`. Railway auto-deploys on push to `main`.
- **Language:** Python 3.11+. All handler functions are `async`. Database functions are synchronous (acceptable at this scale).

---

## 2. File Structure

```
PiBot2.0/
├── main.py                          # Entry point: init DB, register handlers, run polling
├── requirements.txt                 # Python dependencies (ASCII encoded)
├── procfile                         # Railway: worker: python main.py
├── castigados.json                  # Runtime: punished users (created automatically)
├── .env                             # Local only: environment variables (gitignored)
│
├── src/                             # Core modules
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py              # Re-exports from settings.py
│   │   └── settings.py              # All config: env vars, communities, admins, DOMs
│   ├── database/
│   │   ├── __init__.py              # Re-exports all DB functions
│   │   └── database.py             # PostgreSQL operations, schema, CRUD, text utils
│   ├── handlers/
│   │   └── __init__.py              # Empty (unused — handlers live in handlers/)
│   └── utils/
│       ├── __init__.py
│       └── helpers.py               # Shared utilities (currently minimal)
│
├── handlers/                        # All command/event handlers (NOT inside src/)
│   ├── _init_.py                    # Empty
│   ├── general.py                   # /ver, /dar, /quitar, /regalar, /NumAzar + admin check
│   ├── starting_menu.py             # /start, menu callbacks
│   ├── tienda.py                    # /tienda, shop callbacks, purchase flow
│   ├── inventario.py                # /inventario, item viewer, /usar
│   ├── theme_juegosYcasino.py       # /apostar, /aceptar, /cancelar, /jugar, /robar, dice handler
│   ├── battles.py                   # /lucha, /aceptarlucha, /ataque, combat DB operations
│   ├── rewards.py                   # Auto-rewards for media in specific topics
│   ├── welcoming.py                 # New member welcome (currently DISABLED in main.py)
│   └── roles.py                     # /AsignarRol, /MiRol
│
├── gifs_items/                      # GIF animations per item (subfolders by item name)
│   ├── bola mordaza/
│   ├── collar/
│   ├── cuerdas/
│   ├── fusta/
│   ├── galleta/
│   ├── latigo/
│   ├── paleta/
│   ├── sorpresa/
│   └── vara/
│
├── img_items/                       # Item images (collar.png, latigo.png, etc.)
├── docs/                            # (Cleaned — currently empty)
└── tests/                           # (Empty — for future unit tests)
```

### Important: Two `handlers/` directories exist
- `handlers/` (root level) — **THIS IS THE ACTIVE ONE.** All handler files live here.
- `src/handlers/` — Empty `__init__.py` only. Legacy placeholder. Do NOT add handlers here.

---

## 3. Environment Variables

Defined in `src/config/settings.py`. Loaded via `python-dotenv`.

| Variable | Required | Source | Description |
|---|---|---|---|
| `BOT_TOKEN` | Yes | @BotFather | Telegram bot API token |
| `DATABASE_URL` | Yes | Railway auto | PostgreSQL connection string |
| `BOT_USERNAME` | Yes | Manual | Bot's Telegram username without @ (for deep links) |
| `BOTMASTER_IDS` | Yes | Manual | Comma-separated Telegram user IDs for role=3 bootstrap |

Both `BOT_TOKEN` and `DATABASE_URL` raise `ValueError` if empty at import time.

---

## 4. Database Schema

PostgreSQL. All tables created in `src/database/database.py::create_tables()`.

### Tables

#### `usuarios_tb` — User accounts
| Column | Type | Constraints |
|---|---|---|
| `id_user` | BIGINT | PRIMARY KEY |
| `saldo` | INTEGER | DEFAULT 0 |

#### `items_tb` — Item catalog
| Column | Type | Constraints |
|---|---|---|
| `id_item` | SERIAL | PRIMARY KEY |
| `nombre` | TEXT | NOT NULL, UNIQUE |
| `precio` | INTEGER | NOT NULL |
| `imagen` | TEXT | NOT NULL (path to img_items/) |
| `descripcion` | TEXT | |
| `mensaje` | TEXT | Template with {sender_username} and {receptor_username} |

#### `items_usuarios_tb` — User inventory (many-to-many)
| Column | Type | Constraints |
|---|---|---|
| `id` | SERIAL | PRIMARY KEY |
| `id_user` | BIGINT | FK → usuarios_tb, NOT NULL |
| `id_item` | INTEGER | FK → items_tb, NOT NULL |
| `cantidad` | INTEGER | NOT NULL, DEFAULT 1 |
| | | UNIQUE(id_user, id_item) |

Indexes: `idx_usuario(id_user)`, `idx_item(id_item)`

#### `perfiles_tb` — User profiles
| Column | Type | Constraints |
|---|---|---|
| `id_user` | BIGINT | PK, FK → usuarios_tb |
| `username` | TEXT | UNIQUE |
| `nombre` | TEXT | NOT NULL |
| `rol` | TEXT | Profile role label (NOT the internal role system) |
| `orientacion_sexual` | TEXT | |
| `genero` | TEXT | |
| `ubicacion` | TEXT | |
| `edad` | INTEGER | |

> **Warning:** `perfiles_tb.rol` is a TEXT field for the user's BDSM profile role (e.g., "Dom", "Sub"). This is NOT the same as the internal permission role system in `roles_tb`.

#### `combates_tb` — Combat records
| Column | Type | Constraints |
|---|---|---|
| `id_combate` | SERIAL | PRIMARY KEY |
| `id_atacante` | BIGINT | FK → usuarios_tb, NOT NULL |
| `id_defensor` | BIGINT | FK → usuarios_tb, NOT NULL |
| `username_atacante` | TEXT | NOT NULL |
| `username_defensor` | TEXT | NOT NULL |
| `apuesta` | INTEGER | NOT NULL, DEFAULT 0 |
| `hp_atacante` | INTEGER | NOT NULL, DEFAULT 20 |
| `hp_defensor` | INTEGER | NOT NULL, DEFAULT 20 |
| `turno` | INTEGER | NOT NULL, DEFAULT 1 |
| `es_turno_atacante` | INTEGER | NOT NULL, DEFAULT 1 |
| `estado` | TEXT | NOT NULL, DEFAULT 'activo' |
| `ganador` | BIGINT | FK → usuarios_tb, nullable |
| `fecha_inicio` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

Indexes: `idx_combate_atacante(id_atacante)`, `idx_combate_defensor(id_defensor)`

#### `roles_tb` — Internal permission roles
| Column | Type | Constraints |
|---|---|---|
| `id_user` | BIGINT | PK, FK → usuarios_tb |
| `role` | INTEGER | NOT NULL, DEFAULT 1, CHECK (1, 2, 3) |

Role values: **1** = Usuario, **2** = Admin, **3** = BotMaster

### Default Items (seeded by `seed_items()`)

| Name | Price | Image | Description |
|---|---|---|---|
| Collar | 100 | img_items/collar.png | Collar for someone special |
| Latigo | 150 | img_items/latigo.png | Whip for misbehavers |
| Fusta | 120 | img_items/fusta.png | Training crop |
| Galleta | 50 | img_items/galleta.png | Cookie reward |
| Bola mordaza | 3000 | img_items/bola_mordaza.png | Silences its target for 30 seconds when used in a supergroup |
| Sorpresa | 300 | img_items/sorpresa.jpg | Mystery item |

---

## 5. Database API

All functions in `src/database/database.py`. Import via `from src.database.database import <function>`.

### Connection Management
| Function | Description |
|---|---|
| `_init_pool()` | Initialize connection pool (called automatically) |
| `_get_connection()` | Get connection from pool |
| `_put_connection(conn)` | Return connection to pool |

> **Pattern:** Every DB function calls `_get_connection()` and wraps the work in `try/except/finally` with `_put_connection(conn)` in the `finally` block. Always `conn.commit()` on success, `conn.rollback()` on error.

### Initialization
| Function | Description |
|---|---|
| `create_database()` | No-op (PostgreSQL provisioned by Railway) |
| `create_tables()` | CREATE TABLE IF NOT EXISTS for all 6 tables |
| `seed_items()` | Insert default items if not already present (idempotent) |
| `init_botmaster_roles(botmaster_ids)` | Ensure listed user IDs have role=3. Creates user/profile rows if needed. |
| `restart_all_combats()` | Set all `estado='activo'` combats to `'cancelado'` |

### User Operations
| Function | Signature | Returns |
|---|---|---|
| `insert_user` | `(id_user, saldo=0, username=None, nombre=None)` | `bool` |
| `get_campo_usuario` | `(id_user, columna)` | Value or `None` |
| `update_perfil` | `(id_user, **datos)` | `bool` |
| `delete_user` | `(id_user)` | `bool` |
| `get_id_user` | `(username)` | `int` or `None` |

**Valid columns for `get_campo_usuario`:** `nombre`, `username`, `rol`, `orientacion_sexual`, `genero`, `ubicacion`, `edad`, `saldo`, `id_user`. Column `saldo` reads from `usuarios_tb`; all others from `perfiles_tb`.

**Valid columns for `update_perfil`:** `nombre`, `username`, `rol`, `orientacion_sexual`, `genero`, `ubicacion`, `edad`.

### Balance Operations
| Function | Signature | Returns |
|---|---|---|
| `update_saldo` | `(id_user, saldo)` | `bool` |
| `dar_puntos` | `(id_user, cantidad)` | `bool` |
| `quitar_puntos` | `(id_user, cantidad)` | `bool` (floors at 0) |

### Item Operations
| Function | Signature | Returns |
|---|---|---|
| `insert_item` | `(nombre, precio, ruta_imagen, descripcion=None, mensaje=None)` | `bool` |
| `get_campo_item` | `(id_item, columna)` | Value or `None` |
| `update_item` | `(id_item, **datos)` | `bool` |
| `get_id_item` | `(nombre)` | `int` or `None` (uses `to_plain_text` normalization) |
| `delete_item` | `(id_item)` | `bool` |

### Inventory Operations
| Function | Signature | Returns |
|---|---|---|
| `insert_user_item` | `(id_user, id_item, cantidad=1)` | `bool` |
| `get_items` | `(id_user)` | `List[Dict]` with keys: id_item, nombre, precio, imagen, cantidad |
| `get_cantidad_item_inventario` | `(id_user, id_item)` | `int` |
| `update_cantidad` | `(user_id, item_id, cantidad)` | `bool` |
| `delete_item_user` | `(id_user, id_item)` | `bool` |

### Role Operations
| Function | Signature | Returns |
|---|---|---|
| `get_user_role` | `(id_user)` | `int` (0 if not found, 1/2/3 otherwise) |
| `set_user_role` | `(id_user, role)` | `bool` (uses ON CONFLICT upsert) |
| `check_permission` | `(id_user, min_role)` | `bool` (True if user's role >= min_role) |

### Text Utilities (also in database.py)
| Function | Description |
|---|---|
| `normalizar_nombre(first_name, last_name="")` | Clean and normalize user display names |
| `to_plain_text(s, keep_space=False)` | Convert to plain ASCII, strip accents/special chars |
| `reemplazar_acentos(cadena)` | Replace accented chars with base forms |

---

## 6. Handler System

### Handler Group Priority

PTB processes handlers by group number. Lower groups run first. A handler in group -1 can raise `ApplicationHandlerStop()` to prevent all other groups from running.

| Group | Purpose | Handlers |
|---|---|---|
| **-1** | Community blocking | `bloquear_comunidad` — blocks community `-1003397946543` |
| **0** | Core commands | `/start`, `/castigar`, `/perdonar` |
| **1** | Games & dice | `/apostar`, `/aceptar`, `/cancelar`, `/robar`, `/jugar`, `/usar`, `Dice.DICE` → `detectar_dado` |
| **2** | Economy & general | `/tienda`, `/inventario`, `/ver`, `/dar`, `/quitar`, `/regalar`, `/NumAzar`, `/id`, `/saludar`, `/AsignarRol`, `/MiRol`, `/lucha`, `/aceptarlucha`, `/ataque` |
| **3** | Media rewards | `PHOTO \| VIDEO \| ANIMATION` → `manejar_imagenes` |
| **4** | Welcome (DISABLED) | `NEW_CHAT_MEMBERS`, text in presentations topic |
| **5** | Callback queries | Menu, inventory pagination, shop callbacks |
| **6** | Punishment filter | `filters.ALL` → `filtro_castigo` (deletes messages from punished users outside punishment corner) |

### Handler File Details

#### `handlers/general.py`
- **Exports:** `ver`, `dar`, `quitar`, `regalar`, `numero_azar`
- **Internal:** `verificar_admin(user_id, update)` — checks role system (role >= 2) then falls back to config ADMINS list
- **Internal:** `get_receptor(update, context, args_length)` — resolves target user from @mention or reply. Returns user object, `None` (no target), or `False` (@ missing)
- **Internal:** `obtener_gif_aleatorio(nombre_producto)` — picks random GIF from `gifs_items/<name>/`
- **DB imports:** `get_campo_usuario`, `normalizar_nombre`, `update_perfil`, `insert_user`, `get_id_user`, `quitar_puntos`, `dar_puntos`, `reemplazar_acentos`, `check_permission`

#### `handlers/tienda.py`
- **Exports:** `tienda`, `tienda_callback`
- **Also exports (used by inventario):** `main_menu_markup()`, `mostrar_item()`
- **Private-chat only.** In groups, shows a deep-link button to open the bot in private.
- **Deep link:** `https://t.me/{BOT_USERNAME}?start=menu`
- **DB imports:** `get_campo_usuario`, `get_campo_item`, `quitar_puntos`, `insert_user_item`, `get_cantidad_item_inventario`, `update_cantidad`
- **Callback patterns:** `producto_<id>`, `volver_menu`, `volver_catalogo`, `comprar_<id>`

#### `handlers/inventario.py`
- **Exports:** `inventario`, `inventario_callback`, `usar`
- **Private-chat only** (same deep-link pattern as tienda).
- **Paginated** item viewer (one item per page with prev/next buttons).
- `/usar <item_name> @user` — decrements quantity and sends a random GIF from `gifs_items/`. Using `Bola mordaza` in a supergroup silences the target for 30 seconds; the bot needs permission to restrict members.
- **Callback patterns:** `inv_prev_<page>`, `inv_next_<page>`, `ver_item_<id>`
- **DB imports:** `get_items`, `get_campo_item`, `get_id_item`, `get_campo_usuario`, `insert_user`, `normalizar_nombre`, `get_cantidad_item_inventario`, `update_cantidad`, `delete_item_user`

#### `handlers/starting_menu.py`
- **Exports:** `start`, `menu_callback`
- `/start` in private → 4-button menu (commands, shop, inventory, profile)
- **Callback patterns:** `ver_comandos`, `abrir_tienda`, `ver_inventario`, `perfil`
- Unregistered users told to `/ver` first.

#### `handlers/theme_juegosYcasino.py`
- **Exports:** `apostar`, `aceptar`, `cancelar_apuesta`, `detectar_dado`, `jugar`, `robar`
- **Restricted to** `theme_juegosYcasino` topic in each community.
- **Betting:** `apostar` creates bet → `aceptar` within 60s → both roll dice → winner gets pot. In-memory `active_bets` dict.
- **Dice handler (`detectar_dado`):** Checks for active COMBAT first (calls `get_combate_activo` from battles.py), then falls back to betting dice.
- **Jugar:** Solo dice roll. Win 50 PiPesos on 1 or 6. Max 5/day (in-memory).
- **Robar:** `/robar @user`. 1/3 success. Steals 1-100 PiPesos. Max 3/day (in-memory).
- **DB imports:** `normalizar_nombre`, `get_campo_usuario`, `insert_user`, `dar_puntos`, `quitar_puntos`, `update_perfil`

#### `handlers/battles.py`
- **Exports:** `lucha`, `aceptar_lucha`, `ataque`
- **Also used by theme_juegosYcasino.py:** `get_combate_activo`, `actualizar_combate`, `terminar_combate`
- **Challenge:** `/lucha @user <amount>` → deducts bet from both → 60s timeout for acceptance.
- **Accept:** `/aceptarlucha` → creates DB combat record with 20 HP each.
- **Combat:** Turn-based dice in DMs. Damage = dice value. First to 0 HP loses. Winner gets 2× bet.
- **Local DB functions** use raw SQL with `_get_connection()` / `_put_connection()` directly against `combates_tb`.
- **In-memory:** `pending_challenges` dict for unaccepted challenges.

#### `handlers/rewards.py`
- **Exports:** `manejar_imagenes`
- Routes media messages to reward sub-handlers based on topic:
  - **Presentaciones:** 5 PiPesos for first image (one-time per user, tracked in-memory)
  - **Multimedia:** Every 3 images → 10 PiPesos (2 min inactivity reset)
  - **NSFW:** Every 5 images → 16 PiPesos (2 min inactivity reset)
- **All counters are in-memory** — lost on restart.
- **DB imports:** `normalizar_nombre`, `get_campo_usuario`, `insert_user`, `dar_puntos`

#### `handlers/welcoming.py`
- **Exports:** `nuevo_usuario`, `mensaje_de_presentaciones`
- **CURRENTLY DISABLED** — both handlers are commented out in main.py group 4.
- On new member → welcome message → 30 min timer → notify admins if no presentation.

#### `handlers/roles.py`
- **Exports:** `asignar_rol`, `ver_rol`
- `/AsignarRol @user [1|2|3]` — BotMaster only (checks `check_permission(sender.id, 3)`)
- `/MiRol` — shows caller's role
- **DB imports:** `get_id_user`, `get_user_role`, `set_user_role`, `check_permission`

---

## 7. Configuration Details

Defined in `src/config/settings.py`.

### Communities (`COMUNIDADES`)

List of dicts. Each has `id_comunidad`, `nombre`, and `temas` (topic IDs).

| Community | ID | Status |
|---|---|---|
| Kiusama | `-1003290179217` | Active (main) |
| Rub | `-1002983018006` | Active (secondary) |
| Ara | `-1003397946543` | **BLOCKED** (in `bloquear_comunidad`) |

### Topic IDs

Each community has named topics. Key ones:
- `theme_juegosYcasino` — Games/casino commands restricted here
- `theme_rincon` — Punishment corner
- `theme_NSFW`, `theme_Exhibicionismo`, `theme_multimedia` — Reward topics
- `theme_questions`, `theme_presentaciones` — Onboarding

Access via: `obtener_temas_por_comunidad(community_id)` → returns dict or `None`.

### Admin Lists (`ADMINS`)

List of dicts with `id_comunidad` and `admins` (set of user IDs). Per-community admin sets.

Access via: `obtener_admins_comunidad(community_id)` → returns set or empty set.

### DOM System (`DOMS`)

Dict mapping DOM user ID → list of submissive user IDs. Used by punishment system (`/castigar`, `/perdonar`).

```python
DOMS = {
    dom_id: [sub_id_1, sub_id_2, ...],
    ...
}
```

### Helper Functions
- `obtener_temas_por_comunidad(community_id)` → `dict | None`
- `obtener_admins_comunidad(community_id)` → `set`

---

## 8. main.py — Entry Point

### Startup Sequence
```python
create_database()              # No-op for PostgreSQL
create_tables()                # CREATE TABLE IF NOT EXISTS (6 tables)
seed_items()                   # Insert 6 default items (idempotent)
init_botmaster_roles(BOTMASTER_IDS)  # Ensure BotMaster roles
restart_all_combats()          # Cancel stale combats
```

### Defined in main.py (not in handlers/)
- `cargar_castigados()` / `guardar_castigados(data)` — JSON file I/O for punishment list
- `get_theme_id(update, context)` — `/id` command, shows chat_id and thread_id
- `saludar(update, context)` — `/saludar` command, festive welcome
- `castigar(update, context)` — `/castigar @user`, DOM-only punishment
- `filtro_castigo(update, context)` — Deletes messages from punished users outside punishment corner
- `perdonar(update, context)` — `/perdonar @user`, DOM-only release
- `bloquear_comunidad(update, context)` — Blocks community `-1003397946543`, raises `ApplicationHandlerStop()`

---

## 9. Conventions & Patterns

### Import Pattern
```python
from src.config import BOT_TOKEN, COMUNIDADES, ...
from src.database.database import function_name
```
Always import from `src.database.database` (not from `src.database`). The `__init__.py` re-exports are available but direct imports are the convention used throughout.

### User Registration Pattern
Many handlers auto-register users on first interaction:
```python
if get_campo_usuario(user.id, "id_user") is None:
    insert_user(user.id, 0, user.username, normalizar_nombre(user.first_name, user.last_name))
```

### Target User Resolution
Use `get_receptor(update, context, args_length)` from `handlers/general.py`:
- Returns user object (with `.id` and `.username`) on success
- Returns `None` if no target found
- Returns `False` if @ symbol missing from mention

### Admin Check
```python
from handlers.general import verificar_admin
if not await verificar_admin(sender.id, update):
    # deny
```
Checks internal role system (role >= 2) first, then falls back to config ADMINS list.

### BotMaster Check
```python
from src.database.database import check_permission
if not check_permission(user.id, 3):
    # deny
```

### Private-Chat-Only Commands
Tienda and inventario are private-chat only. In groups they show a deep-link button:
```python
bot_user = BOT_USERNAME or context.bot.username
deep_link = f"https://t.me/{bot_user}?start=menu"
```

### In-Memory State (Lost on Restart)
- `active_bets` (theme_juegosYcasino.py) — Active betting sessions
- `pending_challenges` (battles.py) — Unaccepted combat challenges
- `plays_today` / `robs_today` (theme_juegosYcasino.py) — Daily limits
- Reward counters (rewards.py) — Image counting for auto-rewards
- Presentation tracking (rewards.py) — One-time presentation rewards

### Database Query Style
- PostgreSQL: `%s` placeholders (NOT `?`)
- All queries use parameterized values (no f-strings in SQL)
- Pattern: `_get_connection()` → `try` → `cursor.execute()` → `conn.commit()` → `except` → `conn.rollback()` → `finally` → `_put_connection(conn)`
- Column whitelisting: `get_campo_usuario` and `update_perfil` validate column names against a hardcoded set

### Adding a New Command
1. Create handler function in the appropriate `handlers/*.py` file
2. Import it in `main.py`
3. Register with `app.add_handler(CommandHandler("command_name", handler_func), group=N)`
4. Choose the appropriate group number (see Section 6)

### Adding a New Item
Add to the `items` list in `seed_items()` in `src/database/database.py`. Provide:
- `nombre` (unique, used as lookup key)
- `precio` (integer, in PiPesos)
- `imagen` (path relative to project root, e.g., `img_items/name.png`)
- `descripcion` (text shown in shop)
- `mensaje` (template with `{sender_username}` and `{receptor_username}` placeholders)

Also add:
- Item image in `img_items/`
- GIF folder in `gifs_items/<item_name_lowercase>/` with `.gif` files

### Adding a New Database Table
1. Add `CREATE TABLE IF NOT EXISTS` in `create_tables()` in `src/database/database.py`
2. Add CRUD functions following the existing pattern
3. Export new functions in `src/database/__init__.py`

---

## 10. Dependencies

From `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| python-telegram-bot | 22.5 | Telegram bot framework |
| psycopg2-binary | 2.9.10 | PostgreSQL driver |
| python-dotenv | 1.0.0 | Load .env files |
| aiofiles | 24.1.0 | Async file operations |
| aiohttp | 3.12.15 | Async HTTP (PTB dependency) |
| pydantic | 2.11.10 | Data validation |
| APScheduler | 3.10.4 | Task scheduling |
| requests | 2.32.5 | HTTP requests |

---

## 11. Known Limitations & Technical Debt

1. **In-memory state is lost on restart** — betting, combat challenges, daily limits, reward counters all use Python dicts. Consider Redis or DB-backed state for resilience.
2. **`src/handlers/` is unused** — all handlers live in root `handlers/`. The `src/handlers/` directory is a leftover.
3. **`handlers/_init_.py`** has wrong filename (underscore instead of double-underscore). Should be `__init__.py`. Currently empty and unused.
4. **Welcome system is disabled** — handlers exist in `welcoming.py` but are commented out in main.py.
5. **`perfiles_tb.rol`** (TEXT) vs `roles_tb.role` (INTEGER) — two different "role" concepts. Profile rol is user-facing (BDSM role label); roles_tb.role is the internal permission system.
6. **Combat dice handling** lives in `theme_juegosYcasino.py::detectar_dado()`, not in `battles.py`. This is because PTB only allows one handler per filter type per group.
7. **`castigados.json`** is file-based punishment state — persists across restarts but is on ephemeral filesystem on Railway. Consider migrating to PostgreSQL.
8. **Encoding gotcha:** `requirements.txt` must be ASCII/UTF-8. PowerShell `Set-Content` defaults to UTF-16 on Windows — always specify `-Encoding ASCII` or `-Encoding UTF8`.
