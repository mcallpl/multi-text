/* MultiText — Global JS */

// Nothing global needed yet — page-specific JS is in template blocks.
// This file is reserved for shared utilities if needed later.

document.addEventListener('DOMContentLoaded', () => {
    // Highlight active nav link based on current path
    const path = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href === path || (href !== '/' && path.startsWith(href))) {
            link.classList.add('active');
        }
    });
});
