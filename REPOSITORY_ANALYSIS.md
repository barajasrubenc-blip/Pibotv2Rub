# PiBot 2.0 — Complete Repository Analysis

**Last Updated:** April 26, 2026  
**Current Version:** 2.1.0  
**Status:** Production (Railway deployment)

---

## 1. Executive Summary

**PiBot** is a sophisticated Telegram bot for BDSM community management built on **python-telegram-bot 22.5** with **PostgreSQL** backend. It features a virtual economy system (PiPesos), gamification, item shop, turn-based combat, punishment mechanics, and multi-community support. The bot is deployed on **Railway** with automatic GitHub-triggered deployments.

### Key Stats
- **Language:** Python 3.11+
- **Framework:** python-telegram-bot (PTB) 22.5
- **Database:** PostgreSQL with connection pooling
- **Deployment:** Railway (auto-deploy on `main` branch push)
- **Supported Communities:** 2 (Kiusama, Rub) + configurable future additions
- **Total Commands:** 22 user-facing + 3 admin commands

---

## 2. High-Level Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram Network                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │     python-telegram-bot 22.5         │
        │      (PTB Application.builder)       │
        └──────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
    ┌─────────────────┐          ┌──────────────────────┐
    │  main.py        │          │  handlers/           │
    │  - Entry point  │          │  - 9 handler modules │
    │  - Registration │          │  - ~800 LOC each     │
    └─────────────────┘          └──────────────────────┘
        │                                   │
        ├─────────────────┬─────────────────┤
        ▼                 ▼                 ▼
   ┌─────────┐    ┌──────────────┐  ┌────────────┐
   │ Config  │    │   Database   │  │  Handlers  │
   │ module  │    │   Operations │  │  (grouped) │
   └─────────┘    └──────────────┘  └────────────┘
        │                 │                │
        ▼                 ▼                ▼
   src/config/    src/database/      handlers/
   - settings.py  - database.py      - general.py
   - COMUNIDADES  - 6 tables         - tienda.py
   - DOMS         - CRUD ops         - inventario.py
   - BOTMASTER    - Helpers          - battles.py
                                     - etc.
                                     
   ┌─────────────────────────────────────────┐
   │         PostgreSQL (Railway)            │
   │                                         │
   │  - usuarios_tb (balances)               │
   │  - items_tb (catalog)                   │
   │  - items_usuarios_tb (inventory)        │
   │  - perfiles_tb (user profiles)          │
   │  - combates_tb (combat records)         │
   │  - roles_tb (permissions: 1/2/3)        │
   └─────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Framework** | python-telegram-bot 22.5 | Telegram bot interaction, polling |
| **Async Runtime** | aiohttp 3.12.15 | Async HTTP requests |
| **Database Driver** | psycopg2-binary 2.9.10 | PostgreSQL connection pooling |
| **Config Management** | python-dotenv 1.0.0 | Environment variable loading |
| **Data Validation** | pydantic 2.11.10 | Data validation (optional) |
| **Task Scheduling** | APScheduler 3.10.4 | Scheduled tasks (framework included) |
| **HTTP Requests** | requests 2.32.5 | General HTTP operations |
| **File Operations** | aiofiles 24.1.0 | Async file I/O |

---

## 3. How the Bot Works — Execution Flow

### 3.1 Startup Sequence

```
1. main.py runs
   │
   ├─ Load environment variables (.env)
   │  ├─ BOT_TOKEN (required)
   │  ├─ DATABASE_URL (required)
   │  ├─ BOT_USERNAME (required, for deep links)
   │  └─ BOTMASTER_IDS (required, comma-separated)
   │
   ├─ Initialize database:
   │  ├─ create_database() [no-op for PostgreSQL]
   │  ├─ create_tables() [CREATE TABLE IF NOT EXISTS × 6]
   │  ├─ seed_items() [insert 6 default items if missing]
   │  ├─ init_botmaster_roles(BOTMASTER_IDS) [set role=3 for bootstrap users]
   │  └─ restart_all_combats() [cancel stale combat records]
   │
   ├─ Create PTB Application
   │  └─ app = Application.builder().token(BOT_TOKEN).build()
   │
   ├─ Register handlers in priority order (groups -2 to 6)
   │  └─ [See section 3.2]
   │
   └─ Start polling
      └─ app.run_polling(drop_pending_updates=True)
```

