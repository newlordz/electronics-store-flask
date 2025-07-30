#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import products, get_promotional_products, get_featured_products, get_products_by_category, initialize_data_and_defaults, load_data
from datetime import datetime

print("=== PRODUCT DEBUGGING ===")
print(f"Current time: {datetime.now()}")
print(f"Total products in database: {len(products)}")

print("\n=== CHECKING DATA LOADING ===")
print("Attempting to load data...")
data_loaded = load_data()
print(f"Data loaded successfully: {data_loaded}")
print(f"Products after loading: {len(products)}")

if len(products) == 0:
    print("\n=== INITIALIZING DEFAULT DATA ===")
    initialize_data_and_defaults()
    print(f"Products after initialization: {len(products)}")

print("\n=== ALL PRODUCTS ===")
for product_id, product in products.items():
    print(f"ID: {product_id}")
    print(f"Name: {product.name}")
    print(f"Active: {product.is_active}")
    print(f"Promotional: {product.is_promotional}")
    print(f"Promotional End Date: {product.promotional_end_date}")
    if product.promotional_end_date:
        if isinstance(product.promotional_end_date, str):
            try:
                end_date = datetime.fromisoformat(product.promotional_end_date.replace('Z', '+00:00'))
                print(f"Parsed End Date: {end_date}")
                print(f"Is Future: {end_date > datetime.now()}")
            except Exception as e:
                print(f"Error parsing date: {e}")
        else:
            print(f"Is Future: {product.promotional_end_date > datetime.now()}")
    print("---")

print("\n=== PROMOTIONAL PRODUCTS ===")
promotional = get_promotional_products()
print(f"Promotional products count: {len(promotional)}")
for product in promotional:
    print(f"- {product.name} (${product.price} → ${product.promotional_price})")

print("\n=== FEATURED PRODUCTS ===")
featured = get_featured_products(6)
print(f"Featured products count: {len(featured)}")
for product in featured:
    print(f"- {product.name} (${product.price})")

print("\n=== PRODUCTS BY CATEGORY ===")
for category in ['Laptops', 'Smartphones', 'Headphones', 'Keyboards', 'Mice', 'Tablets']:
    cat_products = get_products_by_category(category)
    print(f"{category}: {len(cat_products)} products")
    for product in cat_products:
        print(f"  - {product.name}") 