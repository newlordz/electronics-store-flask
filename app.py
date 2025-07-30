import os
import logging
from flask import Flask, g, session, request
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('flask_session', exist_ok=True)

# Initialize session
Session(app)

logger.info("Flask app initialized successfully")

# --- IMPORTANT: Initialize default data / Load persisted data BEFORE importing routes ---
# This ensures that 'users' and 'products' dictionaries are populated
# before any route functions try to access them for authentication or product display.
from models import initialize_data_and_defaults, save_data, get_cart_items
initialize_data_and_defaults() # Call the new combined function

# Comment out automatic saving to prevent infinite loops
# @app.teardown_appcontext
# def teardown_db(exception):
#     # Only save if there's an active request and it's not a static file request
#     if request and not request.path.startswith('/static/') and not request.path.startswith('/uploads/'):
#         try:
#             save_data()
#         except Exception as e:
#             logger.error(f"Error saving data: {e}")

# Context processor to make cart_items_count available in all templates
@app.context_processor
def inject_global_data():
    cart_items_count = 0
    if 'user_id' in session:
        user_cart = get_cart_items(session['user_id'])
        cart_items_count = sum(item.quantity for item in user_cart)
    return dict(cart_items_count=cart_items_count)


# Import routes after app creation and data initialization to avoid circular imports
from routes import *

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