### 3.2 Handler Priority System

PTB processes handlers by **group number** (lower = higher priority). Once a handler succeeds, later groups still run unless the handler raises `ApplicationHandlerStop()`.

| Group | Purpose | Handlers | Key Behavior |
|-------|---------|----------|---|
| **-2** | Auto-register | `auto_registrar` → MessageHandler(ALL) | Silent. Creates user on first message if missing. Never blocks. |
| **-1** | Community blocking | `bloquear_comunidad` → MessageHandler(ALL) | Can raise `ApplicationHandlerStop()` to block entire community |
| **0** | Core commands | `/start`, `/castigar`, `/perdonar` | Punishment system, menu initialization |
| **1** | Games & betting | `/apostar`, `/aceptar`, `/cancelar`, `/robar`, `/jugar`, `/usar`, Dice handler | In-memory state tracking. Daily limits. |
| **2** | Economy & general | `/tienda`, `/inventario`, `/ver`, `/dar`, `/quitar`, `/regalar`, `/lucha`, `/ataque`, `/AsignarRol`, `/MiRol` | Main gameplay commands |
| **3** | Auto-rewards | PHOTO\|VIDEO\|ANIMATION handler | Topic-based rewards (presentations, multimedia, NSFW) |
| **4** | Welcome (DISABLED) | NEW_CHAT_MEMBERS handler | Currently commented out in main.py |
| **5** | Inline buttons | CallbackQueryHandler (menu, shop, inventory) | Routes button clicks back to handlers |
| **6** | Punishment filter | `filtro_castigo` → MessageHandler(ALL) | Deletes punished user messages outside punishment corner |

### 3.3 Message Flow Example: `/dar 50 @user`

```
1. User sends message: "/dar 50 @user"
   │
2. Group -2: auto_registrar
   └─ Check if user exists → if not, create profile
   │
3. Group -1: bloquear_comunidad
   └─ Check if in blocked community (-1003397946543)
   │  └─ If yes, raise ApplicationHandlerStop() [STOP ALL]
   │
4. Group 2: CommandHandler("dar", dar)
   ├─ Extract arguments: cantidad=50, target_user=@user
   │
   ├─ Verify sender has balance ≥ 50
   │  ├─ YES: quitar_puntos(sender, 50) → dar_puntos(target, 50)
   │  │       → reply "✅ Transferencia exitosa"
   │  └─ NO:  reply "❌ Saldo insuficiente"
   │
   └─ Update database (commit)
```

### 3.4 Command Categories

#### Economy & Wallet
- **`/ver`** — Show my balance
- **`/dar <amount> @user`** — Transfer PiPesos
- **`/regalar <amount> @user`** — Gift (admin only)
- **`/quitar <amount>`** — Deduct (admin only)

#### Shop & Inventory
- **`/tienda`** — Open shop (private chat only, shows deep-link button in groups)
- **`/inventario`** — View my items (private chat only)
- **`/usar <item> @user`** — Use item on someone (decrements quantity, sends GIF)

#### Games & Gambling
- **`/apostar <amount>`** — Create bet → opponent has 60s to `/aceptar`
- **`/jugar`** — Solo dice roll (50 PiPesos on 1 or 6, max 5/day)
- **`/robar @user`** — Try to steal 1-100 PiPesos (1/3 success, max 3/day)

#### Combat System
- **`/lucha @user <amount>`** — Challenge to duel → opponent has 60s to `/aceptarlucha`
- **`/aceptarlucha`** — Accept challenge, both roll dice in DM, first to 0 HP loses
- **`/ataque`** — Roll dice during active combat (turn-based in DM)

