// Frontend JavaScript for CrossBorder E-commerce Platform

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all frontend functionality
    initializeScrollAnimations();
    initializeNavbarEffects();
    initializeProductInteractions();
    initializeHeroAnimations();
    initializeCategoryHoverEffects();
    initializeScrollProgress();
});

// Scroll animations for fade-in elements
function initializeScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                // Add stagger effect for multiple elements
                const fadeElements = entry.target.querySelectorAll('.fade-in');
                fadeElements.forEach((element, index) => {
                    setTimeout(() => {
                        element.classList.add('visible');
                    }, index * 150);
                });
            }
        });
    }, observerOptions);

    // Observe all fade-in elements
    const fadeElements = document.querySelectorAll('.fade-in');
    fadeElements.forEach(element => {
        observer.observe(element);
    });
}

// Navbar effects on scroll
function initializeNavbarEffects() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            navbar.classList.add('navbar-scrolled');
            navbar.style.backdropFilter = 'blur(10px)';
            navbar.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
            navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
        } else {
            navbar.classList.remove('navbar-scrolled');
            navbar.style.backdropFilter = 'none';
            navbar.style.backgroundColor = 'white';
            navbar.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1)';
        }
    });
}

// Product card interactions
function initializeProductInteractions() {
    // Heart button functionality
    const heartButtons = document.querySelectorAll('.product-overlay .btn-light');
    heartButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const icon = this.querySelector('i');
            if (icon.classList.contains('bi-heart')) {
                icon.classList.remove('bi-heart');
                icon.classList.add('bi-heart-fill', 'text-danger');
                showToast('已添加到收藏夹 ❤️', 'success');
            } else {
                icon.classList.remove('bi-heart-fill', 'text-danger');
                icon.classList.add('bi-heart');
                showToast('已从收藏夹移除', 'info');
            }
        });
    });

    // Add to cart functionality
    const cartButtons = document.querySelectorAll('.product-overlay .btn-primary');
    cartButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const originalHTML = this.innerHTML;
            this.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div>';
            this.disabled = true;
            
            // Simulate adding to cart
            setTimeout(() => {
                this.innerHTML = '<i class="bi bi-check-circle"></i>';
                showToast('已添加到购物车 🛒', 'success');
                
                // Update cart counter (if exists)
                updateCartCounter();
                
                setTimeout(() => {
                    this.innerHTML = originalHTML;
                    this.disabled = false;
                }, 1500);
            }, 1000);
        });
    });
}

// Hero section animations
function initializeHeroAnimations() {
    const heroSection = document.querySelector('.hero-section');
    if (!heroSection) return;

    // Animate hero elements on load
    const heroElements = heroSection.querySelectorAll('.hero-title, .hero-subtitle, .hero-buttons');
    heroElements.forEach((element, index) => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(30px)';
        setTimeout(() => {
            element.style.transition = 'all 0.8s ease';
            element.style.opacity = '1';
            element.style.transform = 'translateY(0)';
        }, index * 200);
    });
}

// Category hover effects
function initializeCategoryHoverEffects() {
    const categoryCards = document.querySelectorAll('.category-card');
    categoryCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            const icon = this.querySelector('i');
            if (icon) {
                icon.style.transform = 'scale(1.1) rotate(5deg)';
                icon.style.transition = 'all 0.3s ease';
            }
        });
        
        card.addEventListener('mouseleave', function() {
            const icon = this.querySelector('i');
            if (icon) {
                icon.style.transform = 'scale(1) rotate(0deg)';
            }
        });
    });
}

// Scroll progress indicator
function initializeScrollProgress() {
    const progressBar = document.createElement('div');
    progressBar.className = 'scroll-progress';
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0%;
        height: 3px;
        background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
        z-index: 9999;
        transition: width 0.3s ease;
    `;
    document.body.appendChild(progressBar);

    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = (scrollTop / docHeight) * 100;
        progressBar.style.width = scrollPercent + '%';
    });
}

// Update cart counter
function updateCartCounter() {
    const cartCounter = document.querySelector('.cart-counter');
    if (cartCounter) {
        let count = parseInt(cartCounter.textContent) || 0;
        count++;
        cartCounter.textContent = count;
        
        // Add animation
        cartCounter.style.transform = 'scale(1.3)';
        setTimeout(() => {
            cartCounter.style.transform = 'scale(1)';
        }, 200);
    }
}

// Toast notification system
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} border-0`;
    toast.setAttribute('role', 'alert');
    toast.style.cssText = 'min-width: 250px;';
    
    const emoji = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body d-flex align-items-center">
                <span class="me-2">${emoji}</span>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

// Create toast container if it doesn't exist
function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Counter animation for statistics
function animateCounters() {
    const counters = document.querySelectorAll('.feature-stats .h5');
    counters.forEach(counter => {
        const text = counter.textContent;
        const hasPercentage = text.includes('%');
        const hasPlus = text.includes('+');
        const hasDays = text.includes('天');
        const number = parseInt(text.replace(/[^\d]/g, ''));
        
        if (isNaN(number)) return;
        
        const increment = number / 50;
        let current = 0;
        
        const timer = setInterval(() => {
            current += increment;
            if (current >= number) {
                let finalText = number.toString();
                if (hasPercentage) finalText += '%';
                if (hasPlus) finalText += '+';
                if (hasDays) finalText = '7';
                counter.textContent = finalText;
                clearInterval(timer);
            } else {
                counter.textContent = Math.floor(current) + (hasPercentage ? '%' : '') + (hasPlus ? '+' : '') + (hasDays ? '天' : '');
            }
        }, 30);
    });
}

// Initialize counter animation when feature section is visible
const featureSection = document.querySelector('.feature-stats');
if (featureSection) {
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounters();
                observer.unobserve(entry.target);
            }
        });
    });
    observer.observe(featureSection);
}

// Add loading animation
window.addEventListener('load', function() {
    document.body.classList.add('loaded');
    
    // Add entrance animations
    setTimeout(() => {
        const elements = document.querySelectorAll('.hero-section, .category-card, .product-card');
        elements.forEach((element, index) => {
            setTimeout(() => {
                element.style.opacity = '1';
                element.style.transform = 'translateY(0)';
            }, index * 100);
        });
    }, 300);
});

// Add some utility functions for frontend
window.FrontendUtils = {
    formatPrice: function(price) {
        return '¥' + parseFloat(price).toFixed(2);
    },
    
    formatDate: function(date) {
        return new Intl.DateTimeFormat('zh-CN', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        }).format(new Date(date));
    },
    
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // Add to cart function - 使用Utils.addToCart替代
    addToCart: function(productId, quantity = 1) {
        if (typeof Utils !== 'undefined' && Utils.addToCart) {
            Utils.addToCart(productId, quantity);
        } else {
            showToast('正在添加到购物车...', 'info');
            setTimeout(() => {
                updateCartCounter();
                showToast('商品已添加到购物车！', 'success');
            }, 800);
        }
    },
    
    // Wishlist function
    toggleWishlist: function(productId) {
        showToast('收藏夹功能已更新', 'success');
    }
};

// Add CSS for initial states
document.addEventListener('DOMContentLoaded', function() {
    const style = document.createElement('style');
    style.textContent = `
        .hero-section, .category-card, .product-card {
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.6s ease;
        }
        
        .navbar-scrolled {
            transition: all 0.3s ease;
        }
        
        .scroll-progress {
            transition: width 0.3s ease;
        }
    `;
    document.head.appendChild(style);
});