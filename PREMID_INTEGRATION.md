# Building a PreMiD Presence for Modo

This guide details how to build a [PreMiD](https://premid.app/) extension (Presence) that integrates with Modo to show your current focus status, task, and time remaining on Discord.

Modo exposes its internal timer state via standard HTML5 `data-` attributes on the `<body>` tag, making it extremely easy to scrape and display.

---

## 📡 The Data API

Modo automatically updates the following attributes on the `<body>` element every second:

| Attribute | Possible Values | Description |
| :--- | :--- | :--- |
| `data-modo-status` | `running`, `paused` | The current state of the timer. |
| `data-modo-mode` | `focus`, `break` | Whether the user is working or taking a break. |
| `data-modo-time` | `MM:SS` (e.g., `24:59`) | The remaining time formatted as text. |
| `data-modo-task` | String (e.g., `Learn Python`) | The title of the currently selected task. |

### Example DOM State
```html
<body 
    data-modo-status="running" 
    data-modo-mode="focus" 
    data-modo-time="15:30" 
    data-modo-task="Refactor Database">
    ...
</body>
```

---

## 🛠️ Implementation Guide

### 1. Prerequisites
- Node.js installed.
- [PreMiD Development Tools](https://docs.premid.app/dev/getting-started).

### 2. File Structure
Create a new folder for your presence (e.g., `modo-presence`) with the following files:
```text
modo-presence/
├── manifest.json
└── presence.ts
```

### 3. manifest.json
Defines the metadata and which URL the presence triggers on.

```json
{
    "service": "Modo",
    "description": "Productivity and Pomodoro tracking for Modo.",
    "url": "regex:.*localhost:5000.*|.*koyeb.app.*",
    "version": "1.0.0",
    "logo": "https://raw.githubusercontent.com/ashwinnair/modo/main/static/favicon.svg",
    "author": {
        "name": "Your Name",
        "id": "YOUR_DISCORD_ID"
    }
}
```
*Note: Update the `url` regex to match your actual deployment domain.*

### 4. presence.ts
The core logic that reads the DOM and formats the Discord Rich Presence.

```typescript
import { Presence } from "premid";

const presence = new Presence({
    clientId: "YOUR_DISCORD_APP_ID" // Optional: Create an app in Discord Dev Portal for custom images
});

presence.on("UpdateData", async () => {
    const presenceData: any = {};

    // 1. Read Data from Modo DOM
    const status = document.body.getAttribute("data-modo-status");
    const mode = document.body.getAttribute("data-modo-mode"); // 'focus' or 'break'
    const timeStr = document.body.getAttribute("data-modo-time");
    const task = document.body.getAttribute("data-modo-task") || "No Task Selected";

    // 2. Logic
    if (status === "running" && timeStr) {
        // Calculate End Timestamp for Discord's native countdown
        const [mins, secs] = timeStr.split(":").map(Number);
        const remainingSeconds = (mins * 60) + secs;
        presenceData.endTimestamp = Date.now() + (remainingSeconds * 1000);

        // Details
        if (mode === "focus") {
            presenceData.details = "🍅 Focusing";
            presenceData.state = `Working on: ${task}`;
            presenceData.largeImageKey = "focus_icon_url"; // Or use a default asset key
            presenceData.largeImageText = "Focus Mode";
        } else {
            presenceData.details = "☕ Taking a Break";
            presenceData.state = "Recharging...";
            presenceData.largeImageKey = "break_icon_url";
            presenceData.largeImageText = "Break Mode";
        }
        
        presenceData.smallImageKey = "play";
        presenceData.smallImageText = "Timer Running";

    } else {
        // Paused or Idle
        presenceData.details = "Idling";
        presenceData.state = `Paused: ${task}`;
        presenceData.largeImageKey = "logo";
        presenceData.smallImageKey = "pause";
        presenceData.smallImageText = "Timer Paused";
    }

    return presenceData;
});
```

### 5. Assets (Optional)
If you create a custom Discord Application for `clientId`:
1.  Go to [Discord Developer Portal](https://discord.com/developers/applications).
2.  Create an application named "Modo".
3.  Upload assets in "Rich Presence" -> "Art Assets".
4.  Use the names of those assets (e.g., `focus_icon`, `break_icon`) in the `largeImageKey` fields above.

---

## 🧪 Testing

1.  Open PreMiD Store (Extension menu).
2.  Load your unpacked extension folder.
3.  Open Modo in your browser (`http://localhost:5000`).
4.  Start the timer.
5.  Check your Discord profile status!
