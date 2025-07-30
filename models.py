import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import json
import os

logger = logging.getLogger(__name__)

# Define the path for the data file
DATA_FILE = 'data.json'

# In-memory "databases" - these will be loaded from/saved to DATA_FILE
users = {}
products = {}
orders = {}
cart_items = {} # Stores (user_id, product_id) -> CartItem object
order_comments = {} # Stores order_id -> list of Comment objects
product_reviews = {} # Stores product_id -> list of Review objects
discount_codes = {} # Stores code -> DiscountCode object
spin_attempts = {} # Stores user_id -> list of SpinAttempt objects

# --- Helper for JSON serialization/deserialization ---
class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects and custom classes."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, (User, Product, CartItem, Order, OrderComment, ProductReview)):
            return obj.to_dict()
        return json.JSONEncoder.default(self, obj)

def object_hook(dct):
    """Custom JSON object hook to reconstruct objects from dicts."""
    if '__class__' in dct:
        class_name = dct['__class__']
        if class_name == 'User':
            user = User(dct['username'], dct['email'], 'dummy_password') # Password hash will be re-hashed if user updates password
            user.id = dct['id']
            user.password_hash = dct['password_hash'] # Restore actual hash
            user.role = dct['role']
            user.created_at = datetime.fromisoformat(dct['created_at'])
            user.updated_at = datetime.fromisoformat(dct['updated_at'])
            user.wishlist = dct.get('wishlist', []) # Restore wishlist
            return user
        elif class_name == 'Product':
            product = Product(dct['name'], dct['description'], dct['price'], dct['category'], dct['vendor_id'], dct['image_filename'])
            product.id = dct['id']
            product.is_active = dct['is_active']
            product.stock = dct.get('stock', 0) # Add stock with a default for old data
            product.is_promotional = dct.get('is_promotional', False)
            product.promotional_price = dct.get('promotional_price')
            product.promotional_end_date = datetime.fromisoformat(dct['promotional_end_date']) if dct.get('promotional_end_date') else None
            product.created_at = datetime.fromisoformat(dct['created_at'])
            product.updated_at = datetime.fromisoformat(dct['updated_at'])
            return product
        elif class_name == 'CartItem':
            cart_item = CartItem(dct['user_id'], dct['product_id'], dct['quantity'])
            cart_item.id = dct['id']
            cart_item.added_at = datetime.fromisoformat(dct['added_at'])
            return cart_item
        elif class_name == 'Order':
            order = Order(
                dct['customer_id'], 
                dct['items'], 
                dct['total_amount'],
                dct.get('discount_code'),
                dct.get('discount_percentage', 0),
                dct.get('discount_amount', 0),
                dct.get('subtotal', 0)
            )
            order.id = dct['id']
            order.status = dct['status']
            order.created_at = datetime.fromisoformat(dct['created_at'])
            order.updated_at = datetime.fromisoformat(dct['updated_at'])
            return order
        elif class_name == 'OrderComment':
            comment = OrderComment(dct['order_id'], dct['user_id'], dct['message'], dct['user_role'])
            comment.id = dct['id']
            comment.created_at = datetime.fromisoformat(dct['created_at'])
            return comment
        elif class_name == 'ProductReview':
            review = ProductReview(dct['product_id'], dct['user_id'], dct['rating'], dct['comment'], dct['user_name'])
            review.id = dct['id']
            review.created_at = datetime.fromisoformat(dct['created_at'])
            return review
        elif class_name == 'DiscountCode':
            discount = DiscountCode(dct['code'], dct['discount_percentage'], dct['user_id'])
            discount.id = dct['id']
            discount.is_used = dct.get('is_used', False)
            discount.created_at = datetime.fromisoformat(dct['created_at'])
            discount.expires_at = datetime.fromisoformat(dct['expires_at']) if dct.get('expires_at') else None
            return discount
        elif class_name == 'SpinAttempt':
            attempt = SpinAttempt(dct['user_id'], dct['spin_number'], dct['result_discount'], datetime.fromisoformat(dct['timestamp']))
            attempt.id = dct['id']
            return attempt
    return dct

# --- Add __class__ to objects before serialization ---
def add_class_info(obj):
    if isinstance(obj, User):
        obj_dict = obj.to_dict()
        obj_dict['password_hash'] = obj.password_hash # Include hash for User
        obj_dict['__class__'] = 'User'
        return obj_dict
    if isinstance(obj, Product):
        obj_dict = obj.to_dict()
        obj_dict['__class__'] = 'Product'
        return obj_dict
    if isinstance(obj, CartItem):
        obj_dict = obj.to_dict()
        obj_dict['__class__'] = 'CartItem'
        return obj_dict
    if isinstance(obj, Order):
        obj_dict = obj.to_dict()
        obj_dict['__class__'] = 'Order'
        return obj_dict
    if isinstance(obj, OrderComment):
        obj_dict = obj.to_dict()
        obj_dict['__class__'] = 'OrderComment'
        return obj_dict
    if isinstance(obj, DiscountCode):
        obj_dict = obj.to_dict()
        obj_dict['__class__'] = 'DiscountCode'
        return obj_dict
    if isinstance(obj, SpinAttempt):
        obj_dict = obj.to_dict()
        obj_dict['__class__'] = 'SpinAttempt'
        return obj_dict
    if isinstance(obj, ProductReview):
        obj_dict = obj.to_dict()
        obj_dict['__class__'] = 'ProductReview'
        return obj_dict
    return obj

