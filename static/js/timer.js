document.addEventListener('DOMContentLoaded', () => {
    const settings = window.userSettings || {};
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
    let currentMode = 'focus'; 

    function getBodyData() {
        if (window.Alpine && window.Alpine.$data) return window.Alpine.$data(document.body);
        if (document.body.__x && document.body.__x.$data) return document.body.__x.$data;
        if (document.body._x_dataStack) return document.body._x_dataStack[0];
        return null;
    }

    function init() {
        loadState();
        attachListeners();
        setInterval(checkExternalUpdates, 1000);
    }

    function loadState() {
        if (!localStorage.getItem('timerStatus') && settings.serverMode !== 'none' && settings.serverEnd) {
            localStorage.setItem('timerMode', settings.serverMode);
            localStorage.setItem('timerEnd', settings.serverEnd);
            localStorage.setItem('timerStatus', 'running');
        }

        const savedEnd = localStorage.getItem('timerEnd');
        const savedStatus = localStorage.getItem('timerStatus');
        const savedTask = localStorage.getItem('timerTask');
        const savedSubtask = localStorage.getItem('timerSubtask');
        const savedSeconds = localStorage.getItem('timerSecondsLeft');
        const savedMode = localStorage.getItem('timerMode');

        if (savedTask && savedTask !== 'null') {
            currentTaskId = savedTask;
            updateTaskSelects(currentTaskId);
            currentSubtaskId = savedSubtask;
            fetchSubtasks(currentTaskId, currentSubtaskId);
        }
        
        if (savedMode) currentMode = savedMode;

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
        } else if (savedSeconds && savedSeconds !== 'NaN' && savedSeconds !== 'null') {
             secondsLeft = parseInt(savedSeconds);
             isRunning = false;
        } else {
             secondsLeft = (currentMode === 'break' ? (settings.breakDuration || 5) : (settings.focusDuration || 25)) * 60;
        }
        
        if (isNaN(secondsLeft) || secondsLeft === null) {
            secondsLeft = (settings.focusDuration || 25) * 60;
        }

        updateUI();
    }

    function checkExternalUpdates() {
        const now = Date.now();
        if (!lastSync || now - lastSync > 5000) syncPresence();
        if (settings.syncMode && settings.activeRoomId) {
             if (!lastRoomSync || now - lastRoomSync > 2000) syncWithRoom(settings.activeRoomId);
        }
    }
    
    let lastSync = 0;
    let lastRoomSync = 0;
    
    function syncWithRoom(roomId) {
        fetch("/api/study/state/" + roomId)
            .then(r => r.json())
            .then(data => {
                lastRoomSync = Date.now();
                if (data.mode !== currentMode) {
                    currentMode = data.mode;
                    localStorage.setItem('timerMode', currentMode);
                }
                const myTaskEl = document.getElementById('sync-my-task');
                const otherTaskEl = document.getElementById('sync-other-task');
                if (myTaskEl) myTaskEl.textContent = data.my_task || 'No Task';
                if (otherTaskEl) otherTaskEl.textContent = data.other_task || 'No Task';
                if (data.is_running) {
                    if (!isRunning) {
                        isRunning = true;
                        localStorage.setItem('timerStatus', 'running');
                        startInterval(); 
                    }
                    if (Math.abs(secondsLeft - data.seconds_remaining) > 2) secondsLeft = data.seconds_remaining;
                } else {
                    if (isRunning) pauseTimer(false);
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
        const csrfEl = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfEl ? csrfEl.content : '';
        fetch('/api/sync_presence', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
            body: JSON.stringify({
                status: status,
                mode: currentMode,
                seconds_left: secondsLeft,
                task_id: currentTaskId
            })
        }).then(res => {
            if (res.status === 401) {
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
        if (triggerSubtaskFetch) fetchSubtasks(value, currentSubtaskId);
    }

    function fetchSubtasks(taskId, selectedSubtaskId = null) {
        if (!taskId || taskId === 'null') {
            updateSubtaskSelects([]);
            return;
        }
        fetch("/api/tasks/" + taskId + "/subtasks")
            .then(r => r.json())
            .then(subtasks => updateSubtaskSelects(subtasks, selectedSubtaskId));
    }

    function updateSubtaskSelects(subtasks, selectedSubtaskId = null) {
        const selects = [elements.global.subtask, elements.page.subtask];
        const incompleteSubtasks = (subtasks || []).filter(s => !s.is_completed);
        
        if (selectedSubtaskId) {
            const stillActive = incompleteSubtasks.find(s => s.id == selectedSubtaskId);
            if (!stillActive) {
                selectedSubtaskId = null;
                currentSubtaskId = null;
                localStorage.setItem('timerSubtask', '');
            }
        }
        if (!selectedSubtaskId && incompleteSubtasks.length > 0 && settings.autoSelectPriority) {
            selectedSubtaskId = incompleteSubtasks[0].id;
            currentSubtaskId = selectedSubtaskId;
            localStorage.setItem('timerSubtask', currentSubtaskId);
        }

        const container = document.getElementById('page-timer-subtask-container');
        if (container) {
            container.classList.toggle('hidden', incompleteSubtasks.length === 0);
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
                html += "<option value='" + s.id + "' " + (s.id == selectedSubtaskId ? 'selected' : '') + ">- " + s.title + "</option>";
            });
            select.innerHTML = html;
        });
    }

    function updateUI() {
        const minutes = Math.floor(secondsLeft / 60);
        const seconds = secondsLeft % 60;
        const text = minutes + ":" + seconds.toString().padStart(2, '0');
        if (elements.global.display) elements.global.display.textContent = text;
        if (elements.page.display) elements.page.display.textContent = text.padStart(5, '0');
        const minDisplay = document.getElementById('min-timer-display');
        if (minDisplay) minDisplay.textContent = text;

        const statusDisplay = document.getElementById('global-timer-status');
        const statusDot = document.getElementById('global-timer-dot');
        if (statusDisplay) statusDisplay.textContent = isRunning ? (currentMode === 'break' ? 'BREAK' : 'FOCUS') : 'PAUSED';
        if (statusDot) statusDot.className = isRunning ? 'w-1.5 h-1.5 bg-accent animate-pulse' : 'w-1.5 h-1.5 bg-gray-500';

        const subtaskDisplayContainer = document.getElementById('global-active-process');
        const subtaskDisplayText = document.getElementById('global-active-subtask-display');
        if (subtaskDisplayContainer && subtaskDisplayText) {
            if (currentSubtaskId && elements.global.subtask && elements.global.subtask.selectedIndex > 0) {
                const opt = elements.global.subtask.options[elements.global.subtask.selectedIndex];
                if (opt) {
                    subtaskDisplayContainer.classList.remove('hidden');
                    subtaskDisplayText.textContent = opt.text.replace('- ', '');
                }
            } else {
                subtaskDisplayContainer.classList.add('hidden');
            }
        }

        const total = ((currentMode === 'break' ? (settings.breakDuration || 5) : (settings.focusDuration || 25)) * 60) || 1500;
        const percent = ((total - secondsLeft) / total) * 100;
        document.body.dispatchEvent(new CustomEvent('timerTick', { detail: { percent: percent, minutes, seconds } }));

        document.body.dataset.modoStatus = isRunning ? 'running' : 'paused';
        document.body.dataset.modoMode = currentMode;
        document.body.dataset.modoTime = text;
        
        let taskTitle = 'No Task Selected';
        if (elements.global.task && elements.global.task.selectedIndex >= 0) {
            const selected = elements.global.task.options[elements.global.task.selectedIndex];
            if (selected && selected.value) {
                taskTitle = selected.text;
                if (elements.global.subtask && elements.global.subtask.selectedIndex > 0) {
                    const selectedSub = elements.global.subtask.options[elements.global.subtask.selectedIndex];
                    if (selectedSub) taskTitle += " (" + selectedSub.text.replace('- ', '') + ")";
                }
            }
        }
        const pomProgressContainer = document.getElementById('global-pom-progress');
        if (pomProgressContainer && elements.global.task) {
            const selectedOption = elements.global.task.options[elements.global.task.selectedIndex];
            if (selectedOption && selectedOption.value) {
                const est = parseInt(selectedOption.dataset.est || 1);
                const done = parseInt(selectedOption.dataset.done || 0);
                const count = Math.max(est, done);
                let html = '';
                for (let i = 0; i < count; i++) html += "<div class='w-2 h-2 border " + (i < done ? 'bg-accent border-accent' : 'opacity-20 border-accent') + "'></div>";
                pomProgressContainer.innerHTML = html;
            } else {
                pomProgressContainer.innerHTML = '';
            }
        }
        document.body.dataset.modoTask = taskTitle;
        const isBreak = currentMode === 'break';
        if (elements.global.display) elements.global.display.style.color = isBreak ? '#10B981' : '';
        if (elements.page.display) elements.page.display.classList.toggle('text-green-500', isBreak);
        document.title = isRunning ? "(" + text + ") " + (isBreak ? '☕' : '🍅') + " Modo" : 'Modo - Productivity Manager';

        toggleButtons(elements.global, isRunning);
        toggleButtons(elements.page, isRunning);
    }

    function toggleButtons(els, showPause) {
        if (els.start && els.pause) {
            if (!showPause) {
                els.start.textContent = currentMode === 'break' ? 'Start Break' : 'Start Focus';
                els.start.classList.remove('hidden');
                els.pause.classList.add('hidden');
            } else {
                els.start.classList.add('hidden');
                els.pause.classList.remove('hidden');
            }
        }
        if (els.skip) els.skip.classList.toggle('hidden', currentMode !== 'break');
        if (els.end) {
            const fullDuration = (settings.focusDuration || 25) * 60;
            els.end.classList.toggle('hidden', !(currentMode === 'focus' && (isRunning || secondsLeft < fullDuration)));
        }
        if (els.task) els.task.disabled = (currentMode === 'break'); 
    }

    function startTimer(setNewEndTime = true) {
        if (settings.syncMode && settings.activeRoomId) {
            const csrfEl = document.querySelector('meta[name="csrf-token"]');
            fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfEl ? csrfEl.content : ''},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'start' })
            });
            return; 
        }
        if (currentMode === 'focus' && !currentTaskId) {
            currentTaskId = (elements.page.task ? elements.page.task.value : '') || (elements.global.task ? elements.global.task.value : '');
            if (!currentTaskId || currentTaskId === 'null') {
                window.modoAlert('Please select a task first!', 'VALIDATION_ERROR');
                return;
            }
            updateTaskSelects(currentTaskId);
            localStorage.setItem('timerTask', currentTaskId);
        }
        isRunning = true;
        localStorage.setItem('timerStatus', 'running');
        localStorage.setItem('timerMode', currentMode);
        if (setNewEndTime) localStorage.setItem('timerEnd', Date.now() + (secondsLeft * 1000));
        updateUI();
        startInterval();
        syncPresence();
    }

    function startInterval() {
        if (timerInterval) clearInterval(timerInterval);
        checkDrift();
        timerInterval = setInterval(() => {
            if (!isRunning) return;
            checkDrift();
            if (secondsLeft <= 0) completeTimer(); else updateUI();
        }, 1000);
    }

    function checkDrift() {
        const savedEnd = localStorage.getItem('timerEnd');
        if (savedEnd && isRunning) {
            const remaining = Math.ceil((parseInt(savedEnd) - Date.now()) / 1000);
            secondsLeft = Math.max(0, remaining);
        } else if (isRunning) {
            secondsLeft--;
        }
        if (secondsLeft < 0) secondsLeft = 0;
        localStorage.setItem('timerSecondsLeft', secondsLeft);
    }

    function pauseTimer(notifyServer = true) {
        if (notifyServer && settings.syncMode && settings.activeRoomId) {
             const csrfEl = document.querySelector('meta[name="csrf-token"]');
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfEl ? csrfEl.content : ''},
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
        const elapsed = ((settings.focusDuration || 25) * 60) - secondsLeft;
        if (elapsed < 60) {
             window.modoNotify('Insufficient elapsed time (< 1m)', 'warning');
             resetTimer();
             return;
        }
        const bData = getBodyData();
        if (bData) {
            bData.endSessionModal.mins = Math.floor(elapsed / 60);
            bData.endSessionModal.taskId = currentTaskId;
            bData.endSessionModal.open = true;
        }
    }

    window.finalizeEndSession = function(confirm) {
        const bData = getBodyData();
        if (!bData) return;
        const minutesLogged = bData.endSessionModal.mins;
        const taskId = bData.endSessionModal.taskId;
        bData.endSessionModal.open = false;
        if (confirm) {
             pauseTimer(); 
             const csrfEl = document.querySelector('meta[name="csrf-token"]');
             fetch('/api/log_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfEl ? csrfEl.content : ''},
                body: JSON.stringify({ minutes: parseInt(minutesLogged), task_id: taskId, room_id: settings.activeRoomId })
            }).then(() => {
                window.modoNotify('Session logged!', 'success');
                resetTimer();
            });
        }
    }

    function resetTimer() {
        if (settings.syncMode && settings.activeRoomId) {
             const csrfEl = document.querySelector('meta[name="csrf-token"]');
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfEl ? csrfEl.content : ''},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'reset' })
            });
            return;
        }
        pauseTimer(false);
        secondsLeft = (currentMode === 'break' ? (settings.breakDuration || 5) : (settings.focusDuration || 25)) * 60;
        localStorage.removeItem('timerSecondsLeft');
        updateUI();
    }
    
    function skipBreak() {
        if (settings.syncMode && settings.activeRoomId) {
             const csrfEl = document.querySelector('meta[name="csrf-token"]');
             fetch('/api/study/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfEl ? csrfEl.content : ''},
                body: JSON.stringify({ room_id: settings.activeRoomId, action: 'skip' })
            });
            return;
        }
        pauseTimer(false);
        currentMode = 'focus';
        secondsLeft = (settings.focusDuration || 25) * 60;
        localStorage.setItem('timerMode', currentMode);
        localStorage.removeItem('timerSecondsLeft');
        updateUI();
    }

    function completeTimer() {
        pauseTimer();
        if (currentMode === 'focus') {
            const csrfEl = document.querySelector('meta[name="csrf-token"]');
            fetch('/api/log_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfEl ? csrfEl.content : ''},
                body: JSON.stringify({ minutes: parseInt(settings.focusDuration || 25), task_id: currentTaskId, room_id: settings.activeRoomId })
            }).then(() => {
                document.body.dispatchEvent(new CustomEvent('tasksChanged'));
                currentMode = 'break';
                secondsLeft = (settings.breakDuration || 5) * 60;
                localStorage.setItem('timerMode', currentMode);
                localStorage.removeItem('timerSecondsLeft'); 
                if (settings.autoSelectPriority) {
                    fetch('/api/next_priority_task').then(r => r.json()).then(data => {
                        if (data.id) { currentTaskId = data.id.toString(); localStorage.setItem('timerTask', currentTaskId); updateTaskSelects(currentTaskId); }
                    });
                }
                updateUI();
                if (settings.autoStartBreak) startTimer(true); else window.modoNotify('Focus Complete! Take a break?', 'warning');
            });
        } else {
            currentMode = 'focus';
            secondsLeft = (settings.focusDuration || 25) * 60;
            localStorage.setItem('timerMode', currentMode);
            localStorage.removeItem('timerSecondsLeft');
            if (settings.autoSelectPriority) {
                fetch('/api/next_priority_task').then(r => r.json()).then(data => {
                    if (data && data.id) {
                        currentTaskId = data.id.toString();
                        localStorage.setItem('timerTask', currentTaskId);
                        updateTaskSelects(currentTaskId);
                        fetchSubtasks(currentTaskId, null);
                    }
                    setTimeout(() => finishBreak(), 200);
                });
            } else finishBreak();
        }
    }

    function finishBreak() {
        updateUI();
        document.body.dispatchEvent(new CustomEvent('tasksChanged'));
        if (settings.autoStartFocus) startTimer(true); else window.modoNotify('Break Over! Ready to focus?', 'warning');
    }

    function attachListeners() {
        document.body.addEventListener('tasksChanged', () => {
            fetch('/api/timer_tasks').then(r => r.text()).then(html => {
                [elements.global.task, elements.page.task].forEach(s => { if(s) { const v = s.value; s.innerHTML = html; s.value = v; } });
                if (currentTaskId) fetchSubtasks(currentTaskId, currentSubtaskId);
            });
        });

        [elements.global, elements.page].forEach(els => {
            if (els.start) els.start.addEventListener('click', () => startTimer(true));
            if (els.pause) els.pause.addEventListener('click', () => pauseTimer());
            if (els.reset) els.reset.addEventListener('click', resetTimer);
            if (els.skip) els.skip.addEventListener('click', skipBreak);
            if (els.end) els.end.addEventListener('click', endSession);
            if (els.task) els.task.addEventListener('change', (e) => { 
                currentTaskId = e.target.value; 
                currentSubtaskId = null; 
                localStorage.setItem('timerSubtask', ''); 
                updateTaskSelects(currentTaskId, true); 
                localStorage.setItem('timerTask', currentTaskId); 
                updateUI(); 
            });
        });

        [elements.global.subtask, elements.page.subtask].forEach(s => {
            if (s) s.addEventListener('change', (e) => {
                currentSubtaskId = e.target.value;
                localStorage.setItem('timerSubtask', currentSubtaskId);
                if (elements.global.subtask) elements.global.subtask.value = currentSubtaskId;
                if (elements.page.subtask) elements.page.subtask.value = currentSubtaskId;
                updateUI();
            });
        });
    }

    window.addEventListener('storage', (e) => {
        if (['timerStatus', 'timerEnd', 'timerSecondsLeft', 'timerMode'].includes(e.key)) loadState();
    });

    init();
});