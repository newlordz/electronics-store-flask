// Enhanced JavaScript for Electronics Store
document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize all components
    initializeAjaxCart();
    initializePaymentMethods();
    initializeProductActions();
    initializeAnimations();
    initializeOrderWorkflow(); // Ensure this is called

    // AJAX Cart functionality
    function initializeAjaxCart() {
        const cartForms = document.querySelectorAll('.ajax-cart-form');
        
        cartForms.forEach(form => {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const button = this.querySelector('.add-to-cart-btn');
                const productId = button.dataset.productId;
                const originalText = button.innerHTML;
                
                // Show loading state
                button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';
                button.disabled = true;
                
                // Send AJAX request
                fetch(this.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => {
                    // Check if response is a redirect (login required)
                    if (response.redirected || response.status === 302) {
                        // User needs to login
                        showLoginModal();
                        button.innerHTML = originalText;
                        button.disabled = false;
                        return;
                    }
                    
                    // Check for 401 status (login required)
                    if (response.status === 401) {
                        return response.json().then(data => {
                            if (data.login_required) {
                                showLoginModal();
                                button.innerHTML = originalText;
                                button.disabled = false;
                                return null;
                            }
                            return data;
                        });
                    }
                    
                    // Check if response is JSON
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json();
                    } else {
                        // Handle non-JSON responses (like HTML redirects)
                        throw new Error('Login required');
                    }
                })
                .then(data => {
                    // Skip if data is null (login modal was shown)
                    if (data === null) {
                        return;
                    }
                    
                    if (data && data.success) {
                        // Show success feedback
                        button.innerHTML = '<i class="fas fa-check me-1"></i>Added!';
                        button.className = 'btn btn-success add-to-cart-btn';
                        
                        // Update cart count if element exists
                        const cartBadge = document.querySelector('.cart-count');
                        if (cartBadge) {
                            cartBadge.textContent = data.cart_count;
                        }
                        
                        // Show toast notification
                        showToast('Product added to cart!', 'success');
                        
                        // Reset button after 2 seconds
                        setTimeout(() => {
                            button.innerHTML = originalText;
                            button.className = 'btn btn-primary add-to-cart-btn';
                            button.disabled = false;
                        }, 2000);
                    } else if (data) {
                        // Show error message from server
                        showToast(data.message || 'Error adding to cart', 'error');
                        button.innerHTML = originalText;
                        button.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    if (error.message === 'Login required') {
                        showLoginModal();
                    } else {
                        showToast('Error adding to cart', 'error');
                    }
                    button.innerHTML = originalText;
                    button.disabled = false;
                });
            });
        });
    }
    
    // Payment method toggle
    function initializePaymentMethods() {
        const paymentMethods = document.querySelectorAll('input[name="payment_method"]');
        const creditCardFields = document.getElementById('creditCardFields');
        const momoFields = document.getElementById('momoFields');
        
        if (paymentMethods.length > 0) {
            paymentMethods.forEach(method => {
                method.addEventListener('change', function() {
                    // Hide all fields
                    if (creditCardFields) creditCardFields.style.display = 'none';
                    if (momoFields) momoFields.style.display = 'none';
                    
                    // Show relevant fields
                    if (this.value === 'credit_card' && creditCardFields) {
                        creditCardFields.style.display = 'block';
                    } else if (this.value === 'momo' && momoFields) {
                        momoFields.style.display = 'block';
                    }
                });
            });
            // Trigger change on load to set initial visibility
            const checkedMethod = document.querySelector('input[name="payment_method"]:checked');
            if (checkedMethod) {
                checkedMethod.dispatchEvent(new Event('change'));
            }
        }
    }
    
    // Product management actions
    function initializeProductActions() {
        // Product delete buttons
        const deleteButtons = document.querySelectorAll('.delete-product-btn');
        deleteButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const productName = this.dataset.productName;
                if (confirm(`Are you sure you want to delete "${productName}"? This action cannot be undone.`)) {
                    window.location.href = this.href;
                }
            });
        });
        
        // Product toggle buttons
        const toggleButtons = document.querySelectorAll('.toggle-product-btn');
        toggleButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const action = this.dataset.action;
                const productName = this.dataset.productName;
                if (confirm(`Are you sure you want to ${action} "${productName}"?`)) {
                    window.location.href = this.href;
                }
            });
        });
    }
    
    // Cart quantity controls
    function initializeCartQuantity() {
        const quantityButtons = document.querySelectorAll('.quantity-btn');
        
        quantityButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                
                const action = this.dataset.action;
                const productId = this.dataset.productId;
                const quantitySpan = document.querySelector(`#quantity-${productId}`);
                let currentQuantity = parseInt(quantitySpan.textContent);
                
                if (action === 'increase') {
                    currentQuantity++;
                } else if (action === 'decrease' && currentQuantity > 1) {
                    currentQuantity--;
                } else if (action === 'decrease' && currentQuantity === 1) {
                    if (confirm('Remove this item from cart?')) {
                        window.location.href = `/remove_from_cart/${productId}`;
                        return;
                    } else {
                        return;
                    }
                }
                
                // Update quantity via AJAX
                fetch(`/update_cart_quantity/${productId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ quantity: currentQuantity })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        quantitySpan.textContent = currentQuantity;
                        // Update item total and cart total
                        document.querySelector(`#item-total-${productId}`).textContent = `$${data.item_total.toFixed(2)}`;
                        document.querySelector('#cart-total').textContent = `$${data.cart_total.toFixed(2)}`;
                    }
                })
                .catch(error => {
                    console.error('Error updating quantity:', error);
                    showToast('Error updating quantity', 'error');
                });
            });
        });
    }
    
    // Initialize cart quantity controls if on cart page
    if (document.querySelector('.quantity-btn')) {
        initializeCartQuantity();
    }
    
    // Animation enhancements
    function initializeAnimations() {
        // Stagger animations for product cards
        const productCards = document.querySelectorAll('.card');
        productCards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
            card.classList.add('animate__animated', 'animate__fadeInUp');
        });
        
        // Hover effects for buttons
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(btn => {
            btn.addEventListener('mouseenter', function() {
                this.classList.add('animate__animated', 'animate__pulse');
            });
            
            btn.addEventListener('mouseleave', function() {
                this.classList.remove('animate__animated', 'animate__pulse');
            });
        });
    }
    
    // Toast notification system
    function showToast(message, type = 'info') {
        console.log('showToast called with:', message, type); // Debug log
        
        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Initialize and show toast
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        bsToast.show();
        
        // Remove toast element after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            this.remove();
        });
    }
    
    // Login modal for non-authenticated users
    function showLoginModal() {
        // Create modal if it doesn't exist
        let loginModal = document.getElementById('loginModal');
        if (!loginModal) {
            loginModal = document.createElement('div');
            loginModal.className = 'modal fade';
            loginModal.id = 'loginModal';
            loginModal.setAttribute('tabindex', '-1');
            loginModal.setAttribute('aria-labelledby', 'loginModalLabel');
            loginModal.setAttribute('aria-hidden', 'true');
            
            loginModal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header bg-primary text-white">
                            <h5 class="modal-title" id="loginModalLabel">
                                <i class="fas fa-sign-in-alt me-2"></i>Login Required
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body text-center">
                            <div class="mb-4">
                                <i class="fas fa-shopping-cart fa-3x text-primary mb-3"></i>
                                <h5>Please Login to Add Items to Cart</h5>
                                <p class="text-muted">You need to be logged in to add products to your shopping cart.</p>
                            </div>
                            <div class="d-grid gap-2">
                                <a href="/login" class="btn btn-primary">
                                    <i class="fas fa-sign-in-alt me-2"></i>Login Now
                                </a>
                                <a href="/register" class="btn btn-outline-primary">
                                    <i class="fas fa-user-plus me-2"></i>Create Account
                                </a>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Continue Shopping</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(loginModal);
        }
        
        // Show the modal
        const modal = new bootstrap.Modal(loginModal);
        modal.show();
    }
    
    // Order workflow status updates
    function initializeOrderWorkflow() {
        const statusButtons = document.querySelectorAll('.order-status-btn');
        
        statusButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault(); // Prevent default form submission initially
                
                const action = this.dataset.action;
                const orderId = this.dataset.orderId;
                
                let confirmMessage = '';
                switch(action) {
                    case 'seller_approve':
                        confirmMessage = 'Approve this order receipt?';
                        break;
                    case 'buyer_confirm':
                        confirmMessage = 'Confirm that you have received this order?';
                        break;
                    case 'buyer_pay': // Added this case for the "Pay Now" button
                        confirmMessage = 'Proceed with payment for this order?';
                        break;
                    default:
                        confirmMessage = 'Proceed with this action?';
                }
                
                if (confirm(confirmMessage)) {
                    // Show loading state
                    const originalText = this.innerHTML;
                    this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                    this.disabled = true;
                    
                    // Submit the form that contains this button
                    // This assumes the button is inside a form
                    const form = this.closest('form');
                    if (form) {
                        form.submit(); // Explicitly submit the form
                    } else {
                        // Fallback if button is not in a form (less ideal for POST requests)
                        // This should ideally not be hit for workflow buttons
                        window.location.href = this.href;
                    }
                }
            });
        });
    }
    
    // Initialize order workflow if elements exist
    // This check is redundant if initializeOrderWorkflow() is called directly,
    // but harmless.
    // if (document.querySelector('.order-status-btn')) {
    //     initializeOrderWorkflow();
    // }
});

