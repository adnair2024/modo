# Deployment Guide (Northflank + Supabase)

This guide will help you deploy **Modo** for free (using trial/free tiers) or cheaply using **Northflank** (App Hosting) and **Supabase** (Database).

## 1. Prepare Supabase (Database)
1.  **Sign up** at [supabase.com](https://supabase.com/).
2.  **Create a new project**.
3.  Go to **Project Settings** -> **Database**.
4.  Find the **Connection String** (URI).
5.  Select **"Transaction Mode (Session)"** (port 5432).
6.  **Copy the URI**. It will look like:
    `postgresql://postgres.yourproject:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres`
    *   *Note: Replace `[YOUR-PASSWORD]` with the password you created in step 2.*

## 2. Prepare Northflank (App Hosting)
1.  **Sign up** at [northflank.com](https://northflank.com/).
2.  **Create a New Service**:
    *   Select **Combined Service** (Build + Deployment).
    *   **Repository:** Link your GitHub account and select the `modo` repository.
    *   **Branch:** `main` (or `master`).
    *   **Build Type:** Select **Dockerfile** (The project now includes one).
3.  **Environment Variables**:
    *   Go to the **Environment** section (or "Runtime Environment" during creation).
    *   Add `SECRET_KEY`: Generate a random string.
    *   Add `SQLALCHEMY_DATABASE_URI`: Paste your **Supabase Connection String**.
        *   *Important:* Ensure it starts with `postgresql://`. If Supabase gives you `postgres://`, rename it to `postgresql://` for compatibility with SQLAlchemy.
4.  **Networking / Ports**:
    *   Ensure the **Port** is set to `8000` (HTTP).
    *   Northflank should detect the `EXPOSE 8000` in the Dockerfile, but verify this.
5.  **Create Service**: Click to build and deploy.

## 3. Verify
*   Wait for the build to complete and the container to start.
*   Northflank will provide a public URL (e.g., `https://modo-xyz.northflank.app`).
*   **Migrations:** The `Dockerfile` includes a script (`docker-entrypoint.sh`) that automatically runs `flask db upgrade` every time the app starts, so your database tables will be created automatically.

---

## Local Development vs. Production
*   **Locally:** Uses `sqlite:///db.sqlite3` (file-based).
*   **Production:** Uses `postgresql://...` (Supabase).
*   The app automatically detects which one to use based on the `SQLALCHEMY_DATABASE_URI` environment variable.