# ELECTRONICS STORES - Flask E-commerce Application

A modern, feature-rich e-commerce platform built with Flask for selling electronics and accessories.

<!-- Deployment Trigger: Force data reset and image fixes -->

## Features

- 🛍️ **Product Management**: Add, edit, and manage products with categories
- 👥 **User Authentication**: Secure login/register system with role-based access
- 🛒 **Shopping Cart**: Add products to cart and manage quantities
- 💳 **Checkout System**: Complete purchase flow with order management
- 🎯 **Flash Sales**: Time-limited promotional offers with countdown timers
- 🎰 **Lucky Spin**: Interactive wheel spin for discounts and rewards
- 📱 **Responsive Design**: Mobile-friendly interface
- 🔍 **Search & Filter**: Find products by category and search terms
- ⭐ **Wishlist**: Save favorite products for later
- 📧 **Newsletter**: Email subscription system

## Tech Stack

- **Backend**: Flask 3.1.1
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Session Management**: Flask-Session
- **Deployment**: Railway.com
- **WSGI Server**: Gunicorn

## Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd AuthFix
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export SESSION_SECRET="your-secret-key-here"
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

5. **Access the application**
   - Open your browser and go to `http://localhost:5000`

## Deployment on Railway

This application is configured for deployment on Railway.com. The following files are included for deployment:

- `requirements.txt` - Python dependencies
- `Procfile` - Process definition for Railway
- `runtime.txt` - Python version specification

### Railway Deployment Steps:

1. **Connect your GitHub repository to Railway**
   - Go to [Railway.com](https://railway.com)
   - Sign up/Login with your GitHub account
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository

2. **Configure Environment Variables**
   - In your Railway project dashboard, go to "Variables"
   - Add the following environment variable:
     - `SESSION_SECRET`: A secure random string for session encryption

3. **Deploy**
   - Railway will automatically detect the Flask application
   - The deployment will use the `Procfile` to run the app with Gunicorn
   - Your app will be available at the provided Railway URL

## Project Structure

```
AuthFix/
├── app.py                 # Main Flask application
├── main.py               # Entry point
├── models.py             # Data models and business logic
├── routes.py             # Route definitions
├── requirements.txt      # Python dependencies
├── Procfile             # Railway deployment configuration
├── runtime.txt          # Python version
├── static/              # Static files (CSS, JS, images)
│   ├── style.css
│   ├── main.js
│   └── uploads/         # Product images
├── templates/           # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   └── ...
└── data.json           # Data storage (JSON-based)
```

## Default Admin Account

For testing purposes, the application includes a default admin account:

- **Email**: admin@example.com
- **Password**: admin123
- **Role**: Admin

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you encounter any issues or have questions, please open an issue on GitHub or contact the development team. 