# GEMINI.md

## 🚀 Flask To-Do & Pomodoro Manager
A high-performance productivity web app built with **Flask**, **SQLAlchemy**, and **HTMX**.

---

## 🛠️ Feature Roadmap

### 1. Authentication & Security
* **Flask-Login:** Managed user sessions and protected routes.
* **Werkzeug:** Password hashing to ensure user data security.

### 2. Dynamic To-Dos (The "Core")
* **Task Model:** Title, Description, Hashtags, and Status.
* **Subtasks:** A nested relationship where tasks can be broken down into granular steps.
* **HTMX Integration:** Add, delete, and toggle tasks without a page refresh for an SPA-like feel.

### 3. Pomodoro & Tracking
* **JavaScript Timer:** A frontend-focused timer to ensure accuracy during navigation.
* **Session Logging:** Auto-save completed "Focus Blocks" to the database to track total productivity.

### 4. Dynamic Theming
* **CSS Variables:** Implementation of themes (e.g., Light, Dark, Retro, Cyberpunk) controlled via a `data-theme` attribute on the HTML body.
* **Persistence:** User theme preferences saved in the database.

### 5. Leaderboard
* **Global Ranking:** A ranking system based on `total_focus_minutes` logged via the Pomodoro timer.
* **Caching:** Use simple Flask caching for the leaderboard to save DB hits.

---

## 📂 Project Structure

/my_flask_app
├── app.py              # Main entry point & routes
├── models.py           # SQLAlchemy database schemas
├── auth.py             # Login/Signup logic
├── static/
│   ├── css/            # Tailwind/Custom CSS with themes
│   └── js/             # Pomodoro logic (timer.js)
├── templates/
│   ├── base.html       # Sidebar, Tabs, & Theme wrapper
│   ├── index.html      # To-do list view
│   ├── timer.html      # Pomodoro interface
│   └── leaderboard.html
├── requirements.txt    # Dependencies
└── .env                # Environment variables (Secret keys)

---

## 🌍 2026 Free Hosting Tips

Hosting has changed recently. Here are the best ways to host this app for free or "effectively free."

### **1. Render (Best All-Rounder)**
* **Why:** Easiest to use. Connect your GitHub, and it deploys automatically.
* **The Catch:** The free tier "spins down" after 15 minutes of inactivity. The first person to visit the site after a break will wait ~30 seconds for it to wake up.
* **Database:** Offers a free managed PostgreSQL instance (usually expires after 90 days, so keep backups!).

### **2. PythonAnywhere (Most Reliable for Flask)**
* **Why:** Specifically built for Python. The app stays "always-on" better than Render's free tier.
* **The Catch:** Free tier gives you a yourusername.pythonanywhere.com domain and limits outbound web requests to a whitelist of sites.
* **Database:** Provides a free MySQL instance.

### **3. Koyeb (High Performance)**
* **Why:** Extremely fast global edge network. They have a very generous "Nano" instance for free.
* **The Catch:** Uses a "MicroVM" approach; great for performance but slightly steeper learning curve than Render.

### **4. Supabase (For your Database)**
* **Pro Tip:** Don't host your database on the same platform as your app. Use **Supabase** for a "Free Forever" PostgreSQL tier. 
* **Connection:** In your Flask app, simply set your SQLALCHEMY_DATABASE_URI to your Supabase connection string.

---

## 🛠️ Quick-Start Commands
To get your environment ready locally:
1. python -m venv venv
2. source venv/bin/activate  # Windows: venv\Scripts\activate
3. pip install flask flask-sqlalchemy flask-login flask-migrate
4. pip freeze > requirements.txt

---

We are using:
- [-] Koyeb for App Hosting
- [-] Supabase for database Hosting

---

## 🛠️ Troubleshooting & Model Maintenance

### 1. Model Not Found (404 Errors)
If you encounter an error like `404 models/gemini-x.x-xxxx is not found`, it usually means the specific versioned model name has been retired or is not supported by the current API version.

**The Fix:**
*   Use the `-latest` aliases instead of specific version numbers.
    *   **Flash:** Use `gemini-flash-latest` instead of `gemini-1.5-flash`.
    *   **Pro:** Use `gemini-pro-latest` instead of `gemini-1.5-pro`.
*   Ensure **Preview Features** are enabled in your configuration:
    *   In `~/.gemini/settings.json`, set `"previewFeatures": true`.
    *   In `~/.config/gemini-cli.toml`, ensure the `model` is set to a `-latest` alias.

### 2. API Version Discrepancies
The CLI currently defaults to the `v1beta` API version. If a model is not found, verify its availability for `v1beta` using:
```bash
python3 -c "import google.generativeai as genai; [print(m.name) for m in genai.list_models()]"
```
Always prefer model names that appear in this list.

### 3. Timer Reset & Early Termination
If the timer resets on reload or the 'Terminate Early' button fails to open the confirmation modal:

*   **State Recovery (Zero-Flicker):** The timer state is now recovered via an **inline script** in `base.html` that reads `localStorage` before the page fully renders. This prevents the default duration (e.g., 25:00) from flickering on refresh.
*   **Clock Calibration:** We use a `clockOffset` (Server UTC vs. Browser Local) to ensure that countdowns remain accurate even if the production server's clock drifts from the user's device.
*   **Alpine.js Data Access:** When accessing Alpine.js data from plain JavaScript (like in `timer.js` or global functions), always use `document.body.__x.$data` instead of just `document.body.__x`. This ensures you are interacting with the reactive data object.