#### Punishment System (DOM-only)
- **`/castigar @user`** — Confine submissive to punishment corner (topic)
- **`/perdonar @user`** — Release submissive from punishment

#### Admin & Config
- **`/AsignarRol @user [1|2|3]`** — Set role (BotMaster only)
- **`/MiRol`** — Check my role
- **`/Suerte @user [1|2|3]`** — Adjust robbery luck (BotMaster only)

#### Utility
- **`/start`** — Show main menu (private)
- **`/id`** — Show chat ID and topic thread ID
- **`/saludar`** — Festive greeting
- **`/NumAzar N1 N2`** — Random number between N1 and N2

---

## 4. Key Components & Modules

### 4.1 File Structure

```
PiBot2.0/
├── main.py                          # Entry point (350 lines)
├── requirements.txt                 # Dependencies (11 packages)
├── procfile                         # Railway start command
├── castigados.json                  # Runtime punishment list (created automatically)
├── .env                             # Local environment variables (gitignored)
│
├── src/                             # Core modules
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py              # Re-exports settings
│   │   └── settings.py              # (85 lines) Config: env vars, COMUNIDADES, DOMS, BOTMASTER_IDS
│   ├── database/
│   │   ├── __init__.py              # Re-exports all DB functions
│   │   └── database.py              # (600+ lines) PostgreSQL operations, CRUD, connection pool
│   └── utils/
│       ├── __init__.py
│       └── helpers.py               # Shared utilities (minimal)
│
├── handlers/                        # Command & event handlers
│   ├── _init_.py                    # Empty (filename typo: should be __init__.py)
│   ├── general.py                   # (250 lines) /ver, /dar, /regalar, /quitar, /NumAzar + helper functions
│   ├── starting_menu.py             # (80 lines) /start, menu navigation
│   ├── tienda.py                    # (180 lines) Shop with pagination
│   ├── inventario.py                # (200 lines) Inventory viewer + /usar command
│   ├── theme_juegosYcasino.py       # (350 lines) Betting, dice, /robar, /jugar
│   ├── battles.py                   # (250 lines) Combat system with DB integration
│   ├── rewards.py                   # (150 lines) Auto-rewards for media uploads
│   ├── welcoming.py                 # (100 lines) New member welcome (DISABLED)
│   └── roles.py                     # (80 lines) /AsignarRol, /MiRol, /Suerte
│
├── gifs_items/                      # GIF animations per item
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
├── img_items/                       # Item catalog images
│   ├── collar.png
│   ├── latigo.png
│   ├── fusta.png
│   ├── galleta.png
│   ├── bola_mordaza.png
│   └── sorpresa.jpg
│
├── docs/                            # Documentation (empty, legacy)
└── tests/                           # Tests directory (empty, for future)
```

### 4.2 Database Schema (6 Tables)

#### `usuarios_tb` — User Accounts
```sql
CREATE TABLE usuarios_tb (
    id_user BIGINT PRIMARY KEY,
    saldo INTEGER DEFAULT 0
);
```
**Purpose:** Core user accounts with balance tracking.

#### `items_tb` — Item Catalog (6 default items)
```sql
CREATE TABLE items_tb (
    id_item SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    precio INTEGER NOT NULL,
    imagen TEXT NOT NULL,  -- path to img_items/
    descripcion TEXT,
    mensaje TEXT            -- template: {sender_username}, {receptor_username}
);
```
**Default Items:**
| Name | Price | Image |
|------|-------|-------|
| Collar | 100 | img_items/collar.png |
| Latigo | 150 | img_items/latigo.png |
| Fusta | 120 | img_items/fusta.png |
| Galleta | 50 | img_items/galleta.png |
| Bola mordaza | 200 | img_items/bola_mordaza.png |
| Sorpresa | 300 | img_items/sorpresa.jpg |

