document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const elements = {
        global: {
            display: document.getElementById('global-timer-display'),
            start: document.getElementById('global-timer-start'),
            pause: document.getElementById('global-timer-pause'),
            reset: document.getElementById('global-timer-reset'),
            skip: document.getElementById('global-timer-skip'),
            end: document.getElementById('global-timer-end'),
            task: document.getElementById('global-timer-task')
        },
        page: {
            display: document.getElementById('page-timer-display'),
            start: document.getElementById('page-timer-start'),
            pause: document.getElementById('page-timer-pause'),
            reset: document.getElementById('page-timer-reset'),
            skip: document.getElementById('page-timer-skip'),
            end: document.getElementById('page-timer-end'),
            task: document.getElementById('page-timer-task')
        }
    };

    let timerInterval;
    let secondsLeft = 25 * 60;
    let isRunning = false;
    let currentTaskId = null;
    let currentMode = 'focus'; // 'focus' or 'break'

    function init() {
        loadState();
        attachListeners();
        setInterval(checkExternalUpdates, 1000);
    }

    function loadState() {
        const savedEnd = localStorage.getItem('timerEnd');
        const savedStatus = localStorage.getItem('timerStatus');
        const savedTask = localStorage.getItem('timerTask');
        const savedSeconds = localStorage.getItem('timerSecondsLeft');
        const savedMode = localStorage.getItem('timerMode');
        const settings = window.userSettings || { focusDuration: 25, breakDuration: 5 };

        if (savedTask) {
            currentTaskId = savedTask;
            updateTaskSelects(currentTaskId);
        }
        
        if (savedMode) {
            currentMode = savedMode;
        }

        if (savedStatus === 'running' && savedEnd) {
            const now = Date.now();
            const remaining = Math.ceil((parseInt(savedEnd) - now) / 1000);
            
            if (remaining > 0) {
                secondsLeft = remaining;
                isRunning = true;
                startInterval(); 
            } else {
                secondsLeft = 0;
                isRunning = false;
                localStorage.setItem('timerStatus', 'paused');
            }
        } else if (savedSeconds) {
             secondsLeft = parseInt(savedSeconds);
             isRunning = false;
        } else {
             // Defaults if nothing saved
             if (currentMode === 'break') secondsLeft = settings.breakDuration * 60;
             else secondsLeft = settings.focusDuration * 60;
        }
        
        // Force sync duration if in sync mode and not running (to override any local stale state or defaults)
        if (settings.syncMode && !isRunning && !savedSeconds) {
             if (currentMode === 'break') secondsLeft = settings.breakDuration * 60;
             else secondsLeft = settings.focusDuration * 60;
        }

        updateUI();
    }

    function checkExternalUpdates() {
        const settings = window.userSettings || {};
        const now = Date.now();
        
        // 1. Sync Presence (Push my status)
        if (!lastSync || now - lastSync > 5000) {
            syncPresence();
        }
        
        // 2. Sync FROM Room (Pull shared status)
        // If we are in a sync room (settings.activeRoomId should be set in base.html)
        if (settings.syncMode && settings.activeRoomId) {
             if (!lastRoomSync || now - lastRoomSync > 2000) {
                syncWithRoom(settings.activeRoomId);
             }
        }
    }
    
    let lastSync = 0;
    let lastRoomSync = 0;
    
    function syncWithRoom(roomId) {
        fetch(`/api/study/state/${roomId}`)
            .then(r => r.json())
            .then(data => {
                lastRoomSync = Date.now();
                
                // Update local state to match server
                if (data.mode !== currentMode) {
                    currentMode = data.mode;
                    localStorage.setItem('timerMode', currentMode);
                }
                
                // Update Tasks
                const myTaskEl = document.getElementById('sync-my-task');
                const otherTaskEl = document.getElementById('sync-other-task');
                if (myTaskEl) myTaskEl.textContent = data.my_task || 'No Task';
                if (otherTaskEl) otherTaskEl.textContent = data.other_task || 'No Task';
                
                // If server is running, we must be running
                if (data.is_running) {
                    if (!isRunning) {
                        isRunning = true;
                        localStorage.setItem('timerStatus', 'running');
                        startInterval(); 
                    }
                    // Sync time roughly
                    if (Math.abs(secondsLeft - data.seconds_remaining) > 2) {
                        secondsLeft = data.seconds_remaining;
                    }
                } else {
                    // Server paused/stopped
                    if (isRunning) {
                        pauseTimer(false); // Don't notify server, just pause local
                    }
                    // Sync time exactly
                    if (secondsLeft !== data.seconds_remaining) {
                        secondsLeft = data.seconds_remaining;
                        updateUI();
                    }
                }
                updateUI();
            });
    }
    
    function syncPresence() {
        const status = isRunning ? 'running' : 'paused'; 
        
        fetch('/api/sync_presence', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                status: status,
                mode: currentMode,
                seconds_left: secondsLeft,
                task_id: currentTaskId
            })
        }).then(() => {
            lastSync = Date.now();
        }).catch(() => {});
    }

    function updateTaskSelects(value) {
        if (elements.global.task) elements.global.task.value = value;
        if (elements.page.task) elements.page.task.value = value;
    }

    function updateUI() {
        // Display Time
        const minutes = Math.floor(secondsLeft / 60);
        const seconds = secondsLeft % 60;
        const text = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        if (elements.global.display) elements.global.display.textContent = text;
        if (elements.page.display) elements.page.display.textContent = text.padStart(5, '0');

        // External API (Data Attributes for PreMiD/Extensions)
        document.body.dataset.modoStatus = isRunning ? 'running' : 'paused';
        document.body.dataset.modoMode = currentMode;
        document.body.dataset.modoTime = text;
        
        let taskTitle = "No Task Selected";
        if (elements.global.task && elements.global.task.selectedIndex >= 0) {
            const selected = elements.global.task.options[elements.global.task.selectedIndex];
            if (selected && selected.value) taskTitle = selected.text;
        }
        document.body.dataset.modoTask = taskTitle;

        // Color/Mode Indication (Optional visual cue)
        const isBreak = currentMode === 'break';
        if (elements.global.display) elements.global.display.style.color = isBreak ? '#10B981' : ''; // Green for break
        if (elements.page.display) elements.page.display.classList.toggle('text-green-500', isBreak);

        // Title
        const modeIcon = isBreak ? '☕' : '🍅';
        document.title = isRunning ? `(${text}) ${modeIcon} Modo` : 'Modo - Productivity Manager';

        // Buttons
        const showPause = isRunning;
        toggleButtons(elements.global, showPause);
        toggleButtons(elements.page, showPause);
    }

    function toggleButtons(els, showPause) {
        if (els.start && els.pause) {
            // Update Start Button Text based on Mode if paused
            if (!showPause) {
                els.start.textContent = currentMode === 'break' ? 'Start Break' : 'Start Focus';
                els.start.classList.remove('hidden');
                els.pause.classList.add('hidden');
            } else {
                els.start.classList.add('hidden');
                els.pause.classList.remove('hidden');
            }
        }
        
        // Show/Hide Skip Break
        if (els.skip) {
            if (currentMode === 'break') {
                els.skip.classList.remove('hidden');
            } else {
                els.skip.classList.add('hidden');
            }
        }

        // Show/Hide End Session (Only in Focus mode and if started)
        if (els.end) {
            const settings = window.userSettings || { focusDuration: 25 };
            const fullDuration = settings.focusDuration * 60;
            // Show if in focus mode AND (running OR (paused AND some time elapsed))
            if (currentMode === 'focus' && (isRunning || secondsLeft < fullDuration)) {
                els.end.classList.remove('hidden');
            } else {
                els.end.classList.add('hidden');
            }
        }

        // Only disable task selection during BREAK, allow it during FOCUS even if running
        if (els.task) {
            els.task.disabled = (currentMode === 'break'); 
        }
    }

    function startTimer(setNewEndTime = true) {
        const settings = window.userSettings || {};
        
        // SYNC OVERRIDE
        if (settings.syncMode && settings.activeRoomId) {
            fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'start' })
            });
            // Don't start locally; wait for poll
            return; 
        }

        if (currentMode === 'focus') {
             if (!currentTaskId) {
                if (elements.global.task && elements.global.task.value) currentTaskId = elements.global.task.value;
                else if (elements.page.task && elements.page.task.value) currentTaskId = elements.page.task.value;
            }

            if (!currentTaskId) {
                alert('Please select a task first!');
                return;
            }
            updateTaskSelects(currentTaskId);
            localStorage.setItem('timerTask', currentTaskId);
        }

        isRunning = true;
        localStorage.setItem('timerStatus', 'running');
        localStorage.setItem('timerMode', currentMode);
        
        if (setNewEndTime) {
            const now = Date.now();
            const endTime = now + (secondsLeft * 1000);
            localStorage.setItem('timerEnd', endTime);
        }

        updateUI();
        startInterval();
        syncPresence();
    }

    function startInterval() {
        if (timerInterval) clearInterval(timerInterval);
        
        timerInterval = setInterval(() => {
            if (!isRunning) return;

            secondsLeft--;
            if (secondsLeft < 0) secondsLeft = 0;
            
            localStorage.setItem('timerSecondsLeft', secondsLeft);
            updateUI();

            if (secondsLeft <= 0) {
                completeTimer();
            }
        }, 1000);
    }

    function pauseTimer(notifyServer = true) {
        const settings = window.userSettings || {};
        
        if (notifyServer && settings.syncMode && settings.activeRoomId) {
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'pause' })
            });
            return;
        }
        
        if (timerInterval) clearInterval(timerInterval);
        isRunning = false;
        localStorage.setItem('timerStatus', 'paused');
        localStorage.removeItem('timerEnd');
        updateUI();
        syncPresence();
    }

    function endSession() {
        pauseTimer(); // Local pause
        const settings = window.userSettings || { focusDuration: 25, breakDuration: 5 };
        const totalSeconds = settings.focusDuration * 60;
        const elapsedSeconds = totalSeconds - secondsLeft;
        
        if (elapsedSeconds <= 0) {
             resetTimer(); 
             return;
        }

        const minutesLogged = Math.max(1, Math.round(elapsedSeconds / 60));

        if (confirm(`End session and log ${minutesLogged} minutes?`)) {
             const payload = { minutes: minutesLogged, task_id: currentTaskId };
             if (settings.syncMode && settings.activeRoomId) payload.room_id = settings.activeRoomId;

             fetch('/api/log_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(() => {
                alert('Session logged!');
                resetTimer();
            });
        }
    }

    function resetTimer() {
        const settings = window.userSettings || {};
        
        if (settings.syncMode && settings.activeRoomId) {
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'reset' })
            });
            return;
        }

        pauseTimer(false);
        // Reset to default of current mode
        secondsLeft = currentMode === 'break' ? settings.breakDuration * 60 : settings.focusDuration * 60;
        localStorage.removeItem('timerSecondsLeft');
        updateUI();
    }
    
    function skipBreak() {
        const settings = window.userSettings || {};
        
        if (settings.syncMode && settings.activeRoomId) {
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'skip' })
            });
            return;
        }
        
        pauseTimer(false);
        currentMode = 'focus';
        secondsLeft = settings.focusDuration * 60;
        localStorage.setItem('timerMode', currentMode);
        localStorage.removeItem('timerSecondsLeft');
        updateUI();
    }

    function completeTimer() {
        pauseTimer();
        const settings = window.userSettings || { focusDuration: 25, breakDuration: 5 };
        
        if (currentMode === 'focus') {
            // Log Session
            const payload = { minutes: settings.focusDuration, task_id: currentTaskId };
            if (settings.syncMode && settings.activeRoomId) payload.room_id = settings.activeRoomId;

            fetch('/api/log_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(() => {
                // Switch to Break
                currentMode = 'break';
                secondsLeft = settings.breakDuration * 60;
                localStorage.setItem('timerMode', currentMode);
                localStorage.removeItem('timerSecondsLeft'); 
                
                // If auto-select priority is on, find the next task for AFTER the break
                if (settings.autoSelectPriority) {
                    fetch('/api/next_priority_task')
                        .then(res => res.json())
                        .then(data => {
                            if (data.id) {
                                currentTaskId = data.id.toString();
                                localStorage.setItem('timerTask', currentTaskId);
                                updateTaskSelects(currentTaskId);
                            }
                        });
                }

                updateUI();

                if (settings.autoStartBreak) {
                    startTimer(true);
                    alert('Focus Complete! Starting Break...');
                } else {
                    alert('Focus Complete! Take a break?');
                }
            });
        } else {
            // Break Complete
            const settings = window.userSettings || { focusDuration: 25, breakDuration: 5 };
            
            // Switch to Focus
            currentMode = 'focus';
            secondsLeft = settings.focusDuration * 60;
            localStorage.setItem('timerMode', currentMode);
            localStorage.removeItem('timerSecondsLeft');

            // If auto-select priority is on, find the next task now
            if (settings.autoSelectPriority) {
                fetch('/api/next_priority_task')
                    .then(res => res.json())
                    .then(data => {
                        if (data.id) {
                            currentTaskId = data.id.toString();
                            localStorage.setItem('timerTask', currentTaskId);
                            updateTaskSelects(currentTaskId);
                        }
                        finishBreak(settings);
                    });
            } else {
                finishBreak(settings);
            }
        }
    }

    function finishBreak(settings) {
        updateUI();
        if (settings.autoStartFocus) {
            startTimer(true);
             alert('Break Over! Starting Focus...');
        } else {
             alert('Break Over! Ready to focus?');
        }
    }

    function attachListeners() {
        // Global
        if (elements.global.start) elements.global.start.addEventListener('click', () => startTimer(true));
        if (elements.global.pause) elements.global.pause.addEventListener('click', pauseTimer);
        if (elements.global.reset) elements.global.reset.addEventListener('click', resetTimer);
        if (elements.global.skip) elements.global.skip.addEventListener('click', skipBreak);
        if (elements.global.end) elements.global.end.addEventListener('click', endSession);
        if (elements.global.task) elements.global.task.addEventListener('change', (e) => {
            currentTaskId = e.target.value;
            updateTaskSelects(currentTaskId);
            localStorage.setItem('timerTask', currentTaskId);
        });

        // Page
        if (elements.page.start) elements.page.start.addEventListener('click', () => startTimer(true));
        if (elements.page.pause) elements.page.pause.addEventListener('click', pauseTimer);
        if (elements.page.reset) elements.page.reset.addEventListener('click', resetTimer);
        if (elements.page.skip) elements.page.skip.addEventListener('click', skipBreak);
        if (elements.page.end) elements.page.end.addEventListener('click', endSession);
        if (elements.page.task) elements.page.task.addEventListener('change', (e) => {
            currentTaskId = e.target.value;
            updateTaskSelects(currentTaskId);
            localStorage.setItem('timerTask', currentTaskId);
        });
    }

    init();

});