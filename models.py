from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

# In-memory data storage for local development
users = {}
products = {}
orders = {}
cart_items = {}
order_comments = {}

class User:
    def __init__(self, username, email, password, role='buyer'):
        self.id = str(uuid.uuid4())
        self.username = username
        self.email = email.lower().strip()  # Normalize email
        self.password_hash = generate_password_hash(password)
        self.role = role  # buyer, seller, admin
        self.created_at = datetime.now()
        logger.debug(f"Created user: {username} ({self.email}) with role: {role}")
        
    def check_password(self, password):
        result = check_password_hash(self.password_hash, password)
        logger.debug(f"Password check for {self.email}: {result}")
        return result
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }

class Product:
    def __init__(self, name, description, price, category, seller_id, image_filename=None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.price = float(price)
        self.category = category
        self.seller_id = seller_id
        self.image_filename = image_filename
        self.created_at = datetime.now()
        self.is_active = True
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'seller_id': self.seller_id,
            'image_filename': self.image_filename,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }

class CartItem:
    def __init__(self, user_id, product_id, quantity=1):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.product_id = product_id
        self.quantity = quantity
        self.added_at = datetime.now()
        
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'added_at': self.added_at.isoformat()
        }

class Order:
    def __init__(self, buyer_id, items, total_amount):
        self.id = str(uuid.uuid4())
        self.buyer_id = buyer_id
        self.items = items  # List of {product_id, quantity, price}
        self.total_amount = total_amount
        self.status = 'created'  # created, paid, delivered
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self):
        return {
            'id': self.id,
            'buyer_id': self.buyer_id,
            'items': self.items,
            'total_amount': self.total_amount,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class OrderComment:
    def __init__(self, order_id, user_id, message, user_role):
        self.id = str(uuid.uuid4())
        self.order_id = order_id
        self.user_id = user_id
        self.message = message
        self.user_role = user_role
        self.created_at = datetime.now()
        
    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user_id': self.user_id,
            'message': self.message,
            'user_role': self.user_role,
            'created_at': self.created_at.isoformat()
        }

# Helper functions for data management
def create_user(username, email, password, role='buyer'):
    # Normalize email to lowercase for consistency
    email = email.lower().strip()
    
    # Check if user already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        logger.warning(f"Attempted to create duplicate user: {email}")
        return None
    
    user = User(username, email, password, role)
    users[user.id] = user
    logger.info(f"Created user: {username} ({email}) with role: {role}")
    return user

def get_user_by_email(email):
    # Normalize email for case-insensitive lookup
    email = email.lower().strip()
    for user in users.values():
        if user.email == email:
            return user
    logger.debug(f"User not found for email: {email}")
    return None

def get_user_by_id(user_id):
    return users.get(user_id)

def create_product(name, description, price, category, seller_id, image_filename=None):
    product = Product(name, description, price, category, seller_id, image_filename)
    products[product.id] = product
    logger.info(f"Created product: {name} by seller {seller_id}")
    return product

def get_products_by_category(category=None):
    if category:
        return [p for p in products.values() if p.category == category and p.is_active]
    return [p for p in products.values() if p.is_active]

def get_products_by_seller(seller_id):
    return [p for p in products.values() if p.seller_id == seller_id]

def add_to_cart(user_id, product_id, quantity=1):
    # Check if item already in cart
    for item in cart_items.values():
        if item.user_id == user_id and item.product_id == product_id:
            item.quantity += quantity
            logger.debug(f"Updated cart item quantity for user {user_id}, product {product_id}")
            return item
    
    # Create new cart item
    cart_item = CartItem(user_id, product_id, quantity)
    cart_items[cart_item.id] = cart_item
    logger.debug(f"Added new cart item for user {user_id}, product {product_id}")
    return cart_item

def get_cart_items(user_id):
    return [item for item in cart_items.values() if item.user_id == user_id]