#### `items_usuarios_tb` — Inventory (Many-to-Many)
```sql
CREATE TABLE items_usuarios_tb (
    id SERIAL PRIMARY KEY,
    id_user BIGINT NOT NULL FK usuarios_tb,
    id_item INTEGER NOT NULL FK items_tb,
    cantidad INTEGER NOT NULL DEFAULT 1,
    UNIQUE(id_user, id_item)
);
```
**Purpose:** Track what items each user owns and quantities.

#### `perfiles_tb` — User Profiles
```sql
CREATE TABLE perfiles_tb (
    id_user BIGINT PRIMARY KEY FK usuarios_tb,
    username TEXT UNIQUE,
    nombre TEXT NOT NULL,
    rol TEXT,               -- BDSM profile role (Dom, Sub, Switch, etc.)
    orientacion_sexual TEXT,
    genero TEXT,
    ubicacion TEXT,
    edad INTEGER
);
```
**⚠️ Important:** `perfiles_tb.rol` is for user's BDSM profile role, NOT permissions. Permissions use `roles_tb.role`.

#### `combates_tb` — Combat Records
```sql
CREATE TABLE combates_tb (
    id_combate SERIAL PRIMARY KEY,
    id_atacante BIGINT NOT NULL FK usuarios_tb,
    id_defensor BIGINT NOT NULL FK usuarios_tb,
    username_atacante TEXT NOT NULL,
    username_defensor TEXT NOT NULL,
    apuesta INTEGER NOT NULL DEFAULT 0,
    hp_atacante INTEGER NOT NULL DEFAULT 20,
    hp_defensor INTEGER NOT NULL DEFAULT 20,
    turno INTEGER NOT NULL DEFAULT 1,
    es_turno_atacante INTEGER NOT NULL DEFAULT 1,
    estado TEXT NOT NULL DEFAULT 'activo',
    ganador BIGINT FK usuarios_tb,
    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**Purpose:** Track ongoing and completed combats.

#### `roles_tb` — Permission Roles (3-Tier System)
```sql
CREATE TABLE roles_tb (
    id_user BIGINT PRIMARY KEY FK usuarios_tb,
    role INTEGER NOT NULL DEFAULT 1
    CHECK (role IN (1, 2, 3))
);
```
**Role values:**
- **1** = Usuario (regular user)
- **2** = Admin (can use `/regalar`, `/quitar`)
- **3** = BotMaster (can assign roles, full control)

### 4.3 Core Handler Modules

#### `handlers/general.py`
**Exports:** `ver`, `dar`, `quitar`, `regalar`, `numero_azar`, `userid`  
**Internal helpers:**
- `verificar_admin(user_id, update)` — Check role system (role ≥ 2) + fallback to ADMINS list
- `get_receptor(update, context, args_length)` — Resolve @mention or reply target
- `obtener_gif_aleatorio(item_name)` — Random GIF from `gifs_items/<item>/`

#### `handlers/tienda.py`
**Exports:** `tienda`, `tienda_callback`, `main_menu_markup()`, `mostrar_item()`  
**Features:**
- Private-chat-only (shows deep-link button in groups)
- Paginated product browser
- Purchase flow with balance validation
- Deep-link: `https://t.me/{BOT_USERNAME}?start=menu`
- **Callback patterns:** `producto_<id>`, `comprar_<id>`, `volver_catalogo`

#### `handlers/inventario.py`
**Exports:** `inventario`, `inventario_callback`, `usar`  
**Features:**
- One item per page with prev/next navigation
- `/usar <item> @user` — decrements qty, sends random GIF
- Looks for GIFs in `gifs_items/<item_name_lowercase>/`
- **Callback patterns:** `inv_prev_<page>`, `inv_next_<page>`, `ver_item_<id>`

