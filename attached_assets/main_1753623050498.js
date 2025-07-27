// Enhanced Electronics Store JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initializeTooltips();
    initializeImageHandling();
    initializeFormValidation();
    initializeSearchAndFilters();
    initializeAnimations();
    initializeProductActions();
    initializeOrderComments();
});

// Initialize Bootstrap tooltips and popovers
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// Handle image loading and error states
function initializeImageHandling() {
    const images = document.querySelectorAll('img');
    
    images.forEach(img => {
        // Add loading placeholder
        if (!img.complete) {
            img.style.backgroundColor = '#f0f0f0';
        }
        
        // Handle image load
        img.addEventListener('load', function() {
            this.style.backgroundColor = 'transparent';
            this.classList.add('fade-in-up');
        });
        
        // Handle image error
        img.addEventListener('error', function() {
            this.src = '/static/images/placeholder.svg';
            this.alt = 'Image not available';
            this.style.backgroundColor = '#f8f9fa';
        });
    });
    
    // Image preview for file uploads
    const fileInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            previewImage(this);
        });
    });
}

// Preview uploaded image
function previewImage(input) {
    const file = input.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            let preview = document.getElementById('image-preview');
            if (!preview) {
                preview = document.createElement('img');
                preview.id = 'image-preview';
                preview.className = 'img-fluid rounded mt-3';
                preview.style.maxHeight = '200px';
                input.parentNode.appendChild(preview);
            }
            preview.src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
}

// Form validation and enhancement
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
                
                // Focus on first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            } else {
                // Show loading state
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    const originalText = submitBtn.innerHTML;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                    submitBtn.disabled = true;
                    
                    // Re-enable after 3 seconds (fallback)
                    setTimeout(() => {
                        submitBtn.innerHTML = originalText;
                        submitBtn.disabled = false;
                    }, 3000);
                }
            }
            form.classList.add('was-validated');
        });
    });
    
    // Real-time validation
    const inputs = document.querySelectorAll('.form-control, .form-select');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.checkValidity()) {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } else {
                this.classList.remove('is-valid');
                this.classList.add('is-invalid');
            }
        });
    });
}

// Search and filter functionality
function initializeSearchAndFilters() {
    const searchForm = document.querySelector('.search-form');
    const searchInput = document.getElementById('search');
    const categorySelect = document.getElementById('category');
    
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            performSearch();
        });
    }
    
    if (searchInput) {
        // Debounced search
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (this.value.length >= 3 || this.value.length === 0) {
                    performSearch();
                }
            }, 500);
        });
    }
    
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            performSearch();
        });
    }
    
    // Category pills
    const categoryPills = document.querySelectorAll('.category-pill');
    categoryPills.forEach(pill => {
        pill.addEventListener('click', function(e) {
            e.preventDefault();
            const category = this.dataset.category;
            window.location.href = `/products${category ? '?category=' + encodeURIComponent(category) : ''}`;
        });
    });
}

// Perform search
function performSearch() {
    const searchInput = document.getElementById('search');
    const categorySelect = document.getElementById('category');
    
    const params = new URLSearchParams();
    
    if (searchInput && searchInput.value.trim()) {
        params.set('search', searchInput.value.trim());
    }
    
    if (categorySelect && categorySelect.value) {
        params.set('category', categorySelect.value);
    }
    
    window.location.href = `/products${params.toString() ? '?' + params.toString() : ''}`;
}

// Initialize animations
function initializeAnimations() {
    // Intersection Observer for scroll animations
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
            }
        });
    }, {
        threshold: 0.1
    });
    
    // Observe cards and other elements
    const elements = document.querySelectorAll('.card, .dashboard-card, .product-card');
    elements.forEach(el => {
        observer.observe(el);
    });
    
    // Smooth scroll for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
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
}

// Product-specific actions
function initializeProductActions() {
    // Add to cart buttons
    const addToCartBtns = document.querySelectorAll('.add-to-cart-btn');
    addToCartBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.dataset.productId;
            
            // Visual feedback
            const originalText = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';
            this.disabled = true;
            
            // Simulate loading (since we're using server-side redirects)
            setTimeout(() => {
                window.location.href = `/add_to_cart/${productId}`;
            }, 500);
        });
    });
    
    // Product status toggle
    const statusToggleBtns = document.querySelectorAll('.status-toggle-btn');
    statusToggleBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.dataset.productId;
            const action = this.dataset.action;
            
            if (confirm(`Are you sure you want to ${action} this product?`)) {
                window.location.href = `/toggle_product/${productId}`;
            }
        });
    });
    
    // Remove from cart with confirmation
    const removeFromCartBtns = document.querySelectorAll('.remove-from-cart-btn');
    removeFromCartBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            if (confirm('Are you sure you want to remove this item from your cart?')) {
                const itemId = this.dataset.itemId;
                window.location.href = `/remove_from_cart/${itemId}`;
            }
        });
    });
}

