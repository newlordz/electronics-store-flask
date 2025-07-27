# Electronics Store Application

## Overview

This is a Flask-based e-commerce web application for selling electronics. The application supports multiple user roles (buyers, sellers, and admins) with a complete product catalog, shopping cart, order management system, and real-time order communication features. The application uses in-memory data storage for development but is designed to be easily migrated to PostgreSQL with SQLAlchemy.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 dark theme for responsive UI
- **Styling**: Custom CSS with CSS variables, gradient backgrounds, and modern UI components
- **JavaScript**: Vanilla JavaScript for interactive features (cart management, form validation, search, animations)
- **Icons**: Font Awesome 6.0 for consistent iconography throughout the application
- **Responsive Design**: Mobile-first approach using Bootstrap grid system with custom enhancements

### Backend Architecture
- **Framework**: Flask (Python web framework) with modular route organization
- **Session Management**: Flask-Session with filesystem storage for user authentication state
- **File Handling**: Werkzeug for secure file uploads with 16MB size limit for product images
- **Authentication**: Custom session-based authentication with Werkzeug password hashing
- **Authorization**: Role-based access control using decorators for different user permissions
- **Error Handling**: Custom 404 and 500 error pages for better user experience

### Data Storage Solutions
- **Current Implementation**: In-memory data storage using Python dictionaries for MVP development
- **Data Models**: Object-oriented design with User, Product, Order, CartItem, and OrderComment classes
- **File Storage**: Local filesystem for uploaded product images in static/uploads directory
- **Session Storage**: Filesystem-based session storage for maintaining user login state
- **Migration Ready**: Designed to easily transition to PostgreSQL with SQLAlchemy ORM

## Key Components

### User Management System
- **Multi-Role Authentication**: Three distinct user types with different permissions and workflows
  - **Buyers**: Browse products, manage shopping cart, place and track orders, communicate with sellers
  - **Sellers**: Manage product listings, view and fulfill orders, require admin approval for account activation
  - **Admins**: Complete system oversight, user management, seller approval workflow, global order management
- **Registration Flow**: Email-based registration with role selection and seller approval process
- **Security Features**: Password hashing, session management, role-based route protection, and input validation

### Product Catalog System
- **Categories**: Predefined electronics categories (Laptops, Smartphones, Mice, Keyboards, Headphones, Tablets, Accessories)
- **Product Management**: Full CRUD operations for sellers with image upload capabilities and product status toggles
- **Search and Filtering**: Text-based search and category filtering for efficient product discovery
- **Product Details**: Comprehensive product pages with images, descriptions, pricing, and seller information

### Shopping Cart and Order Management
- **Shopping Cart**: Session-based cart management with add/remove functionality and quantity tracking
- **Checkout Process**: Multi-step checkout with billing information collection and order confirmation
- **Order Tracking**: Complete order lifecycle management (created → paid → delivered) with status updates
- **Order Communication**: Real-time messaging system between buyers and sellers for order-specific discussions

### Administrative Features
- **User Management**: Admin dashboard for approving seller accounts and managing user roles
- **System Analytics**: Dashboard with statistics on users, products, orders, and revenue metrics
- **Order Oversight**: Global view of all orders with status management capabilities
- **Content Moderation**: Product approval and management system for maintaining quality standards

## Data Flow

### User Registration and Authentication
1. User registers with email, username, password, and role selection
2. Sellers require admin approval before accessing seller features
3. Session-based authentication maintains login state across requests
4. Role-based decorators control access to different application sections

### Product Management Flow
1. Approved sellers create products with images, descriptions, and pricing
2. Products are immediately available in the catalog for buyers
3. Admin can toggle product visibility and manage catalog quality
4. Search and filter functionality enables efficient product discovery

### Order Processing Flow
1. Buyers add products to session-based shopping cart
2. Checkout process collects billing information and creates order
3. Order appears in both buyer's order history and seller's dashboard
4. Sellers can update order status through the fulfillment process
5. Order communication system enables buyer-seller interaction

### Communication System
1. Order-specific chat system between buyers and sellers
2. Comments are timestamped and associated with specific orders
3. Real-time updates on order status changes and communications
4. Admin oversight of all order communications for dispute resolution

## External Dependencies

### Python Packages
- **Flask 3.1.1**: Core web framework for application structure
- **Flask-Session 0.8.0**: Session management for user authentication
- **Werkzeug 3.1.3**: WSGI utilities and secure file handling
- **email-validator 2.2.0**: Email validation for user registration
- **gunicorn 23.0.0**: Production WSGI server for deployment

### Frontend Dependencies
- **Bootstrap 5.3.0**: CSS framework for responsive design and components
- **Font Awesome 6.4.0**: Icon library for consistent UI iconography
- **Custom CSS**: Enhanced styling with CSS variables and modern design patterns

### Optional Database Migration
- **psycopg2-binary**: PostgreSQL adapter for Python (when migrating from in-memory storage)
- **SQLAlchemy**: ORM for database operations and model relationships

## Deployment Strategy

### Development Environment
- **Local Development**: Python 3.11+ with pip-installed dependencies
- **Hot Reload**: Flask development server with debug mode enabled
- **File Storage**: Local filesystem for uploaded images and session data
- **In-Memory Data**: Dictionary-based storage for rapid development iteration

### Production Considerations
- **Database Migration**: Transition from in-memory storage to PostgreSQL with SQLAlchemy
- **Static File Serving**: Configure proper static file serving for production
- **Environment Variables**: Secure configuration management for secrets and database URLs
- **WSGI Server**: Gunicorn for production deployment with appropriate worker configuration
- **Session Storage**: Consider Redis or database-backed sessions for multi-instance deployments

### Security Enhancements for Production
- **HTTPS Configuration**: SSL/TLS encryption for all communications
- **Secret Key Management**: Secure generation and storage of session secrets
- **File Upload Security**: Enhanced validation and scanning of uploaded images
- **Rate Limiting**: Protection against abuse and automated attacks
- **Database Security**: Proper connection pooling and query parameterization