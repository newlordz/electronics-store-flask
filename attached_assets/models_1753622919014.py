from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db
import logging

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='buyer')  # buyer, seller, admin
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='seller', lazy=True)
    orders_as_buyer = db.relationship('Order', backref='buyer', lazy=True)
    cart_items = db.relationship('CartItem', backref='user', lazy=True)
    order_comments = db.relationship('OrderComment', backref='commenter', lazy=True)
    
    def __init__(self, username, email, password, role='buyer'):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.role = role
        self.status = 'approved' if role in ['buyer', 'admin'] else 'pending'
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    image_filename = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price),
            'category': self.category,
            'seller_id': self.seller_id,
            'image_filename': self.image_filename,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
        
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'added_at': self.added_at.isoformat()
        }

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='created')  # created, seller_approved, admin_approved, delivered, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('OrderComment', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'buyer_id': self.buyer_id,
            'total_amount': float(self.total_amount),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relationships
    product = db.relationship('Product', backref='order_items')
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'price_at_time': float(self.price_at_time)
        }

class OrderComment(db.Model):
    __tablename__ = 'order_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    user_role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user_id': self.user_id,
            'message': self.message,
            'user_role': self.user_role,
            'created_at': self.created_at.isoformat()
        }

# Helper functions for database operations
def create_user(username, email, password, role='buyer'):
    user = User(username=username, email=email, password=password, role=role)
    db.session.add(user)
    db.session.commit()
    return user

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def get_user_by_id(user_id):
    return User.query.get(user_id)

def create_product(name, description, price, category, seller_id, image_filename=None):
    product = Product(
        name=name,
        description=description,
        price=price,
        category=category,
        seller_id=seller_id,
        image_filename=image_filename
    )
    db.session.add(product)
    db.session.commit()
    return product

def get_products_by_seller(seller_id):
    return Product.query.filter_by(seller_id=seller_id).all()

def get_active_products():
    return Product.query.filter_by(is_active=True).all()

def get_product_by_id(product_id):
    return Product.query.get(product_id)

def add_to_cart(user_id, product_id, quantity=1):
    # Check if item already exists in cart
    existing_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if existing_item:
        existing_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
    db.session.commit()
    return True

def get_cart_items(user_id):
    return CartItem.query.filter_by(user_id=user_id).all()

def clear_cart(user_id):
    CartItem.query.filter_by(user_id=user_id).delete()
    db.session.commit()

def create_order(buyer_id, items, total_amount):
    order = Order(buyer_id=buyer_id, total_amount=total_amount)
    db.session.add(order)
    db.session.flush()  # Get the order ID
    
    # Add order items
    for item_data in items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data['product_id'],
            quantity=item_data['quantity'],
            price_at_time=item_data['price']
        )
        db.session.add(order_item)
    
    db.session.commit()
    return order

def get_orders_by_buyer(buyer_id):
    return Order.query.filter_by(buyer_id=buyer_id).all()

def get_orders_by_seller(seller_id):
    # Get orders that contain products from this seller
    return db.session.query(Order).join(OrderItem).join(Product).filter(Product.seller_id == seller_id).distinct().all()

def get_order_by_id(order_id):
    return Order.query.get(order_id)

def add_order_comment(order_id, user_id, message, user_role):
    comment = OrderComment(
        order_id=order_id,
        user_id=user_id,
        message=message,
        user_role=user_role
    )
    db.session.add(comment)
    db.session.commit()
    return comment

def get_order_comments(order_id):
    return OrderComment.query.filter_by(order_id=order_id).order_by(OrderComment.created_at).all()

def get_pending_sellers():
    return User.query.filter_by(role='seller', status='pending').all()

def get_all_users():
    return User.query.all()

def get_all_orders():
    return Order.query.all()

def get_all_products():
    return Product.query.all()

def get_products_by_category(category=None):
    if category:
        return Product.query.filter_by(category=category, is_active=True).all()
    return get_active_products()

def update_user_status(user_id, status):
    user = User.query.get(user_id)
    if user:
        user.status = status
        db.session.commit()
        return user
    return None

def update_order_status(order_id, status):
    order = Order.query.get(order_id)
    if order:
        order.status = status
        db.session.commit()
        return order
    return None

def toggle_product_status(product_id):
    product = Product.query.get(product_id)
    if product:
        product.is_active = not product.is_active
        db.session.commit()
        return product
    return None

def init_default_data():
    """Initialize default admin user if no users exist"""
    if User.query.count() == 0:
        admin = create_user('admin', 'admin@electronics.com', 'admin123', 'admin')
        logging.info(f"Created admin user: {admin.email}")
        
        # Create some sample data for testing
        seller = create_user('seller1', 'seller@test.com', 'seller123', 'seller')
        seller.status = 'approved'
        buyer = create_user('buyer1', 'buyer@test.com', 'buyer123', 'buyer')
        
        db.session.commit()
        
        # Add some sample products
        laptop = create_product(
            'MacBook Pro 16"',
            'Powerful laptop for professionals with M2 chip',
            2499.99,
            'Laptops',
            seller.id,
            None
        )
        
        phone = create_product(
            'iPhone 15 Pro',
            'Latest iPhone with advanced camera system',
            999.99,
            'Smartphones',
            seller.id,
            None
        )
        
        logging.info("Created sample data for testing")