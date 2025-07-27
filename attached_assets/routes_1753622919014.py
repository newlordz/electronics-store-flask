from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from app import app
from models import (
    create_user, get_user_by_email, get_user_by_id, update_user_status,
    create_product, toggle_product_status, get_products_by_seller, add_to_cart, get_cart_items, 
    create_order, get_orders_by_buyer, get_orders_by_seller, add_order_comment, 
    get_order_comments, get_pending_sellers, get_active_products, get_product_by_id,
    clear_cart, get_order_by_id, update_order_status, get_all_users, get_all_orders, get_all_products,
    get_products_by_category, CartItem
)

# Categories for electronics
CATEGORIES = ['Laptops', 'Smartphones', 'Mice', 'Keyboards', 'Headphones', 'Tablets', 'Accessories']

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def role_required(roles):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user = get_user_by_id(session['user_id'])
            if not user or user.role not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

def approved_seller_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = get_user_by_id(session['user_id'])
        if not user or user.role != 'seller' or user.status != 'approved':
            flash('You must be an approved seller to access this page.', 'warning')
            return redirect(url_for('seller_approval'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    featured_products = get_active_products()[:8]  # Show first 8 active products
    return render_template('index.html', products=featured_products, categories=CATEGORIES)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = get_user_by_email(email)
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_role'] = user.role
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect based on role and status
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'seller':
                if user.status == 'approved':
                    return redirect(url_for('seller_dashboard'))
                else:
                    return redirect(url_for('seller_approval'))
            else:
                return redirect(url_for('buyer_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'buyer')
        
        # Check if user already exists
        if get_user_by_email(email):
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        
        # Create new user
        user = create_user(username, email, password, role)
        session['user_id'] = user.id
        session['user_role'] = user.role
        
        if role == 'seller':
            flash('Registration successful! Your seller account is pending approval.', 'info')
            return redirect(url_for('seller_approval'))
        else:
            flash('Registration successful!', 'success')
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('buyer_dashboard'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/seller_approval')
@role_required(['seller'])
def seller_approval():
    user = get_user_by_id(session['user_id'])
    return render_template('seller_approval.html', user=user)

@app.route('/products')
def products_list():
    category = request.args.get('category')
    search = request.args.get('search', '').lower()
    
    product_list = get_products_by_category(category)
    
    if search:
        product_list = [p for p in product_list if search in p.name.lower() or search in p.description.lower()]
    
    return render_template('products.html', products=product_list, categories=CATEGORIES, 
                         selected_category=category, search=search)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = get_product_by_id(product_id)
    if not product or not product.is_active:
        flash('Product not found.', 'danger')
        return redirect(url_for('products_list'))
    
    seller = get_user_by_id(product.seller_id)
    return render_template('product_detail.html', product=product, seller=seller)

@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart_route(product_id):
    if session.get('user_role') != 'buyer':
        flash('Only buyers can add items to cart.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    product = get_product_by_id(product_id)
    if not product or not product.is_active:
        flash('Product not found or not available.', 'danger')
        return redirect(url_for('products_list'))
    
    add_to_cart(session['user_id'], product_id)
    flash(f'{product.name} added to cart!', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/cart')
@role_required(['buyer'])
def cart():
    cart_items_list = get_cart_items(session['user_id'])
    cart_with_products = []
    total = 0
    
    for item in cart_items_list:
        product = get_product_by_id(item.product_id)
        if product and product.is_active:
            item_total = product.price * item.quantity
            cart_with_products.append({
                'item': item,
                'product': product,
                'total': item_total
            })
            total += item_total
    
    return render_template('cart.html', cart_items=cart_with_products, total=total)

@app.route('/remove_from_cart/<int:item_id>')
@role_required(['buyer'])
def remove_from_cart(item_id):
    # Delete cart item from database
    cart_item = CartItem.query.filter_by(id=item_id, user_id=session['user_id']).first()
    if cart_item:
        from app import db
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart.', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@role_required(['buyer'])
def checkout():
    cart_items_list = get_cart_items(session['user_id'])
    if not cart_items_list:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart'))
    
    if request.method == 'POST':
        # Process checkout
        order_items = []
        total_amount = 0
        
        for item in cart_items_list:
            product = get_product_by_id(item.product_id)
            if product and product.is_active:
                item_total = product.price * item.quantity
                order_items.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'quantity': item.quantity,
                    'price': product.price,
                    'total': item_total
                })
                total_amount += item_total
        
        # Create order
        order = create_order(session['user_id'], order_items, total_amount)
        
        # Clear cart
        clear_cart(session['user_id'])
        
        flash('Order placed successfully! Waiting for seller approval.', 'success')
        return redirect(url_for('receipt', order_id=order.id))
    
    # Calculate total for GET request
    cart_with_products = []
    total = 0
    
    for item in cart_items_list:
        product = get_product_by_id(item.product_id)
        if product and product.is_active:
            item_total = product.price * item.quantity
            cart_with_products.append({
                'item': item,
                'product': product,
                'total': item_total
            })
            total += item_total
    
    return render_template('checkout.html', cart_items=cart_with_products, total=total)

@app.route('/receipt/<int:order_id>')
@login_required
def receipt(order_id):
    order = get_order_by_id(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('buyer_dashboard'))
    
    # Check access permissions
    user = get_user_by_id(session['user_id'])
    has_access = False
    
    if user.role == 'admin':
        has_access = True
    elif user.role == 'buyer' and order.buyer_id == user.id:
        has_access = True
    elif user.role == 'seller':
        # Check if seller has products in this order
        for item in order.items:
            product = get_product_by_id(item.product_id)
            if product and product.seller_id == user.id:
                has_access = True
                break
    
    if not has_access:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    buyer = get_user_by_id(order.buyer_id)
    return render_template('receipt.html', order=order, buyer=buyer)

@app.route('/buyer_dashboard')
@role_required(['buyer'])
def buyer_dashboard():
    user_orders = get_orders_by_buyer(session['user_id'])
    return render_template('buyer_dashboard.html', orders=user_orders)

@app.route('/seller_dashboard')
@approved_seller_required
def seller_dashboard():
    seller_products = get_products_by_seller(session['user_id'])
    seller_orders = get_orders_by_seller(session['user_id'])
    
    return render_template('seller_dashboard.html', products=seller_products, orders=seller_orders)

@app.route('/admin_dashboard')
@role_required(['admin'])
def admin_dashboard():
    all_orders = get_all_orders()
    all_users = get_all_users()
    all_products = get_all_products()
    pending_sellers = get_pending_sellers()
    
    return render_template('admin_dashboard.html', orders=all_orders, users=all_users, 
                         products=all_products, pending_sellers=pending_sellers)

@app.route('/approve_seller/<int:user_id>')
@role_required(['admin'])
def approve_seller(user_id):
    user = update_user_status(user_id, 'approved')
    if user:
        flash(f'Seller {user.username} has been approved.', 'success')
    else:
        flash('Seller not found.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/reject_seller/<int:user_id>')
@role_required(['admin'])
def reject_seller(user_id):
    user = update_user_status(user_id, 'rejected')
    if user:
        flash(f'Seller {user.username} has been rejected.', 'warning')
    else:
        flash('Seller not found.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/add_product', methods=['GET', 'POST'])
@approved_seller_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        
        # Handle file upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Add timestamp to prevent filename conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        product = create_product(name, description, price, category, session['user_id'], image_filename)
        flash('Product added successfully!', 'success')
        return redirect(url_for('seller_dashboard'))
    
    return render_template('add_product.html', categories=CATEGORIES)

@app.route('/toggle_product/<int:product_id>')
@approved_seller_required
def toggle_product(product_id):
    # Check if the product belongs to the current seller
    product = get_product_by_id(product_id)
    if not product or product.seller_id != session['user_id']:
        flash('Product not found or access denied.', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    product = toggle_product_status(product_id)
    if product:
        status = "activated" if product.is_active else "deactivated"
        flash(f'Product {product.name} has been {status}.', 'success')
    else:
        flash('Product not found or access denied.', 'danger')
    return redirect(url_for('seller_dashboard'))

@app.route('/update_order_status/<int:order_id>/<status>')
@login_required
def update_order_status_route(order_id, status):
    order = get_order_by_id(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('index'))
    
    user = get_user_by_id(session['user_id'])
    
    # Define allowed status transitions
    allowed_transitions = {
        'seller': {'created': 'seller_approved'},
        'admin': {'seller_approved': 'admin_approved'},
        'buyer': {'admin_approved': 'delivered'}
    }
    
    # Check permissions and valid transitions
    can_update = False
    if user.role == 'admin':
        can_update = True
    elif user.role == 'seller' and status in allowed_transitions.get('seller', {}).values():
        # Check if seller has products in this order
        for item in order.items:
            product = get_product_by_id(item.product_id)
            if product and product.seller_id == user.id:
                can_update = True
                break
    elif user.role == 'buyer' and order.buyer_id == user.id and status in allowed_transitions.get('buyer', {}).values():
        can_update = True
    
    if can_update:
        update_order_status(order_id, status)
        flash(f'Order status updated to {status.replace("_", " ").title()}.', 'success')
    else:
        flash('Access denied or invalid status transition.', 'danger')
    
    # Redirect based on role
    if user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif user.role == 'seller':
        return redirect(url_for('seller_dashboard'))
    else:
        return redirect(url_for('buyer_dashboard'))

@app.route('/order_comments/<int:order_id>', methods=['GET', 'POST'])
@login_required
def order_comments(order_id):
    order = get_order_by_id(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('index'))
    
    user = get_user_by_id(session['user_id'])
    
    # Check access rights
    has_access = False
    if user.role == 'admin':
        has_access = True
    elif user.role == 'buyer' and order.buyer_id == user.id:
        has_access = True
    elif user.role == 'seller':
        # Check if seller has products in this order
        for item in order.items:
            product = get_product_by_id(item.product_id)
            if product and product.seller_id == user.id:
                has_access = True
                break
    
    if not has_access:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if message:
            add_order_comment(order_id, user.id, message, user.role)
            flash('Comment added successfully!', 'success')
        else:
            flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('order_comments', order_id=order_id))
    
    comments = get_order_comments(order_id)
    # Add user details to comments
    for comment in comments:
        comment_user = get_user_by_id(comment.user_id)
        comment.username = comment_user.username if comment_user else 'Unknown User'
    
    buyer = get_user_by_id(order.buyer_id)
    return render_template('order_comments.html', order=order, comments=comments, buyer=buyer)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