# --- Persistence Functions ---
def save_data():
    """Saves current in-memory data to a JSON file."""
    global users, products, orders, cart_items, order_comments, product_reviews, discount_codes, spin_attempts
    
    data_to_save = {
        'users': {uid: add_class_info(user) for uid, user in users.items()},
        'products': {pid: add_class_info(product) for pid, product in products.items()},
        'orders': {oid: add_class_info(order) for oid, order in orders.items()},
        'cart_items': {str(key): add_class_info(item) for key, item in cart_items.items()}, # Convert tuple key to string
        'order_comments': {oid: [add_class_info(comment) for comment in comments_list] for oid, comments_list in order_comments.items()},
        'product_reviews': {pid: [add_class_info(review) for review in reviews_list] for pid, reviews_list in product_reviews.items()},
        'discount_codes': {code: add_class_info(discount) for code, discount in discount_codes.items()},
        'spin_attempts': {uid: [add_class_info(attempt) for attempt in attempts_list] for uid, attempts_list in spin_attempts.items()}
    }
    
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data_to_save, f, cls=CustomEncoder, indent=4)
        logger.info(f"💾 Data saved to {DATA_FILE}")
    except Exception as e:
        logger.error(f"❌ Error saving data to {DATA_FILE}: {e}")

def load_data():
    """Loads data from a JSON file into in-memory dictionaries."""
    global users, products, orders, cart_items, order_comments, product_reviews, discount_codes, spin_attempts
    
    logger.info(f"🔍 Attempting to load data from: {os.path.abspath(DATA_FILE)}")
    
    if not os.path.exists(DATA_FILE):
        logger.info(f"No existing data file found at {DATA_FILE}. Starting with empty data.")
        return False # Indicate that no data was loaded
    
    try:
        with open(DATA_FILE, 'r') as f:
            loaded_data = json.load(f)
        
        # Reconstruct objects
        users.clear()
        for uid, user_data in loaded_data.get('users', {}).items():
            users[uid] = object_hook(user_data)
        
        products.clear()
        product_count = 0
        for pid, product_data in loaded_data.get('products', {}).items():
            products[pid] = object_hook(product_data)
            product_count += 1
        
        orders.clear()
        for oid, order_data in loaded_data.get('orders', {}).items():
            orders[oid] = object_hook(order_data)
        
        cart_items.clear()
        for key_str, item_data in loaded_data.get('cart_items', {}).items():
            user_id, product_id = eval(key_str) # Convert string key back to tuple
            cart_items[(user_id, product_id)] = object_hook(item_data)
        
        order_comments.clear()
        for oid, comments_list_data in loaded_data.get('order_comments', {}).items():
            order_comments[oid] = [object_hook(comment_data) for comment_data in comments_list_data]

        product_reviews.clear()
        for pid, reviews_list_data in loaded_data.get('product_reviews', {}).items():
            product_reviews[pid] = [object_hook(review_data) for review_data in reviews_list_data]

        discount_codes.clear()
        for code, discount_data in loaded_data.get('discount_codes', {}).items():
            discount_codes[code] = object_hook(discount_data)

        spin_attempts.clear()
        for uid, attempts_list_data in loaded_data.get('spin_attempts', {}).items():
            spin_attempts[uid] = [object_hook(attempt_data) for attempt_data in attempts_list_data]

        logger.info(f"✅ Data loaded successfully from {DATA_FILE}")
        logger.info(f"📊 Loaded {len(users)} users, {len(products)} products, {len(orders)} orders")
        logger.info(f"🔍 Products loaded: {product_count}")
        return True # Indicate that data was loaded
    except Exception as e:
        logger.error(f"❌ Error loading data from {DATA_FILE}: {e}. Starting with empty data.")
        # Clear any partially loaded data if an error occurs
        users.clear()
        products.clear()
        orders.clear()
        cart_items.clear()
        order_comments.clear()
        discount_codes.clear()
        spin_attempts.clear()
        return False # Indicate that no data was loaded