// Order comments functionality
function initializeOrderComments() {
    const commentForm = document.getElementById('comment-form');
    const commentTextarea = document.getElementById('comment-message');
    const commentSubmitBtn = document.getElementById('comment-submit');
    
    if (commentForm) {
        commentForm.addEventListener('submit', function(e) {
            const message = commentTextarea.value.trim();
            if (!message) {
                e.preventDefault();
                showNotification('Please enter a message', 'warning');
                commentTextarea.focus();
                return;
            }
            
            // Show loading state
            if (commentSubmitBtn) {
                const originalText = commentSubmitBtn.innerHTML;
                commentSubmitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';
                commentSubmitBtn.disabled = true;
            }
        });
    }
    
    // Auto-resize textarea
    if (commentTextarea) {
        commentTextarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }
}

// Utility functions
function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-hide
    setTimeout(() => {
        if (notification && notification.parentNode) {
            notification.remove();
        }
    }, duration);
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Copy to clipboard functionality
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showNotification('Failed to copy to clipboard', 'danger');
    });
}

// Loading overlay
function showLoadingOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner-border text-primary" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoadingOverlay() {
    const overlay = document.querySelector('.loading-overlay');
    if (overlay) {
        overlay.remove();
    }
}

// Handle responsive navigation
function initializeNavigation() {
    const navbar = document.querySelector('.navbar');
    const navbarToggler = document.querySelector('.navbar-toggler');
    
    if (navbarToggler) {
        navbarToggler.addEventListener('click', function() {
            this.classList.toggle('active');
        });
    }
    
    // Close mobile menu when clicking outside
    document.addEventListener('click', function(e) {
        const navbarCollapse = document.querySelector('.navbar-collapse.show');
        if (navbarCollapse && !navbar.contains(e.target)) {
            navbarCollapse.classList.remove('show');
            if (navbarToggler) {
                navbarToggler.classList.remove('active');
            }
        }
    });
}

// Initialize cart functionality
function initializeCart() {
    updateCartBadge();
    
    // Quantity controls
    const quantityInputs = document.querySelectorAll('.quantity-input');
    quantityInputs.forEach(input => {
        input.addEventListener('change', function() {
            updateCartTotal();
        });
    });
    
    const decreaseBtns = document.querySelectorAll('.quantity-decrease');
    const increaseBtns = document.querySelectorAll('.quantity-increase');
    
    decreaseBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const input = this.nextElementSibling;
            const currentValue = parseInt(input.value);
            if (currentValue > 1) {
                input.value = currentValue - 1;
                updateCartTotal();
            }
        });
    });
    
    increaseBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const input = this.previousElementSibling;
            const currentValue = parseInt(input.value);
            input.value = currentValue + 1;
            updateCartTotal();
        });
    });
}

function updateCartBadge() {
    // This would normally be updated via AJAX
    // For now, it's handled server-side
}

function updateCartTotal() {
    const cartItems = document.querySelectorAll('.cart-item');
    let total = 0;
    
    cartItems.forEach(item => {
        const price = parseFloat(item.dataset.price);
        const quantity = parseInt(item.querySelector('.quantity-input').value);
        const itemTotal = price * quantity;
        
        const itemTotalElement = item.querySelector('.item-total');
        if (itemTotalElement) {
            itemTotalElement.textContent = formatCurrency(itemTotal);
        }
        
        total += itemTotal;
    });
    
    const cartTotalElement = document.getElementById('cart-total');
    if (cartTotalElement) {
        cartTotalElement.textContent = formatCurrency(total);
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    initializeCart();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // Page is hidden
        document.title = '💤 ' + document.title.replace('💤 ', '');
    } else {
        // Page is visible
        document.title = document.title.replace('💤 ', '');
    }
});

// Service worker registration (for future PWA features)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        // Service worker would be registered here
        console.log('Electronics Store app loaded');
    });
}
