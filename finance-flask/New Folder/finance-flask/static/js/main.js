// ============================================================
// FinanceTrack — Main JavaScript
// ============================================================

// Auto-dismiss alerts after 5 seconds
document.querySelectorAll('.alert').forEach(function(el) {
    setTimeout(function() {
        el.style.transition = 'opacity .5s';
        el.style.opacity = '0';
        setTimeout(function() { el.remove(); }, 500);
    }, 5000);
});

// Set today's date as default on all date inputs with no value
document.querySelectorAll('input[type="date"]').forEach(function(el) {
    if (!el.value && !el.min) {
        el.value = new Date().toISOString().split('T')[0];
    }
});

// Confirm on all delete links
document.querySelectorAll('a[href*="delete"]').forEach(function(el) {
    el.addEventListener('click', function(e) {
        if (!confirm('Are you sure you want to delete this?')) {
            e.preventDefault();
        }
    });
});