# --- User Class and Functions ---
class User:
    def __init__(self, username, email, password, role='customer'):
        self.id = str(uuid.uuid4())
        self.username = username
        self.email = email.lower().strip()  # Normalize email
        self.password_hash = generate_password_hash(password)
        self.role = role  # 'admin', 'vendor', 'customer'
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.wishlist = []  # List of product IDs

    def check_password(self, password):
        logger.debug(f"Attempting to check password for user {self.email}")
        logger.debug(f"Stored hash: {self.password_hash}")
        result = check_password_hash(self.password_hash, password)
        logger.debug(f"Password check result for {self.email}: {result}")
        return result

    def to_dict(self):
        d = self.__dict__.copy()
        d['created_at'] = self.created_at.isoformat()
        d['updated_at'] = self.updated_at.isoformat()
        d['wishlist'] = self.wishlist
        d['__class__'] = self.__class__.__name__
        return d

    @staticmethod
    def from_dict(d):
        user = User(d['username'], d['email'], '', d.get('role', 'customer'))
        user.id = d['id']
        user.password_hash = d['password_hash']
        user.created_at = datetime.fromisoformat(d['created_at']) if isinstance(d['created_at'], str) else d['created_at']
        user.updated_at = datetime.fromisoformat(d['updated_at']) if isinstance(d['updated_at'], str) else d['updated_at']
        user.wishlist = d.get('wishlist', [])
        return user

# --- Product Class and Functions ---
class Product:
    def __init__(self, name, description, price, category, vendor_id, image_filename=None, stock=0, is_promotional=False, promotional_price=None, promotional_end_date=None): # Added promotional fields
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.price = price
        self.category = category
        self.vendor_id = vendor_id
        self.image_filename = image_filename if image_filename else 'electronics-store-ad.jpg'
        self.is_active = True # Products can be active/inactive
        self.stock = int(stock) # Ensure stock is an integer
        self.is_promotional = is_promotional
        self.promotional_price = promotional_price
        self.promotional_end_date = promotional_end_date
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'vendor_id': self.vendor_id,
            'image_filename': self.image_filename,
            'is_active': self.is_active,
            'stock': self.stock, # Include stock in dict
            'is_promotional': self.is_promotional,
            'promotional_price': self.promotional_price,
            'promotional_end_date': self.promotional_end_date.isoformat() if self.promotional_end_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# --- CartItem Class and Functions ---
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

# --- Order Class and Functions ---
class Order:
    def __init__(self, customer_id, items, total_amount, discount_code=None, discount_percentage=0, discount_amount=0, subtotal=0):
        self.id = str(uuid.uuid4())
        self.customer_id = customer_id
        self.items = items  # List of dicts: [{'product_id', 'product_name', 'quantity', 'price', 'total'}]
        self.subtotal = subtotal  # Total before discount
        self.discount_code = discount_code  # Applied discount code
        self.discount_percentage = discount_percentage  # Discount percentage
        self.discount_amount = discount_amount  # Amount saved from discount
        self.total_amount = total_amount  # Final total after discount
        self.status = 'pending'  # New workflow statuses: 'pending', 'receipt_pending', 'admin_review', 'approved', 'delivered', 'cancelled'
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'items': self.items,
            'subtotal': self.subtotal,
            'discount_code': self.discount_code,
            'discount_percentage': self.discount_percentage,
            'discount_amount': self.discount_amount,
            'total_amount': self.total_amount,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# --- OrderComment Class and Functions ---
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

# --- ProductReview Class and Functions ---
class ProductReview:
    def __init__(self, product_id, user_id, rating, comment, user_name):
        self.id = str(uuid.uuid4())
        self.product_id = product_id
        self.user_id = user_id
        self.user_name = user_name
        self.rating = int(rating)  # 1-5 stars
        self.comment = comment
        self.created_at = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat()
        }

# --- DiscountCode Class and Functions ---
class DiscountCode:
    def __init__(self, code, discount_percentage, user_id):
        self.id = str(uuid.uuid4())
        self.code = code.upper()
        self.discount_percentage = discount_percentage
        self.user_id = user_id
        self.is_used = False
        self.created_at = datetime.now()
        self.expires_at = datetime.now() + timedelta(days=7)  # 7 days expiration

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'discount_percentage': self.discount_percentage,
            'user_id': self.user_id,
            'is_used': self.is_used,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }

# --- SpinAttempt Class and Functions ---
class SpinAttempt:
    def __init__(self, user_id, spin_number, result_discount, timestamp):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.spin_number = spin_number  # 1, 2, or 3
        self.result_discount = result_discount  # 0 for NO DISCOUNT, or percentage
        self.timestamp = timestamp
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'spin_number': self.spin_number,
            'result_discount': self.result_discount,
            'timestamp': self.timestamp.isoformat()
        }

