from flask import render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from app import app
from models import (users, products, orders, cart_items, order_comments as order_comments_data, 
                    create_user, get_user_by_email, get_user_by_id, create_product, 
                    get_products_by_category, get_products_by_seller, add_to_cart, 
                    get_cart_items, create_order, get_orders_by_buyer, get_orders_by_seller,
                    add_order_comment, get_order_comments)

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

@app.route('/')
def index():
    featured_products = list(products.values())[:6]  # Show first 6 products
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
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'seller':
                return redirect(url_for('seller_dashboard'))
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
        flash('Registration successful!', 'success')
        
        # Redirect based on role
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'seller':
            return redirect(url_for('seller_dashboard'))
        else:
            return redirect(url_for('buyer_dashboard'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/clear_session')
def clear_session():
    """Debug route to manually clear sessions"""
    session.clear()
    flash('Session cleared successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/products')
def products_list():
    category = request.args.get('category')
    search = request.args.get('search', '').lower()
    
    product_list = get_products_by_category(category)
    
    if search:
        product_list = [p for p in product_list if search in p.name.lower() or search in p.description.lower()]
    
    return render_template('products.html', products=product_list, categories=CATEGORIES, selected_category=category, search=search)

@app.route('/product/<product_id>')
def product_detail(product_id):
    product = products.get(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products_list'))
    
    seller = get_user_by_id(product.seller_id)
    return render_template('product_detail.html', product=product, seller=seller)

@app.route('/add_to_cart/<product_id>')
@login_required
def add_to_cart_route(product_id):
    if session.get('user_role') != 'buyer':
        flash('Only buyers can add items to cart.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    product = products.get(product_id)
    if not product:
        flash('Product not found.', 'danger')
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
        product = products.get(item.product_id)
        if product:
            item_total = product.price * item.quantity
            cart_with_products.append({
                'item': item,
                'product': product,
                'total': item_total
            })
            total += item_total
    
    return render_template('cart.html', cart_items=cart_with_products, total=total)

@app.route('/remove_from_cart/<item_id>')
@role_required(['buyer'])
def remove_from_cart(item_id):
    if item_id in cart_items:
        del cart_items[item_id]
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
            product = products.get(item.product_id)
            if product:
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
        for item in cart_items_list:
            if item.id in cart_items:
                del cart_items[item.id]
        
        flash('Order placed successfully!', 'success')
        return redirect(url_for('receipt', order_id=order.id))
    
    # Calculate total for GET request
    cart_with_products = []
    total = 0
    
    for item in cart_items_list:
        product = products.get(item.product_id)
        if product:
            item_total = product.price * item.quantity
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
        return redirect(url_for('buyer_dashboard'))
    
    # Check if user has access to this order
    user = get_user_by_id(session['user_id'])
    if user and user.role == 'buyer' and order.buyer_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('buyer_dashboard'))
    
    buyer = get_user_by_id(order.buyer_id)
    return render_template('receipt.html', order=order, buyer=buyer)

@app.route('/buyer_dashboard')
@role_required(['buyer'])
def buyer_dashboard():
    user_orders = get_orders_by_buyer(session['user_id'])
    return render_template('buyer_dashboard.html', orders=user_orders)

@app.route('/seller_dashboard')
@role_required(['seller'])
def seller_dashboard():
    seller_products = get_products_by_seller(session['user_id'])
    seller_orders = get_orders_by_seller(session['user_id'])
    
    return render_template('seller_dashboard.html', products=seller_products, orders=seller_orders)

@app.route('/admin_dashboard')
@role_required(['admin'])
def admin_dashboard():
    all_orders = list(orders.values())
    all_users = list(users.values())
    all_products = list(products.values())
    
    return render_template('admin_dashboard.html', orders=all_orders, users=all_users, products=all_products, users_dict=users)

@app.route('/add_product', methods=['GET', 'POST'])
@role_required(['seller'])
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
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        product = create_product(name, description, price, category, session['user_id'], image_filename)
        flash('Product added successfully!', 'success')
        return redirect(url_for('seller_dashboard'))
    
    return render_template('add_product.html', categories=CATEGORIES)

@app.route('/update_order_status/<order_id>/<status>')
@login_required
def update_order_status(order_id, status):
    order = orders.get(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    user = get_user_by_id(session['user_id'])
    
    # Only admin can update to any status, sellers can only mark as delivered
    if user and (user.role == 'admin' or (user.role == 'seller' and status == 'delivered')):
        order.status = status
        order.updated_at = datetime.now()
        flash(f'Order status updated to {status}.', 'success')
    else:
        flash('Access denied.', 'danger')
    
    if user and user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('seller_dashboard'))

@app.route('/order_comments/<order_id>', methods=['GET', 'POST'])
@login_required
def order_comments(order_id):
    order = orders.get(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('buyer_dashboard'))
    
    user = get_user_by_id(session['user_id'])
    
    if not user:
        flash('Access denied.', 'danger')
        return redirect(url_for('buyer_dashboard'))
    
    # Check access rights
    has_access = False
    if user.role == 'admin':
        has_access = True
    elif user.role == 'buyer' and order.buyer_id == user.id:
        has_access = True
    elif user.role == 'seller':
        # Check if seller has products in this order
        for item in order.items:
            product = products.get(item['product_id'])
            if product and product.seller_id == user.id:
                has_access = True
                break
    
    if not has_access:
        flash('Access denied.', 'danger')
        return redirect(url_for('buyer_dashboard'))
    
    if request.method == 'POST':
        message = request.form['message']
        add_order_comment(order_id, user.id, message, user.role)
        flash('Comment added successfully!', 'success')
        return redirect(url_for('order_comments', order_id=order_id))
    
    comments = get_order_comments(order_id)
    # Add username to comments
    for comment in comments:
        comment_user = get_user_by_id(comment.user_id)
        comment.username = comment_user.username if comment_user else 'Unknown'
    
    return render_template('order_comments.html', order=order, comments=comments)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