#### `handlers/theme_juegosYcasino.py`
**Exports:** `apostar`, `aceptar`, `detectar_dado`, `cancelar_apuesta`, `jugar`, `robar`  
**Features:**
- **Betting:** In-memory `active_bets` dict, 60s timeout
- **Jugar:** Solo roll, win 50 PiPesos on 1 or 6, max 5/day (in-memory tracking)
- **Robar:** 1/3 success rate, steal 1-100 PiPesos, max 3/day
- **Dice handler:** Checks combat first (calls `get_combate_activo`), falls back to betting
- **⚠️ In-memory state lost on restart**

#### `handlers/battles.py`
**Exports:** `lucha`, `aceptar_lucha`, `ataque`  
**Also used by:** `theme_juegosYcasino.py` (calls `get_combate_activo`)  
**Features:**
- Challenge flow: `/lucha @user <bet>` → 60s timeout → `/aceptarlucha` → DM combat
- Turn-based: Damage = dice roll value, first to 0 HP loses
- Winner gets 2× bet
- **Database:** Uses raw SQL with `_get_connection()` / `_put_connection()` pool pattern
- **Pending challenges:** In-memory dict, lost on restart

#### `handlers/rewards.py`
**Exports:** `manejar_imagenes`  
**Features:**
- Topic-based auto-rewards:
  - **Presentaciones:** 5 PiPesos once per user (1-time)
  - **Multimedia:** 10 PiPesos per 3 images (2 min reset)
  - **NSFW:** 16 PiPesos per 5 images (2 min reset)
- **⚠️ Counters are in-memory, lost on restart**

#### `handlers/roles.py`
**Exports:** `asignar_rol`, `ver_rol`, `suerte`  
**Features:**
- `/AsignarRol @user [1|2|3]` — BotMaster only
- `/MiRol` — show caller's role
- `/Suerte @user [1|2|3]` — Adjust robbery luck multiplier

---

## 5. Configuration & Deployment

### 5.1 Environment Variables (Required)

All loaded from `.env` file or Railway environment:

| Variable | Source | Required | Example | Purpose |
|----------|--------|----------|---------|---------|
| `BOT_TOKEN` | @BotFather | ✅ Yes | `123456:ABC-DEF...` | Telegram bot authentication |
| `DATABASE_URL` | Railway auto | ✅ Yes | `postgresql://user:pass@host:5432/db` | PostgreSQL connection |
| `BOT_USERNAME` | Manual | ✅ Yes | `PiBotBotBotBot` | Bot username for deep links (NO @) |
| `BOTMASTER_IDS` | Manual | ✅ Yes | `123456789,987654321` | Comma-separated user IDs for role=3 |

**Loading Order:**
```python
from dotenv import load_dotenv
load_dotenv()  # Load from .env first

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")
```

### 5.2 Community Configuration

Defined in `src/config/settings.py`:

```python
COMUNIDADES = [
    {
        "id_comunidad": -1003290179217,  # Kiusama (main)
        "nombre": "Kiusama",
        "temas": {
            "theme_juegosYcasino": 528,
            "theme_rincon": 77167,  # Punishment corner
            "theme_NSFW": 2,
            "theme_multimedia": 688,
            "theme_presentaciones": TBD,
            # ... more topics
        }
    },
    {
        "id_comunidad": -1002983018006,  # Rub (secondary)
        "nombre": "Rub",
        "temas": { ... }
    }
]

# DOM (Dominant) → Submissives mapping
DOMS = {
    1370162159: [5661536115],
    1174798556: [7064982957, 7819911906, ...],
    # ...
}
```

### 5.3 Deployment on Railway

**Complete Deployment Checklist:**