# --- General Helper Functions ---
def create_user(username, email, password, role):
    email_lower = email.lower().strip()
    if email_lower in [u.email for u in users.values()]:
        logger.warning(f"User creation failed: Email {email_lower} already exists.")
        return None
    user = User(username, email_lower, password, role)
    users[user.id] = user
    logger.debug(f"Created user: {user.username} ({user.email}) with role: {user.role})")
    return user

def get_user_by_email(email):
    email_lower = email.lower().strip()
    for user in users.values():
        if user.email == email_lower:
            return user
    return None

def get_user_by_id(user_id):
    return users.get(user_id)

def create_product(name, description, price, category, vendor_id, image_filename, stock, is_promotional=False, promotional_price=None, promotional_end_date=None): # Added promotional parameters
    product = Product(name, description, price, category, vendor_id, image_filename, stock, is_promotional, promotional_price, promotional_end_date)
    products[product.id] = product
    return product

def get_products_by_category(category=None):
    if category:
        return [p for p in products.values() if p.category == category and p.is_active]
    return [p for p in products.values() if p.is_active]

def get_promotional_products():
    """Get all active promotional products."""
    promotional_products = []
    for p in products.values():
        if p.is_active and p.is_promotional and p.promotional_end_date:
            # Convert string to datetime if needed
            if isinstance(p.promotional_end_date, str):
                try:
                    end_date = datetime.fromisoformat(p.promotional_end_date.replace('Z', '+00:00'))
                except:
                    end_date = datetime.now() - timedelta(days=1)  # Expired if parsing fails
            else:
                end_date = p.promotional_end_date
            
            if end_date > datetime.now():
                promotional_products.append(p)
    
    return promotional_products

def get_featured_products(limit=6):
    """Get featured products (promotional first, then regular products)."""
    promotional = get_promotional_products()
    regular = [p for p in products.values() if p.is_active and not p.is_promotional]
    
    # Combine promotional first, then regular products
    featured = promotional + regular
    return featured[:limit]

def get_products_by_vendor(vendor_id):
    return [p for p in products.values() if p.vendor_id == vendor_id]

def add_to_cart(user_id, product_id, quantity=1): # Added quantity parameter
    product = products.get(product_id)
    if not product:
        logger.warning(f"Attempted to add non-existent product {product_id} to cart.")
        return False
    if product.stock < quantity: # Check if enough stock
        logger.warning(f"Not enough stock for product {product.name}. Available: {product.stock}, Requested: {quantity}")
        return False

    cart_key = (user_id, product_id)
    if cart_key in cart_items:
        # Check if adding more would exceed stock
        if product.stock < (cart_items[cart_key].quantity + quantity):
            logger.warning(f"Cannot add more {product.name} to cart. Exceeds stock. Current in cart: {cart_items[cart_key].quantity}, Available: {product.stock}")
            return False
        cart_items[cart_key].quantity += quantity
    else:
        cart_items[cart_key] = CartItem(user_id, product_id, quantity)
    return True # Indicate success

def get_cart_items(user_id):
    return [item for key, item in cart_items.items() if key[0] == user_id]

def create_order(customer_id, items, total_amount, discount_code=None, discount_percentage=0, discount_amount=0, subtotal=0):
    order = Order(customer_id, items, total_amount, discount_code, discount_percentage, discount_amount, subtotal)
    orders[order.id] = order
    order_comments[order.id] = []

    # Decrement stock for each item in the order
    for item_data in items:
        product = products.get(item_data['product_id'])
        if product:
            product.stock -= item_data['quantity']
            product.updated_at = datetime.now() # Update product timestamp
            logger.info(f"📦 Decremented stock for {product.name}. New stock: {product.stock}")
        else:
            logger.warning(f"Product {item_data['product_id']} not found when decrementing stock for order {order.id}")
    
    if discount_code:
        logger.info(f"🎫 Applied discount code {discount_code} ({discount_percentage}%) - saved ${discount_amount:.2f}")
    
    return order

def get_orders_by_customer(customer_id):
    return [o for o in orders.values() if o.customer_id == customer_id]

def get_orders_by_vendor(vendor_id):
    vendor_orders = []
    for order in orders.values():
        for item in order.items:
            product = products.get(item['product_id'])
            if product and product.vendor_id == vendor_id:
                vendor_orders.append(order)
                break
    return vendor_orders

def get_orders_for_admin():
    return list(orders.values())

def get_orders_pending_vendor_approval(vendor_id):
    pending_orders = []
    for order in orders.values():
        if order.status == 'receipt_pending':
            for item in order.items:
                product = products.get(item['product_id'])
                if product and product.vendor_id == vendor_id:
                    pending_orders.append(order)
                    break
    return pending_orders

def get_orders_pending_admin_approval():
    return [o for o in orders.values() if o.status == 'admin_review']

