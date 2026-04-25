/* common.js - Shared functionality for Subsitech */

document.addEventListener('DOMContentLoaded', () => {
    console.log('Subsitech loaded');
    
    // Navbar scroll effect
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('navbar-scrolled');
            navbar.style.boxShadow = 'var(--shadow-md)';
        } else {
            navbar.classList.remove('navbar-scrolled');
            navbar.style.boxShadow = 'var(--shadow-sm)';
        }
    });

    // Mobile menu toggle (if needed)
    const initMobileMenu = () => {
        // Implementation for burger menu if added to header
    };

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
});
