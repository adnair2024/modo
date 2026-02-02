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
    
    if (e.key === 'j') {
        window.scrollBy({top: 100, behavior: 'smooth'});
    }
    
    if (e.key === 'k') {
        window.scrollBy({top: -100, behavior: 'smooth'});
    }
    
    if (e.key === 'G') {
        if (e.shiftKey)
           window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }
    
    // Go to Dashboard
    if (e.key === 'd') {
        window.location.href = '/';
    }
    
    // Go to Timer
    if (e.key === 't') {
        window.location.href = '/timer';
    }
});
