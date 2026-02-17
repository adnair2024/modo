# Production Finalization TODO

## 1. Features & Logic
- [x] **Leaderboard Caching:** Implement caching for the `/leaderboard` route to reduce DB load as mentioned in the roadmap.
- [x] **Subtasks Implementation:** 
    - [x] Add backend routes for adding/toggling/deleting subtasks.
    - [x] Update `task_item.html` to display and manage subtasks via HTMX.
- [x] **Genesis AI:** Ensure `GOOGLE_API_KEY` is properly handled in the production environment.

## 2. Security & Reliability
- [x] **CSRF Protection:** Enable global CSRF protection for all `POST/PUT/DELETE` requests.
- [x] **Error Pages:** Create custom `404` and `500` templates styled with the Digital Noir theme.
- [x] **Session Security:** Set `SESSION_COOKIE_SECURE=True` and `REMEMBER_COOKIE_HTTPONLY=True` for production HTTPS.
- [x] **Input Validation:** Audit all forms for strict data validation (e.g., max lengths on titles/descriptions).

## 3. Performance
- [x] **Throttling `last_seen`:** Throttling the `update_last_seen` commit logic in `app.py` (currently commits on every single request).
- [x] **Achievement Syncing:** Optimize `sync_achievements.py`. Running a full scan of all users on every container restart will become slow as the user base grows.
- [x] **Database Indexing:** Ensure foreign keys and frequently filtered columns (like `FocusSession.date`) are properly indexed for PostgreSQL.

## 4. Admin & Monitoring
- [x] **Admin Dashboard:** Add more comprehensive stats (e.g., total system focus hours, growth charts).
- [x] **Logging:** Replace `print` statements with a proper Python `logging` configuration for production tracking.

## 5. Deployment
- [x] **Environment Audit:** Ensure `SECRET_KEY` and `SQLALCHEMY_DATABASE_URI` are never hardcoded and always pulled from environment variables.
- [x] **Static Files:** Ensure `gunicorn` or a reverse proxy (like Nginx/Northflank's edge) is handling static files efficiently.