```
1. Create Railway Account
   └─ Sign up with GitHub at https://railway.app

2. Create Project from GitHub
   ├─ New Project → Deploy from GitHub repo
   ├─ Select: aleisnthere31/Pibotv2
   └─ Railway auto-clones repo

3. Add PostgreSQL Database
   ├─ Click "+" → Database → Add PostgreSQL
   ├─ Railway creates instance + auto-sets DATABASE_URL
   └─ ✅ CRITICAL STEP — bot won't work without this

4. Configure Environment Variables
   ├─ Go to Service → Variables tab
   ├─ Add: BOT_TOKEN (from @BotFather)
   ├─ Add: BOT_USERNAME (your bot's username, NO @)
   ├─ Add: BOTMASTER_IDS (comma-separated user IDs)
   └─ DATABASE_URL (auto-set from step 3)

5. Set Start Command
   ├─ Go to Settings tab
   ├─ Find "Start Command"
   ├─ Enter: python main.py
   └─ (Procfile already has this)

6. Deploy
   ├─ Railway auto-deploys on push to main branch
   ├─ Check Logs tab for startup sequence:
   │  [INIT] Creating tables...
   │  [INIT] Seeding items...
   │  [INIT] Initializing BotMaster roles...
   │  🤖 PiBot iniciado...
   └─ Test: Send /start to bot on Telegram

7. Auto-Redeploy on Code Push
   └─ Any push to main → Railway redeploys automatically
```

**Logs should show:**
```
[INIT] Creating database if it doesn't exist...
[INIT] Creating tables...
[INIT] Seeding items catalog...
[INIT] Initializing BotMaster roles...
[INIT] Restarting active combats...
🤖 PiBot iniciado e listo para recibir mensajes...
```

### 5.4 Local Development Setup

```bash
# Clone repo
git clone https://github.com/aleisnthere31/Pibotv2.git
cd PiBot2.0

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
BOT_TOKEN=your_token_from_botfather
DATABASE_URL=postgresql://user:pass@localhost:5432/pibot_dev
BOT_USERNAME=YourBotUsername
BOTMASTER_IDS=your_telegram_id
EOF

# Run bot
python main.py
```

**Database Setup (PostgreSQL):**
```bash
# macOS (using Homebrew)
brew install postgresql
brew services start postgresql

# Create database
createdb pibot_dev

# Connect
psql pibot_dev
```

---

## 6. Key Architectural Decisions

### 6.1 Why PostgreSQL Over SQLite?

**Pros:**
- Persistent on Railway (survives restarts)
- Connection pooling for scalability
- Multi-process support (future)
- Better type system

**Legacy:** Migrated from SQLite in v2.1.0

### 6.2 In-Memory State & Limitations

**Lost on Restart:**
- `active_bets` (betting sessions) — recreated on next `/apostar`
- `pending_challenges` (combat challenges) — 60s timeout or restart
- Daily play limits (`plays_today`, `robs_today`) — reset on restart
- Reward counters (image counting) — resets
- Presentation tracking — resets

**Mitigation:** Consider Redis or PostgreSQL-backed state for resilience in future versions.

### 6.3 Handler Priority System

**Design:** Lower group numbers run first. PTB doesn't re-block on success (unlike other frameworks).

**Key Property:** A handler can raise `ApplicationHandlerStop()` to prevent all later groups (used for community blocking).

### 6.4 Admin System (Dual-Mode)

```python
# Check 1: Internal role system (priority)
if user.role >= 2:  # Admin or BotMaster
    authorized = True

# Check 2: Fallback to config list
elif user_id in config.ADMINS:
    authorized = True
```

**Flexibility:** Supports both DB-backed and config-based admins.

### 6.5 Two "Role" Concepts

⚠️ **Confusion Point:**

- **`roles_tb.role`** (INTEGER 1/2/3) = **Internal permissions** (User/Admin/BotMaster)
- **`perfiles_tb.rol`** (TEXT) = **User's BDSM profile role** (Dom/Sub/Switch)

These are unrelated systems.

---

## 7. Known Limitations & Technical Debt

