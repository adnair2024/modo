# Modo 🍅

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
![HTMX](https://img.shields.io/badge/HTMX-%23336699.svg?style=for-the-badge&logo=htmx&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![CSS3](https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white)

**Modo** is a high-performance, aesthetically pleasing productivity application designed to help you manage tasks and maintain focus. It seamlessly blends a robust **To-Do List** with a customizable **Pomodoro Timer**, built using modern web technologies for a smooth, single-page application (SPA) feel.

---

## ✨ Key Features

### 📝 Dynamic Task Management
*   **Create & Organize:** Manage tasks with rich details—titles, descriptions, priorities, due dates, and tags.
*   **Subtasks:** Break down complex projects into actionable, granular steps.
*   **HTMX Powered:** Experience fluid interactions (add, edit, delete, toggle) without full page reloads.
*   **Smart Sorting:** Organize by priority or due date.

### ⏱️ Pomodoro Timer
*   **Focus & Break Modes:** Integrated timer with customizable durations for Focus sessions, Short Breaks, and Long Breaks.
*   **Productivity Tracking:** Automatically logs "Focus Blocks" to track your total productive time.
*   **Auto-Pilot:** Optional settings to auto-start breaks or focus sessions for a seamless flow.

### 🎨 Personalization
*   **Dynamic Theming:** Choose your vibe with built-in themes like **Light**, **Dark**, **Retro**, and **Cyberpunk**.
*   **Persistence:** Your theme and timer preferences are saved to your profile.

### 🏆 Gamification
*   **Leaderboard:** Compete globally based on total focus minutes logged.
*   **Statistics:** View your productivity history (Focus Sessions).

---

## 🛠️ Tech Stack

*   **Backend:** [Flask](https://flask.palletsprojects.com/) (Python)
*   **Database:** [SQLAlchemy](https://www.sqlalchemy.org/) (ORM), SQLite (Local), PostgreSQL (Production)
*   **Frontend:** HTML5, CSS3 (Custom + Utility classes), JavaScript
*   **Interactivity:** [HTMX](https://htmx.org/) (for dynamic, AJAX-like behavior)
*   **Authentication:** Flask-Login & Werkzeug Security

---

## 🚀 Getting Started

Follow these steps to get a local copy of **Modo** up and running.

### Prerequisites
*   Python 3.8+
*   Git

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/modo.git
    cd modo
    ```

2.  **Create a virtual environment:**
    ```bash
    # macOS/Linux
    python -m venv venv
    source venv/bin/activate

    # Windows
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize the database:**
    ```bash
    flask db upgrade
    ```

5.  **Run the application:**
    ```bash
    flask run
    # or
    python app.py
    ```

6.  **Access the app:**
    Open your browser and navigate to `http://127.0.0.1:5000`.

### 6. TRMNL Device Integration (E-Ink)
Modo supports high-contrast task syncing for the **TRMNL** e-ink display via a private plugin.
- **Endpoint:** `/api/trmnl`
- **Authentication:** Bearer Token (`TRMNL_API_KEY`)
- **Display Data:**
  - **Subject:** Current user's identity (e.g., "LOST").
  - **Task Queue:** The top 5 incomplete tasks.
  - **Metrics:** Pomodoro progress (e.g., "2/4 POMS") and priority level (LOW/MED/HIGH) for each task.
  - **Optimization:** Text is truncated to 40 characters for optimal e-ink legibility.

---

## 📂 Project Structure

```text
modo/
├── app.py              # Application factory & route definitions
├── models.py           # Database models (User, Task, Timer, etc.)
├── auth.py             # Authentication routes (Login/Signup)
├── static/
│   ├── css/            # Stylesheets (Theming engine)
│   └── js/             # Client-side logic (Timer, etc.)
├── templates/          # HTML Templates (Jinja2)
│   ├── base.html       # Layout wrapper
│   ├── partials/       # HTMX fragments
│   └── ...             # Page templates
├── migrations/         # Alembic database migrations
├── Dockerfile          # Containerization setup
└── DEPLOYMENT.md       # Detailed production deployment guide
```

---

## ☁️ Deployment

Modo is container-ready and includes a `Dockerfile` for easy deployment.

For a detailed guide on deploying for **free** using **Northflank** (App Hosting) and **Supabase** (PostgreSQL Database), please refer to:

👉 **[DEPLOYMENT.md](DEPLOYMENT.md)**

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the project
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.# Cache Bust Thu Feb  5 10:43:45 AM CST 2026