def update_order_status(order_id, new_status):
    logger.debug(f"[models.update_order_status] Attempting to update order {order_id} status to {new_status}")
    order = orders.get(order_id)
    if order:
        order.status = new_status
        order.updated_at = datetime.now()
        logger.debug(f"[models.update_order_status] Order {order_id} status successfully set to {order.status}")
        
        # Save the updated data to file
        try:
            save_data()
            logger.info(f"[models.update_order_status] Data saved successfully after status update")
        except Exception as e:
            logger.error(f"[models.update_order_status] Error saving data: {e}")
            return False
            
        return True
    logger.warning(f"[models.update_order_status] Order {order_id} not found for status update.")
    return False

def delete_order(order_id):
    """Delete an order from the system."""
    logger.debug(f"[models.delete_order] Attempting to delete order {order_id}")
    order = orders.get(order_id)
    if order:
        del orders[order_id]
        logger.debug(f"[models.delete_order] Order {order_id} deleted successfully")
        
        # Save the updated data to file
        try:
            save_data()
            logger.info(f"[models.delete_order] Data saved successfully after order deletion")
        except Exception as e:
            logger.error(f"[models.delete_order] Error saving data: {e}")
            return False
            
        return True
    logger.warning(f"[models.delete_order] Order {order_id} not found for deletion.")
    return False

def add_order_comment(order_id, user_id, message, user_role):
    comment = OrderComment(order_id, user_id, message, user_role)
    if order_id not in order_comments:
        order_comments[order_id] = []
    order_comments[order_id].append(comment)
    return comment

def get_order_comments(order_id):
    return order_comments.get(order_id, [])

def add_product_review(product_id, user_id, rating, comment, user_name):
    """Add a review to a product."""
    if product_id not in product_reviews:
        product_reviews[product_id] = []
    
    review = ProductReview(product_id, user_id, rating, comment, user_name)
    product_reviews[product_id].append(review)
    save_data()
    return review

def get_product_reviews(product_id):
    """Get all reviews for a specific product."""
    return product_reviews.get(product_id, [])

def get_product_average_rating(product_id):
    """Get the average rating for a product."""
    reviews = get_product_reviews(product_id)
    if not reviews:
        return 0
    
    # Handle both dictionary and object formats for backward compatibility
    total_rating = 0
    for review in reviews:
        if hasattr(review, 'rating'):
            # Object format
            total_rating += review.rating
        elif isinstance(review, dict) and 'rating' in review:
            # Dictionary format (for old data)
            total_rating += review['rating']
    
    return round(total_rating / len(reviews), 1)

def delete_product_review(review_id):
    """Delete a product review by its ID."""
    for product_id, reviews in product_reviews.items():
        for i, review in enumerate(reviews):
            # Handle both dictionary and object formats
            review_id_to_check = review.id if hasattr(review, 'id') else review.get('id')
            if review_id_to_check == review_id:
                deleted_review = reviews.pop(i)
                logger.info(f"🗑️ Deleted review {review_id} for product {product_id}")
                return deleted_review
    return None

def create_discount_code(discount_percentage, user_id):
    """Create a new discount code for a user."""
    import random
    import string
    
    # Generate a unique 6-character code
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in discount_codes:
            break
    
    discount = DiscountCode(code, discount_percentage, user_id)
    discount_codes[code] = discount
    logger.info(f"🎫 Created discount code {code} for {discount_percentage}% off for user {user_id}")
    return discount

def get_discount_code(code):
    """Get a discount code by its code string."""
    return discount_codes.get(code.upper())

def validate_discount_code(code, user_id):
    """Validate if a discount code is valid and can be used."""
    discount = get_discount_code(code)
    if not discount:
        return False, "Invalid discount code"
    
    if discount.is_used:
        return False, "Discount code has already been used"
    
    if discount.user_id != user_id:
        return False, "Discount code is not valid for this user"
    
    if discount.expires_at and discount.expires_at < datetime.now():
        return False, "Discount code has expired"
    
    return True, discount

def use_discount_code(code, user_id):
    """Mark a discount code as used."""
    discount = get_discount_code(code)
    if discount and discount.user_id == user_id:
        discount.is_used = True
        logger.info(f"🎫 Used discount code {code} for user {user_id}")
        return True
    return False

# --- Spin Attempt Functions ---
def get_user_spin_attempts(user_id):
    """Get all spin attempts for a user in the last 5 minutes."""
    if user_id not in spin_attempts:
        return []
    
    five_minutes_ago = datetime.now() - timedelta(minutes=5)
    recent_attempts = [
        attempt for attempt in spin_attempts[user_id] 
        if attempt.timestamp > five_minutes_ago
    ]
    
    # Clean up old attempts while we're at it
    if len(recent_attempts) != len(spin_attempts[user_id]):
        spin_attempts[user_id] = recent_attempts
        # Save data after cleanup to persist the changes
        try:
            save_data()
            logger.info(f"🎯 Cleaned up old spin attempts for user {user_id} and saved data")
        except Exception as e:
            logger.error(f"Error saving data after spin cleanup: {e}")
    
    return recent_attempts