| Issue | Impact | Mitigation |
|-------|--------|-----------|
| In-memory state lost on restart | Betting, combats, daily limits reset | Database-backed state in v3.0 |
| `src/handlers/` unused | Code confusion | Remove or clarify in docs |
| `handlers/_init_.py` typo | Minor | Rename to `__init__.py` |
| Welcome system disabled | Feature incomplete | Enable in config |
| Dice handler split across modules | Hard to maintain | Refactor to `handlers/dice.py` |
| `castigados.json` file-based | Ephemeral on Railway | Migrate to PostgreSQL |
| Encoding issues on Windows | CI/CD friction | Always use `-Encoding ASCII` with `Set-Content` |
| No unit tests | Regressions possible | Add test suite in `tests/` |

---

## 8. Dependencies Summary

| Package | Version | Size | Purpose |
|---------|---------|------|---------|
| python-telegram-bot | 22.5 | ~200KB | Telegram API wrapper |
| psycopg2-binary | 2.9.10 | ~10MB | PostgreSQL driver (binary) |
| python-dotenv | 1.0.0 | ~50KB | .env file loader |
| aiohttp | 3.12.15 | ~500KB | Async HTTP client |
| aiofiles | 24.1.0 | ~30KB | Async file I/O |
| pydantic | 2.11.10 | ~5MB | Data validation |
| APScheduler | 3.10.4 | ~200KB | Task scheduling |
| requests | 2.32.5 | ~100KB | Sync HTTP client |

**Total footprint:** ~16MB (mostly psycopg2 binary)

---

## 9. Version History

### v2.1.0 (April 17, 2026) — Current Production
- ✅ SQLite → PostgreSQL migration
- ✅ Internal role system (1/2/3)
- ✅ Deep-link bot username fix
- ✅ Handler refactoring
- ✅ DB init sequence (`seed_items`, `init_botmaster_roles`, `restart_combats`)
- ✅ `Agents.md` technical documentation

### v2.0.0 (March 13, 2026)
- ✅ Major refactoring: `src/` modular structure
- ✅ Configuration management (`src/config/settings.py`)
- ✅ Database layer refactor (`src/database/database.py`)
- ✅ Improved error handling
- ✅ Documentation created

---

## 10. Quick Reference

### Most Important Files

| File | Lines | Purpose | Read First? |
|------|-------|---------|-------------|
| [main.py](main.py) | 350 | Entry point, handler registration | ✅ Yes |
| [src/config/settings.py](src/config/settings.py) | 85 | Configuration, communities, DOMS | ✅ Yes |
| [src/database/database.py](src/database/database.py) | 600+ | All DB operations | ✅ Yes |
| [handlers/general.py](handlers/general.py) | 250 | Basic commands, helpers | ⚠️ Maybe |
| [handlers/tienda.py](handlers/tienda.py) | 180 | Shop system | |
| [handlers/battles.py](handlers/battles.py) | 250 | Combat system | |
| [Agents.md](Agents.md) | 800+ | Complete technical reference | ✅ Yes |

### Common Tasks

**Add a new command:**
1. Create handler function in appropriate `handlers/*.py`
2. Import in `main.py`
3. Register with `app.add_handler(CommandHandler(...), group=N)`

**Add a new item:**
1. Add to `items` list in `seed_items()` in `src/database/database.py`
2. Add image to `img_items/`
3. Add GIF folder to `gifs_items/<item_name_lowercase>/`

**Check bot logs on Railway:**
```
Railway Dashboard → Project → Service → Logs tab
```

**Reset all combats:**
Automatic on startup via `restart_all_combats()`

**Bootstrap BotMaster roles:**
Set `BOTMASTER_IDS` env var → runs `init_botmaster_roles()` at startup

---

## 11. Contact & Resources

- **Repository:** https://github.com/aleisnthere31/Pibotv2
- **Deployment:** Railway (https://railway.app)
- **Bot Framework Docs:** https://docs.python-telegram-bot.org
- **PostgreSQL:** https://www.postgresql.org
- **Telegram Bot API:** https://core.telegram.org/bots/api

---

**Document Generated:** April 26, 2026  
**Last Code Version:** v2.1.0  
**Status:** ✅ Production Ready
