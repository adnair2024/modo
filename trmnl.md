# Project: Modo (Productivity App)
**Stack:** Python / Flask / Supabase (Postgres) / Northflank
**Refactor Status:** React -> Vue.js


## 2. TRMNL Integration (Private Plugin)
- **Route:** `/api/trmnl`
- **Logic:** Fetches the top 5 incomplete tasks from `tasks` ordered by `created_at`.
- **Auth:** Uses a header-based `TRMNL-API-KEY` or query param for security.

## 3. Development Environment
- **Local OS:** Ubuntu (2012 MBP) / Windows 10
- **Editor:** Neovim / tmux
- **Hardware:** ZSA Voyager
- **Deployment:** Northflank (Autodeploy from Main)

## 4. Specific Instructions
- Use **SQLAlchemy** (or specify if using `supabase-py` client).
- Favor minimal, high-contrast JSON for the TRMNL feed
