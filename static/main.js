// Main JavaScript file for Electronics Store

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize cart functionality
    initializeCart();
    
    // Initialize form validation
    initializeFormValidation();
    
    // Initialize search functionality
    initializeSearch();
    
    // Initialize product filters
    initializeFilters();
});

// Initialize Bootstrap tooltips
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Cart functionality
function initializeCart() {
    // Update cart count in navbar
    updateCartCount();
    
    // Add to cart buttons
    const addToCartButtons = document.querySelectorAll('.add-to-cart');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.dataset.productId;
            addToCart(productId);
        });
    });
    
    // Remove from cart buttons
    const removeFromCartButtons = document.querySelectorAll('.remove-from-cart');
    removeFromCartButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const itemId = this.dataset.itemId;
            removeFromCart(itemId);
        });
    });
}

// Add product to cart
function addToCart(productId) {
    // Show loading state
    showLoading();
    
    // In a real application, this would be an AJAX call
    // For now, we'll redirect to the add_to_cart route
    window.location.href = `/add_to_cart/${productId}`;
}

// Remove item from cart
function removeFromCart(itemId) {
    if (confirm('Are you sure you want to remove this item from your cart?')) {
        window.location.href = `/remove_from_cart/${itemId}`;
    }
}

// Update cart count in navbar
function updateCartCount() {
    // This would normally fetch the cart count via AJAX
    // For now, we'll use server-side rendering
}

// Form validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
    
    // Custom validation for checkout form
    const checkoutForm = document.getElementById('checkout-form');
    if (checkoutForm) {
        validateCheckoutForm(checkoutForm);
    }
}

// Checkout form validation
function validateCheckoutForm(form) {
    const creditCardFields = document.getElementById('creditCardFields');
    const paymentMethods = document.querySelectorAll('input[name="paymentMethod"]');
    
    paymentMethods.forEach(method => {
        method.addEventListener('change', function() {
            if (this.value === 'credit') {
                creditCardFields.style.display = 'block';
                setFieldsRequired(creditCardFields, true);
            } else {
                creditCardFields.style.display = 'none';
                setFieldsRequired(creditCardFields, false);
            }
        });
    });
}

// Set required attribute for fields
function setFieldsRequired(container, required) {
    const inputs = container.querySelectorAll('input');
    inputs.forEach(input => {
        if (required) {
            input.setAttribute('required', '');
        } else {
            input.removeAttribute('required');
        }
    });
}

// Search functionality
function initializeSearch() {
    const searchInput = document.getElementById('search');
    const searchButton = document.getElementById('search-button');
    
    if (searchInput) {
        // Auto-submit search on Enter
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });
    }
    
    if (searchButton) {
        searchButton.addEventListener('click', function(e) {
            e.preventDefault();
            performSearch();
        });
    }
}

// Perform search
function performSearch() {
    const searchInput = document.getElementById('search');
    const categorySelect = document.getElementById('category');
    
    let searchParams = new URLSearchParams();
    
    if (searchInput && searchInput.value.trim()) {
        searchParams.set('search', searchInput.value.trim());
    }
    
    if (categorySelect && categorySelect.value) {
        searchParams.set('category', categorySelect.value);
    }
    
    window.location.href = `/products?${searchParams.toString()}`;
}

// Filter functionality
function initializeFilters() {
    const filterButtons = document.querySelectorAll('.filter-btn');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filter = this.dataset.filter;
            const value = this.dataset.value;
            applyFilter(filter, value);
        });
    });
}

// Apply filter
function applyFilter(filter, value) {
    let searchParams = new URLSearchParams(window.location.search);
    
    if (value) {
        searchParams.set(filter, value);
    } else {
        searchParams.delete(filter);
    }
    
    window.location.href = `${window.location.pathname}?${searchParams.toString()}`;
}

// Show loading indicator
function showLoading() {
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'loading-overlay';
    loadingIndicator.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingIndicator);
}

// Hide loading indicator
function hideLoading() {
    const loadingIndicator = document.querySelector('.loading-overlay');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show notification`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(notification, container.firstChild);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (notification) {
            notification.remove();
        }
    }, 5000);
}

// Confirm action
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Image preview for file uploads
function previewImage(input, previewId) {
    const file = input.files[0];
    const preview = document.getElementById(previewId);
    
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
}

// Quantity controls
function updateQuantity(itemId, change) {
    const quantityInput = document.querySelector(`input[data-item-id="${itemId}"]`);
    if (quantityInput) {
        let currentQuantity = parseInt(quantityInput.value);
        let newQuantity = currentQuantity + change;
        
        if (newQuantity < 1) {
            newQuantity = 1;
        }
        
        quantityInput.value = newQuantity;
        updateItemTotal(itemId, newQuantity);
    }
}

// Update item total
function updateItemTotal(itemId, quantity) {
    const priceElement = document.querySelector(`[data-price-for="${itemId}"]`);
    const totalElement = document.querySelector(`[data-total-for="${itemId}"]`);
    
    if (priceElement && totalElement) {
        const price = parseFloat(priceElement.dataset.price);
        const total = price * quantity;
        totalElement.textContent = formatCurrency(total);
        
        updateCartTotal();
    }
}

// Update cart total
function updateCartTotal() {
    const totalElements = document.querySelectorAll('[data-total-for]');
    let cartTotal = 0;
    
    totalElements.forEach(element => {
        const total = parseFloat(element.textContent.replace('$', ''));
        cartTotal += total;
    });
    
    const cartTotalElement = document.getElementById('cart-total');
    if (cartTotalElement) {
        cartTotalElement.textContent = formatCurrency(cartTotal);
    }
}

// Smooth scroll to element
function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth'
        });
    }
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showNotification('Copied to clipboard!', 'success');
    }).catch(function(err) {
        console.error('Could not copy text: ', err);
        showNotification('Failed to copy to clipboard', 'danger');
    });
}

// Debounce function for search
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize lazy loading for images
function initializeLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });
    
    images.forEach(img => imageObserver.observe(img));
}

// Handle form submission with loading state
function handleFormSubmission(form) {
    form.addEventListener('submit', function() {
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="loading"></span> Processing...';
        }
    });
}

// Initialize all form submissions
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(handleFormSubmission);
});

// Error handling for images
document.addEventListener('DOMContentLoaded', function() {
    const images = document.querySelectorAll('img');
    images.forEach(img => {
        img.addEventListener('error', function() {
            this.src = '/static/images/placeholder.svg';
            this.alt = 'Image not available';
        });
    });
});
