from flask import render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import logging
from app import app
from models import (users, products, orders, cart_items, order_comments as order_comments_data, 
                    create_user, get_user_by_email, get_user_by_id, create_product, 
                    get_products_by_category, get_products_by_vendor, add_to_cart, # add_to_cart now returns True/False
                    get_cart_items, create_order, get_orders_by_customer, get_orders_by_vendor,
                    add_order_comment, get_order_comments, update_order_status, 
                    get_orders_for_admin, get_orders_pending_vendor_approval, get_orders_pending_admin_approval,
                    get_promotional_products, get_featured_products,
                    create_discount_code, validate_discount_code, use_discount_code,
                    CartItem, spin_attempts, can_user_spin, get_next_spin_number, 
                    determine_spin_result, record_spin_attempt, get_user_spin_attempts,
                    add_product_review, get_product_reviews, get_product_average_rating, save_data) 

logger = logging.getLogger(__name__)

# Categories for electronics
CATEGORIES = ['Laptops', 'Smartphones', 'Mice', 'Keyboards', 'Headphones', 'Tablets', 'Accessories']

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Please log in to access this feature.', 'login_required': True}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def role_required(roles):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            user = get_user_by_id(session['user_id'])
            if not user:
                flash('Access denied. You do not have permission to view this page.', 'danger')
                return redirect(url_for('index'))
            
            # Handle role mapping: 'vendor' should be treated as 'seller'
            user_role = user.role
            if user_role == 'vendor' and 'seller' in roles:
                user_role = 'seller'
            
            if user_role not in roles:
                flash('Access denied. You do not have permission to view this page.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

# Role-specific decorators for convenience
admin_required = role_required(['admin'])
vendor_required = role_required(['seller'])
customer_required = role_required(['customer'])

# Helper function to update order status with proper checks and logging
def _perform_status_update(order_id, new_status, current_user_id):
    logger.debug(f"[_perform_status_update] Attempting to change order {order_id} to {new_status} by user {current_user_id}")
    logger.debug(f"[_perform_status_update] Current orders in memory: {list(orders.keys())}") # See what orders are loaded
    order = orders.get(order_id)
    if not order:
        flash('Order not found.', 'danger')
        logger.warning(f"[_perform_status_update] Failed: Order {order_id} not found in global orders dictionary. This is critical.")
        return False
    
    user = get_user_by_id(current_user_id)
    if not user:
        flash('Authentication error.', 'danger')
        logger.warning(f"[_perform_status_update] Failed: User {current_user_id} not found.")
        return False

    old_status = order.status
    logger.debug(f"[_perform_status_update] Order {order_id} current status: {old_status}, requested new status: {new_status}")
    
    # Define allowed transitions for each role from current status
    # This makes the workflow explicit and secure
    allowed_transitions = {
        'customer': {
            'pending': ['receipt_pending'], # Customer pays
            'approved': ['delivered']      # Customer confirms delivery
        },
        'vendor': {
            'receipt_pending': ['admin_review'], # Vendor approves receipt
            # Vendor can also mark as delivered, but we'll primarily use customer confirmation
            # 'approved': ['delivered'] 
        },
        'admin': {
            'pending': ['cancelled', 'receipt_pending', 'admin_review', 'approved', 'delivered'], # Admin can override
            'receipt_pending': ['cancelled', 'pending', 'admin_review', 'approved', 'delivered'],
            'admin_review': ['cancelled', 'pending', 'receipt_pending', 'approved', 'delivered'],
            'approved': ['cancelled', 'pending', 'receipt_pending', 'admin_review', 'delivered'],
            'delivered': ['cancelled', 'pending', 'receipt_pending', 'admin_review', 'approved'] # Admin can change any status
        }
    }

    # Check if the user's role is allowed to perform this specific transition
    if user.role not in allowed_transitions or new_status not in allowed_transitions[user.role].get(old_status, []):
        flash(f'Access denied. You cannot change order status from "{old_status.replace("_", " ").title()}" to "{new_status.replace("_", " ").title()}".', 'danger')
        logger.warning(f"[_perform_status_update] Access Denied: User {user.email} (Role: {user.role}) attempted invalid transition from {old_status} to {new_status} for order {order_id}")
        return False

    # Specific ownership checks (beyond role-based transitions)
    if user.role == 'customer' and order.customer_id != user.id:
        flash('Access denied. You can only manage your own orders.', 'danger')
        logger.warning(f"[_perform_status_update] Access Denied: Customer {user.email} attempted to modify order {order_id} not belonging to them.")
        return False
    
    if user.role == 'vendor':
        # Vendor can only approve/deliver orders that contain their products
        vendor_owns_product_in_order = False
        for item in order.items:
            product = products.get(item['product_id'])
            if product and product.vendor_id == user.id:
                vendor_owns_product_in_order = True
                break
        if not vendor_owns_product_in_order:
            flash('Access denied. This order does not contain your products.', 'danger')
            logger.warning(f"[_perform_status_update] Access Denied: Vendor {user.email} attempted to modify order {order_id} without owning products in it.")
            return False

    # Perform the actual status update in the models
    # The update_order_status in models.py is now a simple setter.
    logger.debug(f"[_perform_status_update] Calling models.update_order_status for order {order_id} from {old_status} to {new_status}")
    if update_order_status(order_id, new_status):
        flash(f'Order status updated from {old_status.replace("_", " ").title()} to {new_status.replace("_", " ").title()}.', 'success')
        logger.info(f"[_perform_status_update] Success: Order {order_id} status successfully updated from {old_status} to {new_status} by {user.email}")
        return True
    else:
        # This else block should ideally not be hit if update_order_status in models is just a setter,
        # but it's a fallback for unexpected model update failures.
        flash('Failed to update order status due to an internal error.', 'danger')
        logger.error(f"[_perform_status_update] Failed: models.update_order_status returned False for order {order_id} to {new_status} (unexpected).")
        return False


@app.route('/')
def index():
    # Validate session - if user_id exists but user doesn't, clear the session
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if not user:
            logger.warning(f"❌ Invalid session detected - user_id {session['user_id']} not found, clearing session")
            session.clear()
            flash('Your session has expired. Please log in again.', 'info')
        else:
            # Redirect logged-in users to their appropriate dashboard
            if user.role == 'admin':
                logger.info(f"🔄 Admin {user.username} redirected from homepage to admin dashboard")
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'vendor':
                logger.info(f"🔄 Vendor {user.username} redirected from homepage to seller dashboard")
                return redirect(url_for('seller_dashboard'))
            elif user.role == 'customer':
                # Customers can access the homepage
                logger.info(f"🏠 Customer {user.username} accessing homepage")
    
    # Get featured products from current data
    from models import products
    featured_products = get_featured_products(10)  # Get more featured products with promotional first
    promotional_products = get_promotional_products()  # Get active promotional products
    
    # Debug logging
    logger.info(f"🏠 Homepage - Total products in memory: {len(products)}")
    logger.info(f"🏠 Homepage - Featured products: {len(featured_products)}")
    logger.info(f"🏠 Homepage - Promotional products: {len(promotional_products)}")
    for i, product in enumerate(featured_products):
        logger.info(f"🏠 Product {i+1}: {product.name} - Active: {product.is_active} - Stock: {product.stock}")
    for promo in promotional_products:
        logger.info(f"🏠 Promotional product: {promo.name} - ${promo.price} → ${promo.promotional_price}")
    
    return render_template('index.html', products=featured_products, promotional_products=promotional_products, categories=CATEGORIES)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        logger.debug(f"🔐 Login attempt for email: {email}")
        
        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            logger.warning("❌ Login failed: Missing email or password")
            return render_template('login.html')
        
        # Normalize email for lookup
        email = email.lower().strip()
        user = get_user_by_email(email)
        
        if user:
            logger.debug(f"✅ Found user: {user.username} ({user.email}) with role: {user.role}")
            logger.debug(f"Stored password hash: {user.password_hash}")

            if user.check_password(password):
                session['user_id'] = user.id
                session['user_role'] = user.role
                flash(f'Welcome back, {user.username}!', 'success')
                logger.info(f"🎉 Successful login for user: {user.email} (role: {user.role})")
                
                # Redirect based on role
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.role == 'vendor':
                    return redirect(url_for('seller_dashboard'))
                else:
                    return redirect(url_for('customer_dashboard'))
            else:
                logger.warning(f"❌ Invalid password for user: {email}")
                flash('Invalid email or password.', 'danger')
        else:
            logger.warning(f"❌ User not found: {email}")
            logger.debug(f"Available users: {[u.email for u in users.values()]}")
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'customer')
        
        logger.debug(f"📝 Registration attempt for: {username} ({email}) as {role}")
        
        if not username or not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('register.html')
        
        # Check if user already exists
        if get_user_by_email(email):
            flash('Email already registered. Please use a different email or login.', 'danger')
            return render_template('register.html')
        
        # Create new user
        user = create_user(username, email, password, role)
        if user:
            session['user_id'] = user.id
            session['user_role'] = user.role
            flash('Registration successful! Welcome to Electronics Store!', 'success')
            logger.info(f"🎉 New user registered: {username} ({email}) as {role}")
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'vendor':
                return redirect(url_for('seller_dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        else:
            flash('Registration failed. Email may already be in use.', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        user = get_user_by_id(user_id)
        if user:
            logger.info(f"👋 User logged out: {user.email}")
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/clear_session')
def clear_session():
    """Clear the session completely - useful for testing"""
    session.clear()
    flash('Session cleared successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/force_logout')
def force_logout():
    # Clear session completely
    session.clear()
    
    # Clear any cookies
    response = redirect(url_for('index'))
    response.delete_cookie('session')
    
    flash('You have been logged out completely.', 'info')
    return response

@app.route('/clear_session_and_home')
def clear_session_and_home():
    """Clear session and go to homepage to test products display"""
    session.clear()
    flash('Session cleared. Testing homepage products display.', 'info')
    return redirect(url_for('index'))

@app.route('/reload_data')
def reload_data():
    """Force reload data from file"""
    from models import load_data
    success = load_data()
    if success:
        flash('Data reloaded successfully!', 'success')
    else:
        flash('Failed to reload data!', 'danger')
    return redirect(url_for('index'))

@app.route('/test_approve/<order_id>')
@admin_required
def test_approve(order_id):
    """Test route for approval - returns simple JSON response"""
    logger.info(f"[test_approve] Test route accessed for order {order_id}")
    return jsonify({'success': True, 'message': f'Test approval for order {order_id}'})

@app.route('/products')
def products_list():
    # Check if user is logged in and redirect admins/vendors
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            if user.role == 'admin':
                logger.info(f"🔄 Admin {user.username} redirected from products page to admin dashboard")
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'vendor':
                logger.info(f"🔄 Vendor {user.username} redirected from products page to seller dashboard")
                return redirect(url_for('seller_dashboard'))
            # Customers can access the products page
    
    category = request.args.get('category')
    search = request.args.get('search', '').lower()
    page = request.args.get('page', 1, type=int)
    per_page = 15  # Show 15 products per page (3 rows of 5 products each for full first page)
    
    product_list = get_products_by_category(category)
    
    if search:
        product_list = [p for p in product_list if search in p.name.lower() or search in p.description.lower()]
    
    # Get promotional products for the timer and spin wheel
    promotional_products = get_promotional_products()
    
    # Debug logging
    logger.info(f"🔍 Products page - Total products: {len(product_list)}")
    logger.info(f"🔍 Products page - Promotional products: {len(promotional_products)}")
    for promo in promotional_products:
        logger.info(f"🔍 Promotional product: {promo.name} - Promotional: {promo.is_promotional} - End date: {promo.promotional_end_date}")
    
    # Pagination
    total_products = len(product_list)
    total_pages = (total_products + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_products = product_list[start_idx:end_idx]
    
    return render_template('products.html', 
                         products=paginated_products, 
                         categories=CATEGORIES, 
                         selected_category=category, 
                         search=search,
                         promotional_products=promotional_products,
                         current_page=page,
                         total_pages=total_pages,
                         total_products=total_products,
                         per_page=per_page)

@app.route('/product/<product_id>')
def product_detail(product_id):
    # Check if user is logged in and redirect admins/vendors
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            if user.role == 'admin':
                logger.info(f"🔄 Admin {user.username} redirected from product detail page to admin dashboard")
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'vendor':
                logger.info(f"🔄 Vendor {user.username} redirected from product detail page to seller dashboard")
                return redirect(url_for('seller_dashboard'))
            # Customers can access the product detail page
    
    product = products.get(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products_list'))
    
    vendor = get_user_by_id(product.vendor_id)
    
    # Get product reviews and average rating
    reviews = get_product_reviews(product_id)
    average_rating = get_product_average_rating(product_id)
    
    # Process reviews to ensure proper formatting
    processed_reviews = []
    for review in reviews:
        processed_review = {
            'id': review.id if hasattr(review, 'id') else review.get('id', ''),
            'user_name': review.user_name if hasattr(review, 'user_name') else review.get('user_name', ''),
            'rating': review.rating if hasattr(review, 'rating') else review.get('rating', 0),
            'comment': review.comment if hasattr(review, 'comment') else review.get('comment', ''),
            'created_at': review.created_at if hasattr(review, 'created_at') else review.get('created_at', ''),
            'formatted_date': ''
        }
        
        # Format the date safely
        if processed_review['created_at']:
            if hasattr(processed_review['created_at'], 'strftime'):
                processed_review['formatted_date'] = processed_review['created_at'].strftime('%B %d, %Y')
            elif isinstance(processed_review['created_at'], str):
                processed_review['formatted_date'] = processed_review['created_at']
            else:
                processed_review['formatted_date'] = 'Recently'
        else:
            processed_review['formatted_date'] = 'Recently'
        
        processed_reviews.append(processed_review)
    
    return render_template('product_detail.html', 
                         product=product, 
                         vendor=vendor, 
                         reviews=processed_reviews, 
                         average_rating=average_rating)

@app.route('/cart') # This is the primary cart view endpoint
@role_required(['customer'])
def cart():
    user_id = session['user_id']
    user_cart_items = get_cart_items(user_id) # Use the helper function
    
    cart_with_products = []
    total = 0
    
    for item in user_cart_items:
        product = products.get(item.product_id)
        if product and product.is_active: # Ensure product is active
            item_total = product.price * item.quantity
            cart_with_products.append({
                'item': item,
                'product': product,
                'total': item_total
            })
            total += item_total
    
    return render_template('cart.html', cart_items=cart_with_products, total=total)

# Corrected add_to_cart_route
@app.route('/add_to_cart/<product_id>', methods=['GET', 'POST'])
@login_required
def add_to_cart_route(product_id):
    if session.get('user_role') != 'customer':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Only customers can add products to cart.'})
        flash('Only customers can add products to cart.', 'danger')
        return redirect(url_for('products_list'))
    
    user_id = session['user_id']
    product = products.get(product_id)
    
    if not product: # Check if product exists
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Product not found.'})
        flash('Product not found.', 'danger')
        return redirect(url_for('products_list'))

    if not product.is_active: # Check if product is active
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Product is currently unavailable.'})
        flash('Product is currently unavailable.', 'danger')
        return redirect(url_for('products_list'))

    # Attempt to add to cart, which now includes stock check
    if add_to_cart(user_id, product_id, quantity=1): # Pass quantity=1 for single add
        logger.info(f"🛒 Added product {product.name} to cart for user {user_id}")
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            cart_count = sum(item.quantity for item in get_cart_items(user_id)) # Use helper
            return jsonify({
                'success': True,
                'message': f'Added {product.name} to cart',
                'cart_count': cart_count
            })
        
        flash(f'Added {product.name} to your cart!', 'success')
        return redirect(url_for('products_list')) # Explicit redirect
    else:
        # add_to_cart returned False, meaning insufficient stock or other issue
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': f'Not enough stock for {product.name}. Available: {product.stock}'})
        flash(f'Not enough stock for {product.name}. Available: {product.stock}', 'warning')
        return redirect(url_for('products_list'))


@app.route('/update_cart_quantity/<product_id>', methods=['POST'])
@role_required(['customer'])
def update_cart_quantity(product_id):
    try:
        data = request.get_json()
        new_quantity = int(data.get('quantity', 1))
        
        if new_quantity < 1:
            return jsonify({'success': False, 'message': 'Quantity must be at least 1'})
        
        user_id = session['user_id']
        cart_key = (user_id, product_id)
        
        product = products.get(product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found.'})

        if product.stock < new_quantity: # Check stock before updating cart quantity
            return jsonify({'success': False, 'message': f'Not enough stock for {product.name}. Available: {product.stock}'})

        if cart_key in cart_items:
            cart_items[cart_key].quantity = new_quantity
            
            # Calculate new totals
            product = products.get(product_id)
            if product:
                item_total = product.price * new_quantity
                
                # Calculate cart total
                cart_total = sum(
                    products[item.product_id].price * item.quantity 
                    for key, item in cart_items.items() 
                    if key[0] == user_id and products.get(item.product_id)
                )
                
                return jsonify({
                    'success': True,
                    'item_total': item_total,
                    'cart_total': cart_total
                })
        
        return jsonify({'success': False, 'message': 'Item not found in cart'})
    except Exception as e:
        logger.error(f"Error updating cart quantity: {e}")
        return jsonify({'success': False, 'message': 'Server error'})

# This is the single, correct remove_from_cart route
@app.route('/remove_from_cart/<product_id>')
@role_required(['customer'])
def remove_from_cart(product_id):
    user_id = session['user_id']
    cart_key = (user_id, product_id)
    
    if cart_key in cart_items:
        product = products.get(product_id)
        product_name = product.name if product else 'Product'
        del cart_items[cart_key]
        flash(f'Removed {product_name} from your cart.', 'success')
    else:
        flash('Item not found in cart.', 'danger')
    
    return redirect(url_for('cart')) # Redirect to the 'cart' endpoint


@app.route('/clear_cart', methods=['POST'])
@role_required(['customer'])
def clear_cart():
    """Clear all items from the user's cart."""
    user_id = session['user_id']
    
    # Remove all cart items for this user
    cart_keys_to_remove = [key for key in cart_items.keys() if key[0] == user_id]
    for key in cart_keys_to_remove:
        del cart_items[key]
    
    flash('All items have been removed from your cart.', 'info')
    logger.info(f"🗑️ Cleared entire cart for user {user_id}")
    
    return redirect(url_for('cart'))


# Product management routes
@app.route('/toggle_product/<product_id>')
@role_required(['seller', 'admin'])
def toggle_product(product_id):
    product = products.get(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('index')) # Explicit redirect
    
    user = get_user_by_id(session['user_id'])
    # Check if seller owns the product or user is admin
    if user.role == 'seller' and product.seller_id != session['user_id']:
        flash('You can only manage your own products.', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    # Toggle product active status
    product.is_active = not product.is_active
    status = 'activated' if product.is_active else 'deactivated'
    
    flash(f'Product "{product.name}" has been {status}.', 'success')
    logger.info(f"🔄 Product {product.name} {status} by {user.email}")
    
    return redirect(url_for('seller_dashboard')) # Explicit redirect

@app.route('/delete_product/<product_id>')
@role_required(['seller', 'admin'])
def delete_product(product_id):
    product = products.get(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('index')) # Explicit redirect
    
    user = get_user_by_id(session['user_id'])
    # Check if seller owns the product or user is admin
    if user.role == 'seller' and product.seller_id != session['user_id']:
        flash('You can only delete your own products.', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    product_name = product.name
    del products[product_id]
    
    flash(f'Product "{product_name}" has been deleted.', 'success')
    logger.info(f"🗑️ Product {product.name} deleted by {user.email}")
    
    return redirect(url_for('seller_dashboard') if user.role == 'seller' else url_for('admin_dashboard')) # Explicit redirect

@app.route('/checkout', methods=['GET', 'POST'])
@role_required(['customer'])
def checkout():
    cart_items_list = get_cart_items(session['user_id'])
    if not cart_items_list:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart')) # Redirect to 'cart' endpoint
    
    if request.method == 'POST':
        # No payment validation needed here - payment will be collected on receipt page
        logger.info(f"🛒 Processing checkout for user {session['user_id']}")
        
        # Process checkout
        order_items = []
        total_amount = 0
        
        for item in cart_items_list:
            product = products.get(item.product_id)
            if product:
                # Use promotional price if available
                price = product.promotional_price if product.is_promotional and product.promotional_price else product.price
                item_total = price * item.quantity
                order_items.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'quantity': item.quantity,
                    'price': price,
                    'total': item_total
                })
                total_amount += item_total
        
        # Calculate subtotal (before discount)
        subtotal = total_amount
        
        # Apply discount code if provided
        discount_code = request.form.get('discount_code', '').strip()
        applied_discount_code = request.form.get('applied_discount_code', '').strip()
        applied_discount_percentage = request.form.get('applied_discount_percentage', '0')
        applied_discount_amount = request.form.get('applied_discount_amount', '0')
        final_total_amount = request.form.get('final_total_amount', str(total_amount))
        
        # Debug logging for discount information
        logger.info(f"🔍 Discount debug - discount_code: '{discount_code}', applied_discount_code: '{applied_discount_code}', applied_discount_percentage: '{applied_discount_percentage}', applied_discount_amount: '{applied_discount_amount}', final_total_amount: '{final_total_amount}'")
        
        discount_amount = 0
        discount_percentage = 0
        applied_discount = None
        
        # Use the discount information from the form if available
        if applied_discount_code and applied_discount_percentage and applied_discount_amount:
            try:
                discount_percentage = float(applied_discount_percentage)
                discount_amount = float(applied_discount_amount)
                total_amount = float(final_total_amount)
                applied_discount = True
                # Mark discount code as used
                use_discount_code(applied_discount_code, session['user_id'])
                flash(f'Discount code {applied_discount_code} applied! You saved ${discount_amount:.2f}', 'success')
                logger.info(f"🎫 Applied discount from form: {applied_discount_code} ({discount_percentage}%) - saved ${discount_amount:.2f}")
            except ValueError:
                flash('Invalid discount information. Please try again.', 'warning')
                logger.error(f"❌ Invalid discount values: percentage={applied_discount_percentage}, amount={applied_discount_amount}")
        elif discount_code:
            # Fallback to server-side validation if hidden fields are not set
            is_valid, discount_info = validate_discount_code(discount_code, session['user_id'])
            if is_valid:
                applied_discount = discount_info
                discount_percentage = applied_discount.discount_percentage
                discount_amount = (subtotal * discount_percentage) / 100
                total_amount -= discount_amount
                # Mark discount code as used
                use_discount_code(discount_code, session['user_id'])
                flash(f'Discount code {discount_code} applied! You saved ${discount_amount:.2f}', 'success')
                logger.info(f"🎫 Applied discount from validation: {discount_code} ({discount_percentage}%) - saved ${discount_amount:.2f}")
            else:
                flash(f'Invalid discount code: {discount_info}', 'warning')
                logger.warning(f"❌ Invalid discount code: {discount_code} - {discount_info}")
        else:
            logger.info(f"📦 No discount applied. Total amount: ${total_amount:.2f}")
        
        # Create order with 'pending' status and discount information
        logger.info(f"📦 Creating order with: total_amount=${total_amount:.2f}, discount_code={applied_discount_code if applied_discount else None}, discount_percentage={discount_percentage}, discount_amount=${discount_amount:.2f}, subtotal=${subtotal:.2f}")
        
        order = create_order(
            session['user_id'], 
            order_items, 
            total_amount,
            applied_discount_code if applied_discount else None,
            discount_percentage,
            discount_amount,
            subtotal
        )
        
        # Store order ID in session for payment processing
        session['pending_order_id'] = order.id
        
        flash('Order created successfully! Please proceed to payment.', 'success')
        logger.info(f"📦 Order {order.id} created successfully for user {session['user_id']} with status 'pending'")
        # Redirect to receipt where buyer can initiate payment
        return redirect(url_for('receipt', order_id=order.id))
    
    # Calculate total for GET request
    cart_with_products = []
    total = 0
    
    for item in cart_items_list:
        product = products.get(item.product_id)
        if product:
            # Use promotional price if available
            price = product.promotional_price if product.is_promotional and product.promotional_price else product.price
            item_total = price * item.quantity
            cart_with_products.append({
                'item': item,
                'product': product,
                'total': item_total
            })
            total += item_total
    
    return render_template('checkout.html', cart_items=cart_with_products, total=total)


@app.route('/receipt/<order_id>')
@login_required
def receipt(order_id):
    order = orders.get(order_id)
    if not order:
        flash('Order not found.', 'danger')
        logger.warning(f"❌ Receipt page: Order {order_id} not found when accessed.")
        return redirect(url_for('buyer_dashboard')) # Redirect to dashboard if order not found
    
    # Check if user has access to this order
    user = get_user_by_id(session['user_id'])
    if user and user.role == 'customer' and order.customer_id != user.id: # Compare with user.id, not session['user_id'] directly
        flash('Access denied.', 'danger')
        logger.warning(f"❌ Receipt page: Access denied for user {user.email} to order {order_id}.")
        return redirect(url_for('customer_dashboard'))
    
    buyer = get_user_by_id(order.customer_id)
    return render_template('receipt.html', order=order, buyer=buyer)

@app.route('/customer_dashboard')
@role_required(['customer'])
def customer_dashboard():
    user_orders = get_orders_by_customer(session['user_id'])
    logger.debug(f"📊 Customer dashboard loaded for user {session['user_id']}, {len(user_orders)} orders")
    return render_template('customer_dashboard.html', orders=user_orders)

@app.route('/seller_dashboard')
@role_required(['seller'])
def seller_dashboard():
    seller_products = get_products_by_vendor(session['user_id'])
    seller_orders = get_orders_by_vendor(session['user_id'])
    # Filter orders for seller approval using the helper function
    orders_pending_seller_approval_filtered = get_orders_pending_vendor_approval(session['user_id'])

    logger.debug(f"📊 Seller dashboard loaded for user {session['user_id']}, {len(seller_products)} products, {len(seller_orders)} orders")
    return render_template('seller_dashboard.html', 
                           products=seller_products, 
                           orders=seller_orders, 
                           orders_pending_seller_approval=orders_pending_seller_approval_filtered,
                           get_user_by_id=get_user_by_id)

@app.route('/admin_dashboard')
@role_required(['admin'])
def admin_dashboard():
    # Get current data
    from models import orders, users, products
    all_orders = list(orders.values())
    all_users = list(users.values())
    all_products = list(products.values())
    # Filter orders for admin approval using the helper function
    orders_pending_admin_approval_filtered = get_orders_pending_admin_approval()
    
    # Filter out admin_review orders from the "All Orders" table to avoid duplication
    # But include approved orders that should be visible in "All Orders"
    orders_for_all_orders_table = [order for order in all_orders if order.status != 'admin_review']

    # Debug logging to see what's happening
    logger.debug(f"📊 Admin dashboard loaded: {len(all_users)} users, {len(all_products)} products, {len(all_orders)} orders")
    logger.debug(f"📊 Orders pending admin approval: {len(orders_pending_admin_approval_filtered)}")
    logger.debug(f"📊 Orders for All Orders table: {len(orders_for_all_orders_table)}")
    
    # Log all order statuses for debugging
    for order in all_orders:
        logger.debug(f"📊 Order {order.id[:8]}... status: {order.status}")
    
    return render_template('admin_dashboard.html', 
                           orders=orders_for_all_orders_table, # Display filtered orders for admin
                           orders_pending_admin_approval=orders_pending_admin_approval_filtered,
                           users=all_users, 
                           products=all_products, 
                           users_dict=users)

@app.route('/add_product', methods=['GET', 'POST'])
@role_required(['seller'])
def add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        category = request.form.get('category', '')
        stock = request.form.get('stock', '0') # Get stock from form
        
        if not name or not description or not price or not category or not stock:
            flash('Please fill in all fields.', 'danger')
            return render_template('add_product.html', categories=CATEGORIES)
        
        try:
            price = float(price)
            if price <= 0:
                flash('Price must be greater than 0.', 'danger')
                return render_template('add_product.html', categories=CATEGORIES)
            stock = int(stock) # Convert stock to int
            if stock < 0:
                flash('Stock cannot be negative.', 'danger')
                return render_template('add_product.html', categories=CATEGORIES)
        except ValueError:
            flash('Please enter valid numbers for price and stock.', 'danger')
            return render_template('add_product.html', categories=CATEGORIES)
        
        # Handle promotional settings
        is_promotional = 'is_promotional' in request.form
        promotional_price = None
        promotional_end_date = None
        
        if is_promotional:
            promotional_price_str = request.form.get('promotional_price', '').strip()
            promotional_end_date_str = request.form.get('promotional_end_date', '').strip()
            
            if promotional_price_str:
                try:
                    promotional_price = float(promotional_price_str)
                    if promotional_price <= 0 or promotional_price >= price:
                        flash('Promotional price must be greater than 0 and less than regular price.', 'danger')
                        return render_template('add_product.html', categories=CATEGORIES)
                except ValueError:
                    flash('Please enter a valid promotional price.', 'danger')
                    return render_template('add_product.html', categories=CATEGORIES)
            
            if promotional_end_date_str:
                try:
                    promotional_end_date = datetime.fromisoformat(promotional_end_date_str.replace('T', ' '))
                except ValueError:
                    flash('Please enter a valid promotion end date.', 'danger')
                    return render_template('add_product.html', categories=CATEGORIES)
            else:
                # Default to 7 days from now
                promotional_end_date = datetime.now() + timedelta(days=7)
        
        # Handle file upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                try:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_filename = filename
                    logger.info(f"📷 Image uploaded: {filename}")
                except Exception as e:
                    logger.error(f"❌ Failed to upload image: {e}")
                    flash('Failed to upload image, but product was created without image.', 'warning')
        
        product = create_product(name, description, price, category, session['user_id'], image_filename, stock, is_promotional, promotional_price, promotional_end_date)
        flash('Product added successfully!', 'success')
        logger.info(f"✅ Product added: {name} by user {session['user_id']}")
        return redirect(url_for('seller_dashboard'))
    
    return render_template('add_product.html', categories=CATEGORIES)

@app.route('/edit_product/<product_id>', methods=['GET', 'POST'])
@role_required(['seller'])
def edit_product(product_id):
    product = products.get(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    # Check if user owns this product
    if product.seller_id != session['user_id']:
        flash('You can only edit your own products.', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        category = request.form.get('category', '')
        stock = request.form.get('stock', '0')
        
        if not name or not description or not price or not category or not stock:
            flash('Please fill in all fields.', 'danger')
            return render_template('edit_product.html', product=product, categories=CATEGORIES)
        
        try:
            price = float(price)
            if price <= 0:
                flash('Price must be greater than 0.', 'danger')
                return render_template('edit_product.html', product=product, categories=CATEGORIES)
            stock = int(stock)
            if stock < 0:
                flash('Stock cannot be negative.', 'danger')
                return render_template('edit_product.html', product=product, categories=CATEGORIES)
        except ValueError:
            flash('Please enter valid numbers for price and stock.', 'danger')
            return render_template('edit_product.html', product=product, categories=CATEGORIES)
        
        # Handle promotional settings
        is_promotional = 'is_promotional' in request.form
        promotional_price = None
        promotional_end_date = None
        
        if is_promotional:
            promotional_price_str = request.form.get('promotional_price', '').strip()
            promotional_end_date_str = request.form.get('promotional_end_date', '').strip()
            
            if promotional_price_str:
                try:
                    promotional_price = float(promotional_price_str)
                    if promotional_price <= 0 or promotional_price >= price:
                        flash('Promotional price must be greater than 0 and less than regular price.', 'danger')
                        return render_template('edit_product.html', product=product, categories=CATEGORIES)
                except ValueError:
                    flash('Please enter a valid promotional price.', 'danger')
                    return render_template('edit_product.html', product=product, categories=CATEGORIES)
            
            if promotional_end_date_str:
                try:
                    promotional_end_date = datetime.fromisoformat(promotional_end_date_str.replace('T', ' '))
                except ValueError:
                    flash('Please enter a valid promotion end date.', 'danger')
                    return render_template('edit_product.html', product=product, categories=CATEGORIES)
            else:
                promotional_end_date = datetime.now() + timedelta(days=7)
        
        # Handle file upload
        image_filename = product.image_filename
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                try:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_filename = filename
                    logger.info(f"📷 Image uploaded: {filename}")
                except Exception as e:
                    logger.error(f"❌ Failed to upload image: {e}")
                    flash('Failed to upload image, but product was updated.', 'warning')
        
        # Update product
        product.name = name
        product.description = description
        product.price = price
        product.category = category
        product.stock = stock
        product.image_filename = image_filename
        product.is_promotional = is_promotional
        product.promotional_price = promotional_price
        product.promotional_end_date = promotional_end_date
        product.updated_at = datetime.now()
        
        flash('Product updated successfully!', 'success')
        logger.info(f"✅ Product updated: {name} by user {session['user_id']}")
        return redirect(url_for('seller_dashboard'))
    
    return render_template('edit_product.html', product=product, categories=CATEGORIES)

# Renamed the old update_order_status route to avoid conflicts
@app.route('/_update_order_status_route/<order_id>/<status>', methods=['GET'])
@role_required(['admin'])
def _update_order_status_route(order_id, status):
    # This route is now a generic status update, mostly for admin/seller direct changes.
    # The specific workflow steps use dedicated routes below.
    logger.debug(f"[_update_order_status_route] Admin attempting to change order {order_id} to {status}")
    logger.debug(f"[_update_order_status_route] Request headers: {dict(request.headers)}")
    logger.debug(f"[_update_order_status_route] Is AJAX: {request.headers.get('X-Requested-With') == 'XMLHttpRequest'}")
    
    try:
        user = get_user_by_id(session['user_id'])
        if not user:
            logger.warning(f"[_update_order_status_route] Authentication failed for user")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Authentication error'
                }), 401
            else:
                flash('Authentication error.', 'danger')
                return redirect(url_for('index'))

        logger.debug(f"[_update_order_status_route] Calling _perform_status_update for order {order_id} to {status}")
        result = _perform_status_update(order_id, status, session['user_id'])
        logger.debug(f"[_update_order_status_route] _perform_status_update result: {result}")
        
        if result:
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                logger.info(f"[_update_order_status_route] Returning JSON success for order {order_id}")
                return jsonify({
                    'success': True,
                    'message': f'Order status updated to {status.replace("_", " ").title()}'
                })
            else:
                # Fallback for non-AJAX requests
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.role == 'seller':
                    return redirect(url_for('seller_dashboard'))
                else:
                    return redirect(url_for('buyer_dashboard'))
        else:
            logger.warning(f"[_update_order_status_route] _perform_status_update failed for order {order_id}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Failed to update order status'
                }), 400
            else:
                # If _perform_status_update returned False, it already flashed a message.
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.role == 'seller':
                    return redirect(url_for('seller_dashboard'))
                else:
                    return redirect(url_for('buyer_dashboard'))
                    
    except Exception as e:
        logger.error(f"[_update_order_status_route] Error updating order {order_id} to {status}: {e}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': f'Error updating order status: {str(e)}'
            }), 500
        else:
            flash('Error updating order status', 'error')
            return redirect(url_for('admin_dashboard'))


@app.route('/order_comments/<order_id>', methods=['GET', 'POST'])
@login_required
def order_comments(order_id):
    order = orders.get(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    user = get_user_by_id(session['user_id'])
    
    if not user:
        flash('Access denied.', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    # Check access rights
    has_access = False
    if user.role == 'admin':
        has_access = True
    elif user.role == 'customer' and order.customer_id == user.id:
        has_access = True
    elif user.role == 'seller' or user.role == 'vendor':
        # Check if seller/vendor has products in this order
        for item in order.items:
            product = products.get(item['product_id'])
            if product and product.vendor_id == user.id:
                has_access = True
                break
    
    if not has_access:
        flash('Access denied.', 'danger')
        logger.warning(f"❌ Unauthorized comment access attempt by {user.email}")
        return redirect(url_for('customer_dashboard'))
    
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if message:
            add_order_comment(order_id, user.id, message, user.role)
            flash('Comment added successfully!', 'success')
            logger.info(f"💬 Comment added to order {order_id} by {user.email}")
        return redirect(url_for('order_comments', order_id=order_id))
    
    comments = get_order_comments(order_id)
    # Add username to comments
    for comment in comments:
        comment_user = get_user_by_id(comment.user_id)
        comment.username = comment_user.username if comment_user else 'Unknown User'
    
    buyer = get_user_by_id(order.customer_id)
    return render_template('order_comments.html', order=order, comments=comments, buyer=buyer, current_user=user)

# --- New Workflow Routes ---

@app.route('/checkout_payment/<order_id>', methods=['POST'])
@customer_required
def checkout_payment(order_id):
    """Handle customer payment and move order to receipt_pending"""
    logger.debug(f"[checkout_payment] Attempting payment for order {order_id}")
    logger.debug(f"[checkout_payment] Request method: {request.method}")
    logger.debug(f"[checkout_payment] Request form data: {dict(request.form)}")
    logger.debug(f"[checkout_payment] Request headers: {dict(request.headers)}")
    
    # Get the order to verify it exists and show payment details
    order = orders.get(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    # Verify this is the user's order and it's in pending status
    if order.customer_id != session['user_id']:
        flash('You can only pay for your own orders.', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    if order.status != 'pending':
        flash('This order cannot be paid for.', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    # Validate payment information
    payment_method = request.form.get('payment_method')
    logger.debug(f"[checkout_payment] Payment method received: '{payment_method}'")
    if not payment_method:
        logger.debug(f"[checkout_payment] No payment method provided")
        flash('Please select a payment method.', 'danger')
        return redirect(url_for('receipt', order_id=order_id))
    
    if payment_method == 'momo':
        # Validate mobile money payment details
        momo_number = request.form.get('momo_number', '').strip()
        momo_provider = request.form.get('momo_provider', '').strip()
        
        logger.debug(f"[checkout_payment] MoMo validation - number: '{momo_number}', provider: '{momo_provider}'")
        
        if not momo_number:
            logger.debug(f"[checkout_payment] MoMo number missing")
            flash('Please enter your mobile money number.', 'danger')
            return redirect(url_for('receipt', order_id=order_id))
        
        if not momo_provider:
            logger.debug(f"[checkout_payment] MoMo provider missing")
            flash('Please select your mobile money provider.', 'danger')
            return redirect(url_for('receipt', order_id=order_id))
        
        # Validate mobile number format (basic validation)
        if not momo_number.isdigit() or len(momo_number) < 10:
            flash('Please enter a valid mobile money number.', 'danger')
            return redirect(url_for('receipt', order_id=order_id))
        
        logger.info(f"💳 Mobile money payment: {momo_provider} - {momo_number}")
        
    elif payment_method == 'credit_card':
        # Validate credit card payment details
        card_number = request.form.get('card_number', '').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
        cvv = request.form.get('cvv', '').strip()
        
        if not card_number:
            flash('Please enter your card number.', 'danger')
            return redirect(url_for('receipt', order_id=order_id))
        
        if not expiry_date:
            flash('Please enter your card expiry date.', 'danger')
            return redirect(url_for('receipt', order_id=order_id))
        
        if not cvv:
            flash('Please enter your card CVV.', 'danger')
            return redirect(url_for('receipt', order_id=order_id))
        
        # Basic card number validation (should be 13-19 digits)
        card_number_clean = card_number.replace(' ', '')
        if not card_number_clean.isdigit() or len(card_number_clean) < 13 or len(card_number_clean) > 19:
            flash('Please enter a valid card number.', 'danger')
            return redirect(url_for('receipt', order_id=order_id))
        
        logger.info(f"💳 Credit card payment: {card_number[:4]}****")
    
    # Log payment details for debugging
    logger.info(f"💳 Processing payment for order {order_id}")
    logger.info(f"💳 Order total: ${order.total_amount:.2f}")
    if order.discount_code:
        logger.info(f"💳 Discount applied: {order.discount_code} ({order.discount_percentage}%) - Saved: ${order.discount_amount:.2f}")
    
    # Update order status to receipt_pending
    success = _perform_status_update(order_id, 'receipt_pending', session['user_id'])
    
    if success:
        # Clear the cart only after successful payment
        cart_items_list = get_cart_items(session['user_id'])
        for item in cart_items_list:
            cart_key = (session['user_id'], item.product_id)
            if cart_key in cart_items:
                del cart_items[cart_key]
        
        # Clear the pending order from session
        session.pop('pending_order_id', None)
        
        # Log successful payment
        logger.info(f"💳 Payment successful for order {order_id}. Cart cleared for user {session['user_id']}")
        
        # Show success message and redirect to customer dashboard
        flash('Payment successful! Your order has been submitted for processing.', 'success')
        return redirect(url_for('customer_dashboard'))
    else:
        flash('Payment failed. Please try again.', 'danger')
        return redirect(url_for('receipt', order_id=order_id))

@app.route('/vendor_approve_receipt/<order_id>', methods=['POST'])
@vendor_required
def vendor_approve_receipt(order_id):
    """Vendor approves receipt and sends to admin"""
    logger.debug(f"[vendor_approve_receipt] Attempting approval for order {order_id}")
    _perform_status_update(order_id, 'admin_review', session['user_id'])
    return redirect(url_for('seller_dashboard'))

@app.route('/admin_approve_order/<order_id>', methods=['POST'])
@admin_required
def admin_approve_order(order_id):
    """Admin approves order for delivery"""
    logger.info(f"[admin_approve_order] ⚡ Route accessed for order {order_id}")
    logger.debug(f"[admin_approve_order] Attempting approval for order {order_id}")
    logger.debug(f"[admin_approve_order] Request headers: {dict(request.headers)}")
    logger.debug(f"[admin_approve_order] Is AJAX: {request.headers.get('X-Requested-With') == 'XMLHttpRequest'}")
    logger.debug(f"[admin_approve_order] Request method: {request.method}")
    logger.debug(f"[admin_approve_order] Request URL: {request.url}")
    
    try:
        logger.debug(f"[admin_approve_order] Calling _perform_status_update for order {order_id}")
        result = _perform_status_update(order_id, 'approved', session['user_id'])
        logger.debug(f"[admin_approve_order] _perform_status_update result: {result}")
        
        if result:
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                logger.info(f"[admin_approve_order] Returning JSON success for order {order_id}")
                return jsonify({
                    'success': True,
                    'message': 'Order approved successfully!'
                })
            else:
                # Fallback for non-AJAX requests
                return redirect(url_for('admin_dashboard'))
        else:
            logger.warning(f"[admin_approve_order] _perform_status_update failed for order {order_id}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Failed to approve order'
                }), 400
            else:
                flash('Error approving order', 'error')
                return redirect(url_for('admin_dashboard'))
            
    except Exception as e:
        logger.error(f"[admin_approve_order] Error approving order {order_id}: {e}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': f'Error approving order: {str(e)}'
            }), 500
        else:
            flash('Error approving order', 'error')
            return redirect(url_for('admin_dashboard'))

@app.route('/admin_delete_order/<order_id>', methods=['POST'])
@admin_required
def admin_delete_order(order_id):
    """Delete a cancelled order (admin only)."""
    try:
        logger.info(f"🗑️ Admin attempting to delete order {order_id}")
        
        # Check if order exists
        order = orders.get(order_id)
        if not order:
            logger.warning(f"🗑️ Order {order_id} not found for deletion")
            return jsonify({'success': False, 'message': 'Order not found'})
        
        # Check if order is cancelled
        if order.status != 'cancelled':
            logger.warning(f"🗑️ Order {order_id} is not cancelled (status: {order.status}), cannot delete")
            return jsonify({'success': False, 'message': 'Only cancelled orders can be deleted'})
        
        # Delete the order using the models function
        from models import delete_order
        if delete_order(order_id):
            logger.info(f"🗑️ Order {order_id} deleted successfully")
        else:
            logger.error(f"🗑️ Failed to delete order {order_id}")
            return jsonify({'success': False, 'message': 'Failed to delete order'})
        
        return jsonify({'success': True, 'message': 'Order deleted successfully'})
    except Exception as e:
        logger.error(f"🗑️ Error in admin_delete_order: {e}")
        return jsonify({'success': False, 'message': f'Error deleting order: {str(e)}'})

@app.route('/customer_confirm_delivery/<order_id>', methods=['POST'])
@customer_required
def customer_confirm_delivery(order_id):
    """Customer confirms delivery completion"""
    logger.debug(f"[customer_confirm_delivery] Attempting delivery confirmation for order {order_id}")
    _perform_status_update(order_id, 'delivered', session['user_id'])
    return redirect(url_for('customer_dashboard'))

@app.route('/spin_wheel_result', methods=['POST'])
def spin_wheel_result():
    """Handle spin wheel result and create discount code."""
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Check if user is logged in
    if 'user_id' not in session:
        if is_ajax:
            return jsonify({'error': 'Not logged in', 'status': 'login_required'}), 401
        else:
            return redirect(url_for('login'))
    
    try:
        user_id = session['user_id']
        logger.info(f"🎯 Spin wheel result requested for user {user_id}")
        
        # Check if user can spin (max 3 spins per 5 minutes)
        if not can_user_spin(user_id):
            logger.warning(f"🎯 User {user_id} cannot spin - max reached")
            return jsonify({
                'success': False, 
                'message': 'You have reached the maximum of 3 spins per 5 minutes. Please try again later!'
            })
        
        # Get the expected discount from the frontend
        data = request.get_json()
        expected_discount = data.get('expected_discount', 0) if data else 0
        logger.info(f"🎯 Expected discount from frontend: {expected_discount}%")
        
        # Get the next spin number (1, 2, or 3)
        spin_number = get_next_spin_number(user_id)
        logger.info(f"🎯 Spin number for user {user_id}: {spin_number}")
        
        # Use the expected discount from the frontend (where the wheel actually landed)
        result_discount = expected_discount
        logger.info(f"🎯 Final result discount for user {user_id}: {result_discount}%")
        
        # Record the spin attempt
        try:
            record_spin_attempt(user_id, spin_number, result_discount)
            logger.info(f"🎯 Spin attempt recorded for user {user_id}")
        except Exception as record_error:
            logger.error(f"🎯 Error recording spin attempt: {record_error}")
            return jsonify({'success': False, 'message': f'Error recording spin attempt: {str(record_error)}'})
        
        # Handle NO DISCOUNT case
        if result_discount == 0:
            logger.info(f"🎯 User {user_id} got NO DISCOUNT")
            return jsonify({
                'success': True,
                'message': 'Better luck next time! You didn\'t win a discount this time.',
                'discount_code': None,
                'discount_percentage': 0,
                'spin_number': spin_number
            })
        
        # Create discount code for winning spins
        if result_discount not in [5, 10, 15, 20, 25, 30, 50]:
            logger.error(f"🎯 Invalid discount percentage: {result_discount}")
            return jsonify({'success': False, 'message': f'Invalid discount percentage: {result_discount}'})
        
        try:
            discount = create_discount_code(result_discount, user_id)
            logger.info(f"🎯 Discount code created for user {user_id}: {discount.code}")
        except Exception as discount_error:
            logger.error(f"🎯 Error creating discount code: {discount_error}")
            return jsonify({'success': False, 'message': f'Error creating discount code: {str(discount_error)}'})
        
        return jsonify({
            'success': True,
            'message': f'Congratulations! You won {result_discount}% discount!',
            'discount_code': discount.code,
            'discount_percentage': result_discount,
            'spin_number': spin_number
        })
    except Exception as e:
        logger.error(f"🎯 Error in spin wheel result: {e}")
        import traceback
        logger.error(f"🎯 Full traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error processing spin wheel result: {str(e)}'})

@app.route('/check_spin_status')
def check_spin_status():
    """Check if user can spin and return current spin count."""
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Check if user is logged in
    if 'user_id' not in session:
        if is_ajax:
            return jsonify({'error': 'Not logged in', 'status': 'login_required'}), 401
        else:
            return redirect(url_for('login'))
    
    try:
        user_id = session['user_id']
        recent_attempts = get_user_spin_attempts(user_id)
        can_spin = can_user_spin(user_id)
        next_spin_number = get_next_spin_number(user_id)
        
        logger.info(f"🎯 Spin status check for user {user_id}: can_spin={can_spin}, attempts={len(recent_attempts)}, next_spin={next_spin_number}")
        
        return jsonify({
            'can_spin': can_spin,
            'current_spins': len(recent_attempts),
            'next_spin_number': next_spin_number,
            'max_spins': 3
        })
    except Exception as e:
        logger.error(f"Error checking spin status: {e}")
        return jsonify({'error': 'Could not check spin status'})

@app.route('/reset_spin_attempts')
@login_required
def reset_spin_attempts():
    """Reset spin attempts for the current user (for testing)."""
    try:
        user_id = session['user_id']
        logger.info(f"🎯 Attempting to reset spin attempts for user {user_id}")
        logger.info(f"🎯 Current spin_attempts keys: {list(spin_attempts.keys())}")
        logger.info(f"🎯 User {user_id} in spin_attempts: {user_id in spin_attempts}")
        
        # Clear all spin attempts for all users (comprehensive reset)
        total_attempts = sum(len(attempts) for attempts in spin_attempts.values())
        spin_attempts.clear()
        logger.info(f"🎯 Cleared all spin attempts ({total_attempts} total attempts)")
        
        # Save the data to persist the changes
        try:
            # Import save_data here to avoid circular import issues
            import models
            models.save_data()
            logger.info(f"🎯 Data saved after resetting spin attempts")
            
            # Verify the reset worked by checking the data
            from models import load_data
            load_data()  # Reload to verify
            logger.info(f"🎯 After reload, spin_attempts has {len(spin_attempts)} users")
            
        except Exception as save_error:
            logger.error(f"Error saving data: {save_error}")
            # Continue anyway, the reset still worked in memory
        
        logger.info(f"🎯 Reset all spin attempts")
        return jsonify({'success': True, 'message': 'All spin attempts reset successfully!'})
    except Exception as e:
        logger.error(f"Error resetting spin attempts: {e}")
        return jsonify({'success': False, 'message': 'Error resetting spin attempts'})

@app.route('/validate_discount_code', methods=['POST'])
@login_required
def validate_discount_code_ajax():
    """Validate discount code via AJAX for real-time feedback."""
    try:
        data = request.get_json()
        discount_code = data.get('discount_code', '').strip()
        
        if not discount_code:
            return jsonify({'valid': False, 'message': 'Please enter a discount code'})
        
        is_valid, discount_info = validate_discount_code(discount_code, session['user_id'])
        
        if is_valid:
            return jsonify({
                'valid': True,
                'discount': {
                    'code': discount_code,
                    'percentage': discount_info.discount_percentage
                }
            })
        else:
            return jsonify({'valid': False, 'message': discount_info})
            
    except Exception as e:
        logger.error(f"Error validating discount code: {e}")
        return jsonify({'valid': False, 'message': 'Error validating discount code'})

@app.route('/cancel_pending_order/<order_id>', methods=['POST'])
@customer_required
def cancel_pending_order(order_id):
    """Cancel a pending order and clear cart, redirect to products page."""
    try:
        order = orders.get(order_id)
        if not order:
            flash('Order not found.', 'danger')
            return redirect(url_for('customer_dashboard'))
        
        # Verify this is the user's order and it's in pending status
        if order.customer_id != session['user_id']:
            flash('You can only cancel your own orders.', 'danger')
            return redirect(url_for('customer_dashboard'))
        
        if order.status != 'pending':
            flash('Order cannot be cancelled.', 'danger')
            return redirect(url_for('customer_dashboard'))
        
        # Don't clear the cart when cancelling an order - let user keep their items
        # The cart should only be cleared after successful payment
        
        # Delete the pending order
        if order_id in orders:
            del orders[order_id]
        
        # Clear the pending order from session
        session.pop('pending_order_id', None)
        
        flash('Order cancelled successfully. Your cart items are still available.', 'info')
        logger.info(f"❌ Pending order {order_id} cancelled for user {session['user_id']}")
        
        return redirect(url_for('customer_dashboard'))
        
    except Exception as e:
        logger.error(f"Error cancelling pending order: {e}")
        flash('Error cancelling order. Please try again.', 'danger')
        return redirect(url_for('customer_dashboard'))

# Debug route to check system status
@app.route('/debug/status')
def debug_status():
    # Add session debugging
    session_info = {
        'user_id': session.get('user_id'),
        'user_role': session.get('user_role'),
        'session_keys': list(session.keys())
    }
    
    if session.get('user_id'):
        user = get_user_by_id(session['user_id'])
        if user:
            session_info['current_user'] = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        else:
            session_info['current_user'] = 'User not found in database'
    else:
        session_info['current_user'] = 'No user logged in'
    
    # Also check products
    promotional_products = get_promotional_products()
    featured_products = get_featured_products(10)
    session_info['featured_products_count'] = len(featured_products)
    session_info['featured_products'] = [{'name': p.name, 'active': p.is_active, 'stock': p.stock} for p in featured_products]
    
    return jsonify(session_info)
    
    # Get current user's spin attempts
    current_user_spins = []
    can_spin = False
    if 'user_id' in session:
        from models import get_user_spin_attempts, can_user_spin
        current_user_spins = get_user_spin_attempts(session['user_id'])
        can_spin = can_user_spin(session['user_id'])
    
    # Get order status details
    orders_by_status = {}
    pending_admin_approval = []
    
    for order_id, order in orders.items():
        status = order.status
        if status not in orders_by_status:
            orders_by_status[status] = []
        orders_by_status[status].append({
            'id': order_id[:8] + '...',
            'buyer_id': order.buyer_id,
            'total_amount': order.total_amount
        })
        
        if status == 'admin_review':
            pending_admin_approval.append({
                'id': order_id[:8] + '...',
                'buyer_id': order.buyer_id,
                'total_amount': order.total_amount
            })
    
    status = {
        'users_count': len(users),
        'products_count': len(products),
        'orders_count': len(orders),
        'cart_items_count': len(cart_items),
        'promotional_products_count': len(promotional_products),
        'featured_products_count': len(featured_products),
        'spin_attempts_total': len(spin_attempts),
        'spin_attempts_keys': list(spin_attempts.keys()),
        'current_user_spins': [
            {
                'spin_number': attempt.spin_number,
                'result_discount': attempt.result_discount,
                'timestamp': attempt.timestamp.isoformat()
            } for attempt in current_user_spins
        ],
        'current_user_can_spin': can_spin,
        'current_user_spin_count': len(current_user_spins),
        'promotional_products': [
            {
                'name': p.name,
                'price': p.price,
                'promotional_price': p.promotional_price,
                'is_promotional': p.is_promotional,
                'promotional_end_date': str(p.promotional_end_date) if p.promotional_end_date else None
            } for p in promotional_products
        ],
        'users': [{'email': u.email, 'role': u.role} for u in users.values()],
        'session': dict(session),
        'orders_by_status': orders_by_status,
        'pending_admin_approval': pending_admin_approval
    }
    
    return jsonify(status)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    # Log the original error that led to 404
    logger.error(f"❌ 404 Not Found: {request.url}. Referrer: {request.referrer}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"❌ Server error: {error}")
    return render_template('500.html'), 500

logger.info("🚀 Routes initialized successfully")

@app.route('/about')
def about():
    """About Us page"""
    return render_template('about.html')

@app.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')

@app.route('/categories')
def categories():
    """Categories page - browse products by category"""
    category = request.args.get('category')
    if category:
        return redirect(url_for('products_list', category=category))
    
    # Get product counts for each category
    category_counts = {}
    for cat in CATEGORIES:
        category_products = get_products_by_category(cat)
        category_counts[cat] = len([p for p in category_products if p.is_active])
    
    return render_template('categories.html', categories=CATEGORIES, category_counts=category_counts)

@app.route('/deals')
def deals():
    """Deals and promotions page"""
    promotional_products = get_promotional_products()
    featured_products = get_featured_products(10)
    
    return render_template('deals.html', 
                         promotional_products=promotional_products,
                         featured_products=featured_products)

@app.route('/help')
def help_page():
    """Help and FAQ page"""
    return render_template('help.html')

@app.route('/privacy')
def privacy():
    """Privacy Policy page"""
    return render_template('privacy.html')

@app.route('/add_review/<product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    """Add a review to a product."""
    if session.get('user_role') != 'customer':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Only customers can add reviews.'})
        flash('Only customers can add reviews.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    product = products.get(product_id)
    
    if not product:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Product not found.'})
        flash('Product not found.', 'danger')
        return redirect(url_for('products_list'))
    
    # Get form data
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()
    
    # Validate input
    if not rating or rating < 1 or rating > 5:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please provide a valid rating (1-5 stars).'})
        flash('Please provide a valid rating (1-5 stars).', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    if not comment:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please provide a review comment.'})
        flash('Please provide a review comment.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Add the review
    try:
        review = add_product_review(product_id, user_id, rating, comment, user.username)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Review added successfully!',
                'review': {
                    'id': review.id,
                    'user_name': review.user_name,
                    'rating': review.rating,
                    'comment': review.comment,
                    'created_at': review.created_at.isoformat()
                }
            })
        
        flash('Review added successfully!', 'success')
        return redirect(url_for('product_detail', product_id=product_id))
        
    except Exception as e:
        logger.error(f"Error adding review: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Error adding review. Please try again.'})
        flash('Error adding review. Please try again.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

@app.route('/delete_review/<review_id>', methods=['POST'])
@admin_required
def delete_review(review_id):
    """Delete a product review (admin only)."""
    try:
        from models import delete_product_review
        deleted_review = delete_product_review(review_id)
        
        if deleted_review:
            # Save the changes
            from models import save_data
            save_data()
            
            flash('Review deleted successfully!', 'success')
            logger.info(f"🗑️ Admin {session['user_id']} deleted review {review_id}")
        else:
            flash('Review not found.', 'danger')
            logger.warning(f"❌ Admin {session['user_id']} attempted to delete non-existent review {review_id}")
        
        # Redirect back to the previous page or admin dashboard
        return redirect(request.referrer or url_for('admin_dashboard'))
        
    except Exception as e:
        logger.error(f"Error deleting review {review_id}: {e}")
        flash('Error deleting review. Please try again.', 'danger')
        return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/add_to_wishlist/<product_id>', methods=['POST'])
def add_to_wishlist(product_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Please log in to add items to wishlist'}), 401
            return redirect(url_for('login'))
        
        user = get_user_by_id(session['user_id'])
        if not user:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'User not found'}), 401
            return redirect(url_for('login'))
        
        # Check if product exists
        if product_id not in products:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        
        # Check if already in wishlist
        if product_id in user.wishlist:
            return jsonify({'success': False, 'message': 'Item already in wishlist'})
        
        # Add to wishlist
        user.wishlist.append(product_id)
        save_data()
        
        return jsonify({'success': True, 'message': 'Added to wishlist successfully'})
        
    except Exception as e:
        print(f"Error in add_to_wishlist: {e}")  # Debug print
        return jsonify({'success': False, 'message': f'Error adding to wishlist: {str(e)}'}), 500

@app.route('/remove_from_wishlist/<product_id>', methods=['POST'])
def remove_from_wishlist(product_id):
    # Check if user is logged in
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please log in to remove items from wishlist'}), 401
        return redirect(url_for('login'))
    
    user = get_user_by_id(session['user_id'])
    if not user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'User not found'}), 401
        return redirect(url_for('login'))
    
    if product_id in user.wishlist:
        user.wishlist.remove(product_id)
        save_data()
        return jsonify({'success': True, 'message': 'Removed from wishlist successfully'})
    else:
        return jsonify({'success': False, 'message': 'Item not found in wishlist'})

@app.route('/wishlist')
@login_required
def wishlist():
    user = get_user_by_id(session['user_id'])
    wishlist_products = [products[pid] for pid in user.wishlist if pid in products]
    return render_template('wishlist.html', products=wishlist_products)
