# Deployment Guide (Koyeb + Supabase)

This guide will help you deploy **Modo** for free using Koyeb (App Hosting) and Supabase (Database).

## 1. Prepare Supabase (Database)
1.  **Sign up** at [supabase.com](https://supabase.com/).
2.  **Create a new project**.
3.  Go to **Project Settings** -> **Database**.
4.  Find the **Connection String** (URI).
5.  Select **"Transaction Mode (Session)"** (port 5432) or standard connection.
6.  **Copy the URI**. It will look like:
    `postgresql://postgres.yourproject:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres`
    *   *Note: Replace `[YOUR-PASSWORD]` with the password you created in step 2.*

## 2. Prepare Koyeb (App Hosting)
1.  **Sign up** at [koyeb.com](https://koyeb.com/).
2.  **Create a new App**.
3.  **Source:** Select **GitHub** and choose this repository (`modo`).
4.  **Builder:** Select **Buildpack** (it will auto-detect Python).
5.  **Environment Variables:** Add the following keys:
    *   `SECRET_KEY`: Generate a random string (e.g., `openssl rand -hex 32`).
    *   `SQLALCHEMY_DATABASE_URI`: Paste your **Supabase Connection String** here.
        *   *Important:* Ensure it starts with `postgresql://`. If Supabase gives you `postgres://`, rename it to `postgresql://` for compatibility with SQLAlchemy.
6.  **Build Command:** Override the default build command if necessary to include migrations:
    `pip install -r requirements.txt && flask db upgrade`
7.  **Run Command:**
    `gunicorn app:app`
8.  **Deploy!**

## 3. Verify
*   Visit your Koyeb URL (e.g., `https://modo-xyz.koyeb.app`).
*   The database will be automatically created (`flask db upgrade` runs during build/deploy).
*   **Troubleshooting:** Check the "Runtime Logs" in the Koyeb dashboard if the app fails to start.

---

## Local Development vs. Production
*   **Locally:** Uses `sqlite:///db.sqlite3` (file-based).
*   **Production:** Uses `postgresql://...` (Supabase).
*   The app automatically detects which one to use based on the `SQLALCHEMY_DATABASE_URI` environment variable.