def create_order(buyer_id, items, total_amount):
    order = Order(buyer_id, items, total_amount)
    orders[order.id] = order
    logger.info(f"Created order {order.id} for buyer {buyer_id}, total: ${total_amount}")
    return order

def get_orders_by_buyer(buyer_id):
    return [order for order in orders.values() if order.buyer_id == buyer_id]

def get_orders_by_seller(seller_id):
    seller_orders = []
    for order in orders.values():
        for item in order.items:
            product = products.get(item['product_id'])
            if product and product.seller_id == seller_id:
                seller_orders.append(order)
                break
    return seller_orders

def add_order_comment(order_id, user_id, message, user_role):
    comment = OrderComment(order_id, user_id, message, user_role)
    if order_id not in order_comments:
        order_comments[order_id] = []
    order_comments[order_id].append(comment)
    logger.debug(f"Added comment to order {order_id} by user {user_id}")
    return comment

def get_order_comments(order_id):
    return order_comments.get(order_id, [])

# Initialize with default users for testing
def init_data():
    global users, products
    
    # Clear existing data to prevent duplicates on reload
    if users:
        logger.info("Data already initialized, skipping...")
        return
    
    logger.info("Initializing default data...")
    
    try:
        # Create admin user
        admin = create_user('Admin User', 'admin@electronics.com', 'admin123', 'admin')
        if admin:
            logger.info(f"✅ Created admin user: {admin.email}")
        
        # Create test seller
        seller = create_user('Test Seller', 'seller@test.com', 'seller123', 'seller')
        if seller:
            logger.info(f"✅ Created seller user: {seller.email}")
        
        # Create test buyer
        buyer = create_user('Test Buyer', 'buyer@test.com', 'buyer123', 'buyer')
        if buyer:
            logger.info(f"✅ Created buyer user: {buyer.email}")
        
        # Only create products if we have a seller
        if seller:
            # Create some sample products
            laptop = create_product(
                "Gaming Laptop Pro", 
                "High-performance gaming laptop with RTX 4080 graphics card, Intel i9 processor, 32GB RAM, and 1TB NVMe SSD. Perfect for gaming, content creation, and professional work.", 
                1899.99, 
                "Laptops", 
                seller.id
            )
            
            smartphone = create_product(
                "Smartphone Ultra 5G", 
                "Latest flagship smartphone with 6.8-inch OLED display, triple camera system with 108MP main sensor, 5G connectivity, and 256GB storage.", 
                999.99, 
                "Smartphones", 
                seller.id
            )
            
            headphones = create_product(
                "Wireless Noise-Cancelling Headphones", 
                "Premium over-ear headphones with active noise cancellation, 30-hour battery life, and high-resolution audio support.", 
                299.99, 
                "Headphones", 
                seller.id
            )
            
            keyboard = create_product(
                "Mechanical Gaming Keyboard", 
                "RGB backlit mechanical keyboard with Cherry MX switches, programmable keys, and aluminum construction.", 
                149.99, 
                "Keyboards", 
                seller.id
            )
            
            mouse = create_product(
                "Gaming Mouse Pro", 
                "High-precision gaming mouse with 16000 DPI sensor, RGB lighting, and ergonomic design.", 
                79.99, 
                "Mice", 
                seller.id
            )
            
            tablet = create_product(
                "Tablet Pro 12-inch", 
                "Professional tablet with 12-inch Retina display, Apple M2 chip, and support for Apple Pencil and Magic Keyboard.", 
                1099.99, 
                "Tablets", 
                seller.id
            )
            
            logger.info("✅ Created sample products")
        
        logger.info("🎉 Data initialization completed successfully!")
        logger.info("=" * 50)
        logger.info("TEST ACCOUNTS:")
        logger.info("Admin: admin@electronics.com / admin123")
        logger.info("Seller: seller@test.com / seller123")
        logger.info("Buyer: buyer@test.com / buyer123")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"❌ Error during data initialization: {e}")
        raise

# Initialize data when module is imported
init_data()
