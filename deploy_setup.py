#!/usr/bin/env python3
"""
Deployment Setup Script for Railway
This script helps prepare your Flask application for deployment on Railway.com
"""

import os
import subprocess
import sys
import secrets

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}: {e}")
        print(f"Error output: {e.stderr}")
        return None

def generate_secret_key():
    """Generate a secure secret key for production"""
    return secrets.token_hex(32)

def main():
    print("🚀 Railway Deployment Setup")
    print("=" * 50)
    
    # Check if git is installed
    if not run_command("git --version", "Checking Git installation"):
        print("❌ Git is not installed. Please install Git first.")
        sys.exit(1)
    
    # Initialize git repository if not already done
    if not os.path.exists(".git"):
        if not run_command("git init", "Initializing Git repository"):
            sys.exit(1)
    else:
        print("✅ Git repository already exists")
    
    # Add all files to git
    if not run_command("git add .", "Adding files to Git"):
        sys.exit(1)
    
    # Check if there are changes to commit
    result = run_command("git status --porcelain", "Checking Git status")
    if result and result.strip():
        # Commit changes
        if not run_command('git commit -m "Initial commit for Railway deployment"', "Committing changes"):
            sys.exit(1)
    else:
        print("✅ No changes to commit")
    
    # Generate a secure secret key
    secret_key = generate_secret_key()
    print(f"🔑 Generated secure SESSION_SECRET: {secret_key}")
    
    print("\n📋 Next Steps:")
    print("1. Create a new repository on GitHub:")
    print("   - Go to https://github.com/new")
    print("   - Choose a repository name (e.g., 'electronics-store-flask')")
    print("   - Make it public or private as you prefer")
    print("   - Don't initialize with README, .gitignore, or license")
    
    print("\n2. Connect your local repository to GitHub:")
    print("   - Copy the repository URL from GitHub")
    print("   - Run: git remote add origin <your-github-repo-url>")
    print("   - Run: git branch -M main")
    print("   - Run: git push -u origin main")
    
    print("\n3. Deploy on Railway:")
    print("   - Go to https://railway.com")
    print("   - Sign up/Login with your GitHub account")
    print("   - Click 'New Project' → 'Deploy from GitHub repo'")
    print("   - Select your repository")
    print("   - Add environment variable: SESSION_SECRET = " + secret_key)
    
    print("\n4. Your app will be automatically deployed!")
    print("   - Railway will detect the Flask app from the Procfile")
    print("   - The app will be available at the provided Railway URL")
    
    print(f"\n🔐 Important: Save this SESSION_SECRET for Railway:")
    print(f"SESSION_SECRET={secret_key}")

if __name__ == "__main__":
    main() 