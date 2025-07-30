import os
from app import app

if __name__ == '__main__':
    # Use environment variable for debug mode, default to False in production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
