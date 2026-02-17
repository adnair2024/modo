document.addEventListener('keydown', (e) => {
    // Ignore if input/textarea focused
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
        if (e.key === 'Escape') document.activeElement.blur();
        return;
    }
    
    // Global Binds
    if (e.key === '/') {
        e.preventDefault();
        const search = document.querySelector('input[name="q"]');
        if (search) search.focus();
    }
    
    if (e.key === 'c') {
        e.preventDefault();
        const title = document.querySelector('input[name="title"]');
        if (title) title.focus();
    }
    
    // Navigation
    if (e.key === 'j') {
        window.scrollBy({top: 150, behavior: 'smooth'});
    }
    
    if (e.key === 'k') {
        window.scrollBy({top: -150, behavior: 'smooth'});
    }

    if (e.key === 'g') {
        const genesisInput = document.getElementById('genesis-input');
        if (genesisInput && document.activeElement !== genesisInput) {
            e.preventDefault();
            genesisInput.focus();
            return;
        }
        
        if (window.lastG && Date.now() - window.lastG < 500) {
            window.scrollTo({ top: 0, behavior: 'smooth' });
            window.lastG = 0;
        } else {
            window.lastG = Date.now();
        }
    }
    
    if (e.key === 'G') {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }
    
    // Page Shortcuts
    if (e.key === 'd') window.location.href = '/';
    if (e.key === 't') window.location.href = '/timer';
    if (e.key === 's') window.location.href = '/schedule';
    if (e.key === 'h') window.location.href = '/habits';
    if (e.key === 'p') window.location.href = '/projects';
    if (e.key === 'f') window.location.href = '/friends';
    
    // Timer Controls (if on timer page or using global timer)
    if (e.key === ' ') { // Space to start/pause
        e.preventDefault();
        const startBtn = document.getElementById('page-timer-start') || document.getElementById('global-timer-start');
        const pauseBtn = document.getElementById('page-timer-pause') || document.getElementById('global-timer-pause');
        
        if (startBtn && !startBtn.classList.contains('hidden')) startBtn.click();
        else if (pauseBtn && !pauseBtn.classList.contains('hidden')) pauseBtn.click();
    }
    
    if (e.key === 'r') { // Reset timer
        const resetBtn = document.getElementById('page-timer-reset') || document.getElementById('global-timer-reset');
        if (resetBtn) resetBtn.click();
    }
});