def can_user_spin(user_id):
    """Check if user can spin (max 3 spins per 5 minutes)."""
    recent_attempts = get_user_spin_attempts(user_id)
    return len(recent_attempts) < 3

def get_next_spin_number(user_id):
    """Get the next spin number (1, 2, or 3) for the user."""
    recent_attempts = get_user_spin_attempts(user_id)
    return len(recent_attempts) + 1

def record_spin_attempt(user_id, spin_number, result_discount):
    """Record a spin attempt for the user."""
    if user_id not in spin_attempts:
        spin_attempts[user_id] = []
    
    attempt = SpinAttempt(user_id, spin_number, result_discount, datetime.now())
    spin_attempts[user_id].append(attempt)
    logger.info(f"🎯 Recorded spin attempt for user {user_id}: spin #{spin_number}, result: {result_discount}%")
    return attempt

def determine_spin_result(spin_number):
    """Determine the result based on spin number."""
    import random
    
    # All spins are now random for better user experience
    possible_results = [0, 5, 10, 15, 20, 25, 30]  # 0 = NO DISCOUNT
    return random.choice(possible_results)

# --- Initial Data Setup / Load Data ---
def initialize_data_and_defaults():
    """
    Attempts to load data from file. If no data or error, initializes default data.
    """
    global users, products, orders, cart_items, order_comments, discount_codes, spin_attempts

    logger.info("🔍 Starting data initialization...")
    
    if load_data(): # Try to load existing data
        logger.info("Existing data loaded. Skipping default user/product creation.")
        # Ensure default users exist even if data was loaded (e.g., if data file was old)
        # This part is a safety net.
        admin_user = get_user_by_email('admin@electronics.com')
        if not admin_user:
            admin_user = create_user('Admin User', 'admin@electronics.com', 'admin123', 'admin')
            logger.info(f"✅ Created missing admin user: {admin_user.email}")
        
        vendor_user = get_user_by_email('vendor@test.com')
        if not vendor_user:
            vendor_user = create_user('Test Vendor', 'vendor@test.com', 'vendor123', 'vendor')
            logger.info(f"✅ Created missing vendor user: {vendor_user.email}")

        customer_user = get_user_by_email('customer@test.com')
        if not customer_user:
            customer_user = create_user('Test Customer', 'customer@test.com', 'customer123', 'customer')
            logger.info(f"✅ Created missing customer user: {customer_user.email}")

        # Only create sample products if products dict is empty AND a vendor exists
        logger.info(f"🔍 Products dict has {len(products)} products, vendor_user exists: {vendor_user is not None}")
        if not products and vendor_user:
            # Create promotional products with end dates
            from datetime import timedelta
            promo_end_date = datetime(2099, 1, 1)  # Far future date
            
            create_product('Gaming Laptop Pro', 'High-performance gaming laptop with RTX 3080.', 1800.00, 'Laptops', vendor_user.id, 'gaming-laptop.jpg', 10, True, 1499.00, promo_end_date) # Promotional
            create_product('Smartphone Ultra 5G', 'Latest 5G smartphone with advanced camera.', 999.00, 'Smartphones', vendor_user.id, 'smartphone-5g.jpg', 15, True, 799.00, promo_end_date) # Promotional
            create_product('Wireless Noise-Cancelling Headphones', 'Immersive sound with active noise cancellation.', 250.00, 'Headphones', vendor_user.id, 'noise-cancelling-headphones.jpg', 20) # Regular
            create_product('Mechanical Gaming Keyboard', 'RGB backlit mechanical keyboard with tactile switches.', 120.00, 'Keyboards', vendor_user.id, 'mechanical-keyboard.jpg', 25, True, 89.00, promo_end_date) # Promotional
            create_product('Gaming Mouse Pro', 'Ergonomic gaming mouse with high DPI sensor.', 75.00, 'Mice', vendor_user.id, 'gaming-mouse.jpg', 30) # Regular
            create_product('Tablet Pro 12-inch', 'Powerful tablet for creativity and productivity.', 700.00, 'Tablets', vendor_user.id, 'tablet-pro.jpg', 8) # Regular
            create_product('Bluetooth Speaker', 'Portable wireless speaker with premium sound quality.', 89.00, 'Speakers', vendor_user.id, 'bluetooth-speaker.jpg', 15, True, 69.00, promo_end_date) # Promotional
            create_product('Smart Watch', 'Fitness tracking smartwatch with heart rate monitor.', 299.00, 'Wearables', vendor_user.id, 'smartwatch.jpg', 12, False, None, None) # Regular
            create_product('Wireless Earbuds', 'True wireless earbuds with noise cancellation.', 159.00, 'Headphones', vendor_user.id, 'wireless-earbuds.jpg', 25, True, 129.00, promo_end_date) # Promotional
            create_product('Gaming Headset', '7.1 surround sound gaming headset with microphone.', 129.00, 'Headphones', vendor_user.id, 'gaming-headset.jpg', 18, False, None, None) # Regular
            create_product('USB-C Hub', 'Multi-port USB-C hub for laptop connectivity.', 45.00, 'Accessories', vendor_user.id, 'usb-c-hub.jpg', 30, True, 35.00, promo_end_date) # Promotional
            create_product('Wireless Charger', 'Fast wireless charging pad for smartphones.', 39.00, 'Accessories', vendor_user.id, 'wireless-charger.jpg', 22, False, None, None) # Regular
            create_product('Laptop Stand', 'Adjustable aluminum laptop stand for ergonomic setup.', 29.00, 'Accessories', vendor_user.id, 'laptop-stand.jpg', 35, True, 24.00, promo_end_date) # Promotional
            create_product('Webcam HD', '1080p HD webcam for video conferencing.', 79.00, 'Accessories', vendor_user.id, 'webcam-hd.jpg', 20, False, None, None) # Regular
            create_product('External SSD', '1TB portable SSD with USB 3.2 Gen 2.', 129.00, 'Storage', vendor_user.id, 'external-ssd.jpg', 14, True, 99.00, promo_end_date) # Promotional
            create_product('Monitor 4K', '27-inch 4K Ultra HD monitor for professional work.', 399.00, 'Monitors', vendor_user.id, 'monitor-4k.jpg', 8, False, None, None) # Regular
            create_product('Gaming Chair', 'Ergonomic gaming chair with lumbar support.', 249.00, 'Furniture', vendor_user.id, 'gaming-chair.jpg', 12, True, 199.00, promo_end_date) # Promotional
            create_product('Microphone Pro', 'USB condenser microphone for streaming.', 89.00, 'Audio', vendor_user.id, 'microphone-pro.jpg', 25, False, None, None) # Regular
            create_product('Graphics Card', 'RTX 4070 graphics card for gaming.', 599.00, 'Components', vendor_user.id, 'graphics-card.jpg', 6, True, 549.00, promo_end_date) # Promotional
            create_product('Power Bank', '20000mAh portable charger for devices.', 49.00, 'Accessories', vendor_user.id, 'power-bank.jpg', 30, False, None, None) # Regular
            create_product('Smart Speaker', 'Voice-controlled smart speaker with Alexa.', 79.00, 'Speakers', vendor_user.id, 'smart-speaker.jpg', 20, True, 59.00, promo_end_date) # Promotional
            create_product('Tablet Stand', 'Adjustable tablet holder for desk use.', 19.00, 'Accessories', vendor_user.id, 'tablet-stand.jpg', 40, False, None, None) # Regular
            create_product('Cable Organizer', 'Multi-compartment cable management box.', 15.00, 'Accessories', vendor_user.id, 'cable-organizer.jpg', 50, True, 12.00, promo_end_date) # Promotional
            logger.info("✅ Created sample products with promotional offers (after loading existing data)")

    else: # No data file found or error loading, so initialize defaults
        logger.info("No existing data found or error loading. Initializing default data...")
        admin_user = create_user('Admin User', 'admin@electronics.com', 'admin123', 'admin')
        vendor_user = create_user('Test Vendor', 'vendor@test.com', 'vendor123', 'vendor')
        customer_user = create_user('Test Customer', 'customer@test.com', 'customer123', 'customer')

        logger.info(f"🔍 Initial setup - vendor_user exists: {vendor_user is not None}")
        if vendor_user:
            # Create promotional products with end dates
            from datetime import timedelta
            promo_end_date = datetime(2099, 1, 1)  # Far future date
            
            create_product('Gaming Laptop Pro', 'High-performance gaming laptop with RTX 3080.', 1800.00, 'Laptops', vendor_user.id, 'gaming-laptop.jpg', 10, True, 1499.00, promo_end_date) # Promotional
            create_product('Smartphone Ultra 5G', 'Latest 5G smartphone with advanced camera.', 999.00, 'Smartphones', vendor_user.id, 'smartphone-5g.jpg', 15, True, 799.00, promo_end_date) # Promotional
            create_product('Wireless Noise-Cancelling Headphones', 'Immersive sound with active noise cancellation.', 250.00, 'Headphones', vendor_user.id, 'noise-cancelling-headphones.jpg', 20) # Regular
            create_product('Mechanical Gaming Keyboard', 'RGB backlit mechanical keyboard with tactile switches.', 120.00, 'Keyboards', vendor_user.id, 'mechanical-keyboard.jpg', 25, True, 89.00, promo_end_date) # Promotional
            create_product('Gaming Mouse Pro', 'Ergonomic gaming mouse with high DPI sensor.', 75.00, 'Mice', vendor_user.id, 'gaming-mouse.jpg', 30) # Regular
            create_product('Tablet Pro 12-inch', 'Powerful tablet for creativity and productivity.', 700.00, 'Tablets', vendor_user.id, 'tablet-pro.jpg', 8) # Regular
            create_product('Bluetooth Speaker', 'Portable wireless speaker with premium sound quality.', 89.00, 'Speakers', vendor_user.id, 'bluetooth-speaker.jpg', 15, True, 69.00, promo_end_date) # Promotional
            create_product('Smart Watch', 'Fitness tracking smartwatch with heart rate monitor.', 299.00, 'Wearables', vendor_user.id, 'smartwatch.jpg', 12, False, None, None) # Regular
            create_product('Wireless Earbuds', 'True wireless earbuds with noise cancellation.', 159.00, 'Headphones', vendor_user.id, 'wireless-earbuds.jpg', 25, True, 129.00, promo_end_date) # Promotional
            create_product('Gaming Headset', '7.1 surround sound gaming headset with microphone.', 129.00, 'Headphones', vendor_user.id, 'gaming-headset.jpg', 18, False, None, None) # Regular
            create_product('USB-C Hub', 'Multi-port USB-C hub for laptop connectivity.', 45.00, 'Accessories', vendor_user.id, 'usb-c-hub.jpg', 30, True, 35.00, promo_end_date) # Promotional
            create_product('Wireless Charger', 'Fast wireless charging pad for smartphones.', 39.00, 'Accessories', vendor_user.id, 'wireless-charger.jpg', 22, False, None, None) # Regular
            create_product('Laptop Stand', 'Adjustable aluminum laptop stand for ergonomic setup.', 29.00, 'Accessories', vendor_user.id, 'laptop-stand.jpg', 35, True, 24.00, promo_end_date) # Promotional
            create_product('Webcam HD', '1080p HD webcam for video conferencing.', 79.00, 'Accessories', vendor_user.id, 'webcam-hd.jpg', 20, False, None, None) # Regular
            create_product('External SSD', '1TB portable SSD with USB 3.2 Gen 2.', 129.00, 'Storage', vendor_user.id, 'external-ssd.jpg', 14, True, 99.00, promo_end_date) # Promotional
            create_product('Monitor 4K', '27-inch 4K Ultra HD monitor for professional work.', 399.00, 'Monitors', vendor_user.id, 'monitor-4k.jpg', 8, False, None, None) # Regular
            create_product('Gaming Chair', 'Ergonomic gaming chair with lumbar support.', 249.00, 'Furniture', vendor_user.id, 'gaming-chair.jpg', 12, True, 199.00, promo_end_date) # Promotional
            create_product('Microphone Pro', 'USB condenser microphone for streaming.', 89.00, 'Audio', vendor_user.id, 'microphone-pro.jpg', 25, False, None, None) # Regular
            create_product('Graphics Card', 'RTX 4070 graphics card for gaming.', 599.00, 'Components', vendor_user.id, 'graphics-card.jpg', 6, True, 549.00, promo_end_date) # Promotional
            create_product('Power Bank', '20000mAh portable charger for devices.', 49.00, 'Accessories', vendor_user.id, 'power-bank.jpg', 30, False, None, None) # Regular
            create_product('Smart Speaker', 'Voice-controlled smart speaker with Alexa.', 79.00, 'Speakers', vendor_user.id, 'smart-speaker.jpg', 20, True, 59.00, promo_end_date) # Promotional
            create_product('Tablet Stand', 'Adjustable tablet holder for desk use.', 19.00, 'Accessories', vendor_user.id, 'tablet-stand.jpg', 40, False, None, None) # Regular
            create_product('Cable Organizer', 'Multi-compartment cable management box.', 15.00, 'Accessories', vendor_user.id, 'cable-organizer.jpg', 50, True, 12.00, promo_end_date) # Promotional
            logger.info("✅ Created sample products with promotional offers (initial setup)")

    logger.info("🎉 Data initialization/loading completed successfully!")
    logger.info("==================================================")
    # Ensure users exist before trying to access their emails
    admin_email = get_user_by_email('admin@electronics.com').email if get_user_by_email('admin@electronics.com') else 'N/A'
    vendor_email = get_user_by_email('vendor@test.com').email if get_user_by_email('vendor@test.com') else 'N/A'
    customer_email = get_user_by_email('customer@test.com').email if get_user_by_email('customer@test.com') else 'N/A'

    logger.info(f"TEST ACCOUNTS:")
    logger.info(f"Admin: {admin_email} / admin123")
    logger.info(f"Vendor: {vendor_email} / vendor123")
    logger.info(f"Customer: {customer_email} / customer123")
    logger.info("==================================================")