// Global utility functions
window.ElectronicsStore = {
    // Show loading state for any button
    showButtonLoading: function(button, loadingText = 'Loading...') {
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>${loadingText}`;
        button.disabled = true;
    },
    
    // Reset button to original state
    resetButton: function(button) {
        if (button.dataset.originalText) {
            button.innerHTML = button.dataset.originalText;
            button.disabled = false;
        }
    },
    // Function to update cart count in navbar
    updateCartCount: function() {
        // This function would typically make an AJAX call to get the current cart count
        // For now, it will just update based on the server-rendered count or a dummy value.
        // The context processor in app.py already handles the initial render.
        // If you need real-time updates without page reload, you'd add fetch logic here.
        console.log("Updating cart count (placeholder for AJAX update)");
    }
};

// Wishlist AJAX
$(document).on('click', '.add-to-wishlist-btn', function(e) {
    console.log('Wishlist button clicked'); // Debug log
    e.preventDefault();
    var productId = $(this).data('product-id');
    console.log('Product ID:', productId); // Debug log
    
    // Show loading state
    var button = $(this);
    var originalText = button.html();
    button.html('<i class="fas fa-spinner fa-spin"></i>');
    button.prop('disabled', true);
    
    fetch('/add_to_wishlist/' + productId, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        console.log('Response status:', response.status); // Debug log
        if (response.status === 401) {
            showLoginModal();
            return null;
        }
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data); // Debug log
        if (!data) {
            // Reset button if login modal was shown
            button.html(originalText);
            button.prop('disabled', false);
            return;
        }
        if (data.success) {
            console.log('Showing success toast'); // Debug log
            showToast('Added to wishlist!', 'success');
            
            // Change button to show "Added" state but keep it visible
            button.removeClass('btn-outline-danger').addClass('btn-success');
            button.html('<i class="fas fa-heart"></i>');
            button.prop('disabled', true);
            
            // Keep the button visible but change it back after a delay
            setTimeout(() => {
                button.removeClass('btn-success').addClass('btn-outline-danger');
                button.html('<i class="fas fa-heart"></i>');
                button.prop('disabled', false);
            }, 3000);
            
        } else {
            console.log('Showing error toast'); // Debug log
            showToast(data.message || 'Error adding to wishlist', 'error');
            // Reset button on error
            button.html(originalText);
            button.prop('disabled', false);
        }
    })
    .catch((error) => {
        console.log('Fetch error:', error); // Debug log
        showToast('Error adding to wishlist', 'error');
        // Reset button on error
        button.html(originalText);
        button.prop('disabled', false);
    });
});

$(document).on('click', '.remove-from-wishlist-btn', function(e) {
    e.preventDefault();
    var productId = $(this).data('product-id');
    fetch('/remove_from_wishlist/' + productId, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (response.status === 401) {
            showLoginModal();
            return null;
        }
        return response.json();
    })
    .then(data => {
        if (!data) return;
        if (data.success) {
            location.reload();
        } else {
            showToast(data.message || 'Error removing from wishlist', 'error');
        }
    })
    .catch(() => {
        showToast('Error removing from wishlist', 'error');
    });
});
