const presence = new Presence({
    clientId: "1330907080839958568" // You should ideally use your own Client ID from Discord Dev Portal
});

const timestamps = {};

presence.on("UpdateData", async () => {
    const dataset = document.body.dataset;
    const status = dataset.modoStatus; // 'running' | 'paused'
    const mode = dataset.modoMode;     // 'focus' | 'break'
    const timeText = dataset.modoTime; // 'MM:SS'
    const task = dataset.modoTask;

    // Default state if nothing is active
    let presenceData = {
        largeImageKey: "logo", 
        // Note: 'logo' key must exist in your Discord App Assets. 
        // For local dev, sometimes this defaults to the app icon if not found.
        details: "Idle",
        state: "Not timer active"
    };

    if (timeText) {
        const [mins, secs] = timeText.split(':').map(Number);
        const totalSeconds = (mins * 60) + secs;

        presenceData.details = task || "No Task Selected";
        presenceData.state = mode === 'break' ? "Taking a Break" : "Focusing";
        
        // Buttons to open the site
        presenceData.buttons = [
            { label: "Open Modo", url: "https://p01--modo--w87x9wdr7kmw.code.run/" }
        ];

        if (status === 'running') {
            // Calculate end timestamp
            if (!timestamps.end || Math.abs(timestamps.end - (Date.now() + totalSeconds * 1000)) > 2000) {
                 timestamps.end = Date.now() + (totalSeconds * 1000);
            }
            presenceData.endTimestamp = timestamps.end;
            presenceData.smallImageKey = "play"; // These keys need to exist in Discord Assets
            presenceData.smallImageText = "Running";
        } else {
            // Paused
            delete timestamps.end;
            presenceData.state += ` [Paused: ${timeText} left]`;
            presenceData.smallImageKey = "pause";
            presenceData.smallImageText = "Paused";
        }
    }

    presence.setActivity(presenceData);
});
