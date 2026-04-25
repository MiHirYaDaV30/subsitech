/* home.js - Home Page Specific Logic */

document.addEventListener('DOMContentLoaded', () => {
    // Add any home-page specific interactions here
    
    // Example: Animate stats counts
    const stats = document.querySelectorAll('.stat-item h3');
    
    const animateStats = () => {
        stats.forEach(stat => {
            // Simple animation logic if desired
            // stat.innerText = ...
        });
    };

    // Intersection Observer for scroll animations
    const observerOptions = {
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .opp-card').forEach(el => {
        observer.observe(el);
    });

    // FAQ Accordion Logic
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        question.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            
            // Close all other items
            faqItems.forEach(otherItem => {
                otherItem.classList.remove('active');
            });
            
            // Toggle current item
            if (!isActive) {
                item.classList.add('active');
            }
        });
    });
});
