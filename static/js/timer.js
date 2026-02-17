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
            task: document.getElementById('global-timer-task'),
            subtask: document.getElementById('global-timer-subtask')
        },
        page: {
            display: document.getElementById('page-timer-display'),
            start: document.getElementById('page-timer-start'),
            pause: document.getElementById('page-timer-pause'),
            reset: document.getElementById('page-timer-reset'),
            skip: document.getElementById('page-timer-skip'),
            end: document.getElementById('page-timer-end'),
            task: document.getElementById('page-timer-task'),
            subtask: document.getElementById('page-timer-subtask')
        }
    };

    let timerInterval;
    let secondsLeft = null;
    let isRunning = false;
    let currentTaskId = null;
    let currentSubtaskId = null;
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
        const savedSubtask = localStorage.getItem('timerSubtask');
        const savedSeconds = localStorage.getItem('timerSecondsLeft');
        const savedMode = localStorage.getItem('timerMode');
        const settings = window.userSettings || { focusDuration: 25, breakDuration: 5 };

        if (savedTask) {
            currentTaskId = savedTask;
            updateTaskSelects(currentTaskId);
            currentSubtaskId = savedSubtask;
            fetchSubtasks(currentTaskId, currentSubtaskId);
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
        } else if (savedSeconds !== null && savedSeconds !== undefined && savedSeconds !== "") {
             secondsLeft = parseInt(savedSeconds);
             isRunning = false;
        } else {
             // Defaults if nothing saved
             if (currentMode === 'break') secondsLeft = settings.breakDuration * 60;
             else secondsLeft = settings.focusDuration * 60;
        }
        
        // Final fallback if something went wrong
        if (secondsLeft === null || isNaN(secondsLeft)) {
            secondsLeft = settings.focusDuration * 60;
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
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
            body: JSON.stringify({
                status: status,
                mode: currentMode,
                seconds_left: secondsLeft,
                task_id: currentTaskId
            })
        }).then(res => {
            if (res.status === 401) {
                // User logged out elsewhere
                localStorage.removeItem('timerStatus');
                localStorage.removeItem('timerEnd');
                document.title = 'Modo - Productivity Manager';
                return;
            }
            lastSync = Date.now();
        }).catch(() => {});
    }

    function updateTaskSelects(value, triggerSubtaskFetch = false) {
        if (elements.global.task) elements.global.task.value = value;
        if (elements.page.task) elements.page.task.value = value;
        if (triggerSubtaskFetch) {
            fetchSubtasks(value, currentSubtaskId);
        }
    }

    function fetchSubtasks(taskId, selectedSubtaskId = null) {
        if (!taskId) {
            updateSubtaskSelects([]);
            return;
        }

        fetch(`/api/tasks/${taskId}/subtasks`)
            .then(r => r.json())
            .then(subtasks => {
                updateSubtaskSelects(subtasks, selectedSubtaskId);
            });
    }

    function updateSubtaskSelects(subtasks, selectedSubtaskId = null) {
        const selects = [elements.global.subtask, elements.page.subtask];
        const incompleteSubtasks = subtasks.filter(s => !s.is_completed);

        // If current subtask is done or no longer in list, clear it
        if (selectedSubtaskId) {
            const stillActive = incompleteSubtasks.find(s => s.id == selectedSubtaskId);
            if (!stillActive) {
                selectedSubtaskId = null;
                currentSubtaskId = null;
                localStorage.setItem('timerSubtask', '');
            }
        }

        // Auto-select first incomplete subtask if autoSelectPriority is on
        const settings = window.userSettings || {};
        if (!selectedSubtaskId && incompleteSubtasks.length > 0 && settings.autoSelectPriority) {
            selectedSubtaskId = incompleteSubtasks[0].id;
            currentSubtaskId = selectedSubtaskId;
            localStorage.setItem('timerSubtask', currentSubtaskId);
        }

        selects.forEach(select => {
            if (!select) return;
            
            if (incompleteSubtasks.length === 0) {
                select.classList.add('hidden');
                select.innerHTML = '<option value="">[NO_SUBTASK]</option>';
                return;
            }

            select.classList.remove('hidden');
            let html = '<option value="">[SELECT_SUBTASK]</option>';
            incompleteSubtasks.forEach(s => {
                html += `<option value="${s.id}" ${s.id == selectedSubtaskId ? 'selected' : ''}>- ${s.title}</option>`;
            });
            select.innerHTML = html;
        });
    }

    function updateUI() {
        // Display Time
        const minutes = Math.floor(secondsLeft / 60);
        const seconds = secondsLeft % 60;
        const text = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        if (elements.global.display) elements.global.display.textContent = text;
        if (elements.page.display) elements.page.display.textContent = text.padStart(5, '0');

        const minDisplay = document.getElementById('min-timer-display');
        if (minDisplay) minDisplay.textContent = text;

        // Update Global Status Label
        const statusDisplay = document.getElementById('global-timer-status');
        const statusDot = document.getElementById('global-timer-dot');
        if (statusDisplay) {
            statusDisplay.textContent = isRunning ? (currentMode === 'break' ? 'BREAK' : 'FOCUS') : 'PAUSED';
        }
        if (statusDot) {
            statusDot.className = isRunning ? 'w-1.5 h-1.5 bg-accent animate-pulse' : 'w-1.5 h-1.5 bg-gray-500';
        }

        // Update Subtask Display in Bubble
        const subtaskDisplayContainer = document.getElementById('global-active-process');
        const subtaskDisplayText = document.getElementById('global-active-subtask-display');
        if (subtaskDisplayContainer && subtaskDisplayText) {
            if (currentSubtaskId && elements.global.subtask && elements.global.subtask.selectedIndex > 0) {
                subtaskDisplayContainer.classList.remove('hidden');
                subtaskDisplayText.textContent = elements.global.subtask.options[elements.global.subtask.selectedIndex].text.replace('- ', '');
        

            } else {
                subtaskDisplayContainer.classList.add('hidden');
            }
        }

        // Dispatch Tick Event for Dot Matrix
        const settings = window.userSettings || { focusDuration: 25, breakDuration: 5 };
        const total = currentMode === 'break' ? settings.breakDuration * 60 : settings.focusDuration * 60;
        const percent = ((total - secondsLeft) / total) * 100;
        
        document.body.dispatchEvent(new CustomEvent('timerTick', { 
            detail: { percent: percent, minutes, seconds } 
        }));

        // External API (Data Attributes for PreMiD/Extensions)
        document.body.dataset.modoStatus = isRunning ? 'running' : 'paused';
        document.body.dataset.modoMode = currentMode;
        document.body.dataset.modoTime = text;
        
        let taskTitle = "No Task Selected";
        if (elements.global.task && elements.global.task.selectedIndex >= 0) {
            const selected = elements.global.task.options[elements.global.task.selectedIndex];
            if (selected && selected.value) {
                taskTitle = selected.text;
                // Add subtask if selected
                if (elements.global.subtask && elements.global.subtask.selectedIndex > 0) {
                    const selectedSub = elements.global.subtask.options[elements.global.subtask.selectedIndex];
                    taskTitle += ` (${selectedSub.text.replace('- ', '')})`;
                }
            }
        }
                // Update Pomodoro Progress Blocks in Bubble
        const pomProgressContainer = document.getElementById('global-pom-progress');
        if (pomProgressContainer && elements.global.task) {
            const selectedOption = elements.global.task.options[elements.global.task.selectedIndex];
            if (selectedOption && selectedOption.value) {
                const est = parseInt(selectedOption.dataset.est || 1);
                const done = parseInt(selectedOption.dataset.done || 0);
                const count = Math.max(est, done);
                
                let html = '';
                for (let i = 0; i < count; i++) {
                    const isActive = i < done;
                    html += `<div class="w-2 h-2 border ${isActive ? 'bg-accent border-accent' : 'opacity-20 border-accent'}"></div>`;
                }
                pomProgressContainer.innerHTML = html;
            } else {
                pomProgressContainer.innerHTML = '';
            }
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
            const fullDuration = (window.userSettings && window.userSettings.focusDuration ? window.userSettings.focusDuration : 25) * 60;
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
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
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
                window.modoAlert('Please select a task first!', 'VALIDATION_ERROR');
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
        
        checkDrift(); // Sync immediately

        timerInterval = setInterval(() => {
            if (!isRunning) return;

            checkDrift();
            
            if (secondsLeft <= 0) {
                completeTimer();
            } else {
                updateUI();
            }
        }, 1000);
    }

    function checkDrift() {
        const savedEnd = localStorage.getItem('timerEnd');
        if (savedEnd && isRunning) {
            const now = Date.now();
            const remaining = Math.ceil((parseInt(savedEnd) - now) / 1000);
            // Use calculated remaining time to correct any drift
            if (remaining >= 0) {
                secondsLeft = remaining;
            } else {
                secondsLeft = 0;
            }
        } else if (isRunning) {
            // Fallback if no end time but running
            secondsLeft--;
        }
        if (secondsLeft < 0) secondsLeft = 0;
        localStorage.setItem('timerSecondsLeft', secondsLeft);
    }

    function pauseTimer(notifyServer = true) {
        const settings = window.userSettings || {};
        
        if (notifyServer && settings.syncMode && settings.activeRoomId) {
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'pause' })
            });
        }
        
        if (timerInterval) clearInterval(timerInterval);
        isRunning = false;
        localStorage.setItem('timerStatus', 'paused');
        localStorage.removeItem('timerEnd');
        updateUI();
        syncPresence();
    }

        function endSession() {
        const settings = window.userSettings || { focusDuration: 25, breakDuration: 5 };
        const totalSeconds = settings.focusDuration * 60;
        const elapsedSeconds = totalSeconds - secondsLeft;
        
        if (elapsedSeconds < 60) {
             // We can still use alert for very minor errors or just ignore
             window.modoNotify('Insufficient elapsed time (< 1m)', 'warning');
             resetTimer();
             return;
        }

        const minutesLogged = Math.floor(elapsedSeconds / 60);
        
        // Open the custom Alpine modal instead of confirm()
        const bodyData = document.body.__x.$data;
        if (bodyData) {
            bodyData.endSessionModal.mins = minutesLogged;
            bodyData.endSessionModal.taskId = currentTaskId;
            bodyData.endSessionModal.open = true;
        }
    }

    window.finalizeEndSession = function(confirm) {
        const bodyData = document.body.__x.$data;
        if (!bodyData) return;
        
        const minutesLogged = bodyData.endSessionModal.mins;
        const taskId = bodyData.endSessionModal.taskId;
        bodyData.endSessionModal.open = false;

        if (confirm) {
             pauseTimer(); 
             const settings = window.userSettings || {};
             const payload = { minutes: minutesLogged, task_id: taskId };
             if (settings.syncMode && settings.activeRoomId) payload.room_id = settings.activeRoomId;

             fetch('/api/log_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
                body: JSON.stringify(payload)
            }).then(() => {
                window.modoNotify('Session logged!', 'success');
                resetTimer();
            });
        }
    }

    function resetTimer() {
        const settings = window.userSettings || {};
        
        if (settings.syncMode && settings.activeRoomId) {
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
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
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
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
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
                body: JSON.stringify(payload)
            }).then(() => {
                // Refresh task lists in case task was completed
                document.body.dispatchEvent(new CustomEvent('tasksChanged'));
                
                // Sync: Tell server to switch to break
                if (settings.syncMode && settings.activeRoomId) {
                     fetch('/api/study/control', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
                        body: JSON.stringify({ room_id: settings.activeRoomId, action: 'skip' })
                    });
                }

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
                    window.modoNotify('Focus Complete! Starting Break...', 'info');
                } else {
                    window.modoNotify('Focus Complete! Take a break?', 'warning');
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

            // Sync: Tell server to switch to focus
            if (settings.syncMode && settings.activeRoomId) {
                     fetch('/api/study/control', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
                        body: JSON.stringify({ room_id: settings.activeRoomId, action: 'skip' })
                    });
            }

            // If auto-select priority is on, find the next task now
            if (settings.autoSelectPriority) {
                fetch('/api/next_priority_task')
                    .then(res => res.json())
                    .then(data => {
                        if (data && data.id) {
                            currentTaskId = data.id.toString();
                            localStorage.setItem('timerTask', currentTaskId);
                            updateTaskSelects(currentTaskId);
                            fetchSubtasks(currentTaskId, null); // This will auto-select the first subtask
                        }
                        // Wait a tiny bit for the subtask fetch to complete before finishing break
                        setTimeout(() => finishBreak(settings), 200);
                    });
            } else {
                finishBreak(settings);
            }
        }
    }

    function finishBreak(settings) {
        updateUI();
        document.body.dispatchEvent(new CustomEvent('tasksChanged'));
        if (settings.autoStartFocus) {
            startTimer(true);
             window.modoNotify('Break Over! Starting Focus...', 'info');
        } else {
             window.modoNotify('Break Over! Ready to focus?', 'warning');
        }
    }

    function attachListeners() {
        // HTMX task update listener
        document.body.addEventListener('tasksChanged', () => {
            fetch('/api/timer_tasks')
                .then(r => r.text())
                .then(html => {
                    const selects = [elements.global.task, elements.page.task];
                    selects.forEach(select => {
                        if (select) {
                            const currentVal = select.value;
                            select.innerHTML = html;
                            select.value = currentVal; // Restore selection if it still exists
                        }
                    });
                    if (currentTaskId) {
                        fetchSubtasks(currentTaskId, currentSubtaskId);
                    }
                });
        });

        // Global
        if (elements.global.start) elements.global.start.addEventListener('click', () => startTimer(true));
        if (elements.global.pause) elements.global.pause.addEventListener('click', pauseTimer);
        if (elements.global.reset) elements.global.reset.addEventListener('click', resetTimer);
        if (elements.global.skip) elements.global.skip.addEventListener('click', skipBreak);
        if (elements.global.end) elements.global.end.addEventListener('click', endSession);
        if (elements.global.task) elements.global.task.addEventListener('change', (e) => { currentTaskId = e.target.value; currentSubtaskId = null; localStorage.setItem('timerSubtask', ''); updateTaskSelects(currentTaskId, true); localStorage.setItem('timerTask', currentTaskId); updateUI(); });

        const globalSubtask = document.getElementById('global-timer-subtask');
        if (globalSubtask) {
            globalSubtask.addEventListener('change', (e) => {
                currentSubtaskId = e.target.value;
                localStorage.setItem('timerSubtask', currentSubtaskId);
                const pageSubtask = document.getElementById('page-timer-subtask');
                if (pageSubtask) pageSubtask.value = currentSubtaskId;
                updateUI();
            });
        }

        // Page
        if (elements.page.start) elements.page.start.addEventListener('click', () => startTimer(true));
        if (elements.page.pause) elements.page.pause.addEventListener('click', pauseTimer);
        if (elements.page.reset) elements.page.reset.addEventListener('click', resetTimer);
        if (elements.page.skip) elements.page.skip.addEventListener('click', skipBreak);
        if (elements.page.end) elements.page.end.addEventListener('click', endSession);
        if (elements.page.task) elements.page.task.addEventListener('change', (e) => { currentTaskId = e.target.value; currentSubtaskId = null; localStorage.setItem('timerSubtask', ''); updateTaskSelects(currentTaskId, true); localStorage.setItem('timerTask', currentTaskId); updateUI(); });

        const pageSubtask = document.getElementById('page-timer-subtask');
        if (pageSubtask) {
            pageSubtask.addEventListener('change', (e) => {
                currentSubtaskId = e.target.value;
                localStorage.setItem('timerSubtask', currentSubtaskId);
                const globalSubtask = document.getElementById('global-timer-subtask');
                if (globalSubtask) globalSubtask.value = currentSubtaskId;
                updateUI();
            });
        }
    }


    window.addEventListener('storage', (e) => {
        if (e.key === 'timerStatus' || e.key === 'timerEnd' || e.key === 'timerSecondsLeft' || e.key === 'timerMode') {
            loadState();
        }
    });

    init();

});