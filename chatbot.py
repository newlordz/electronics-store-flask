#!/usr/bin/env python3
"""
Chatbot system for Electronics Store
Handles customer support, reporting, and general inquiries
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from flask import session, request
import re

logger = logging.getLogger(__name__)

class ChatbotMessage:
    def __init__(self, user_id: str, message: str, message_type: str = "user", timestamp: Optional[datetime] = None):
        self.user_id = user_id
        self.message = message
        self.message_type = message_type  # "user" or "bot"
        self.timestamp = timestamp or datetime.now()
        self.id = f"{self.user_id}_{self.timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'message': self.message,
            'message_type': self.message_type,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data):
        msg = cls(
            user_id=data['user_id'],
            message=data['message'],
            message_type=data['message_type'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )
        msg.id = data['id']
        return msg

class Report:
    def __init__(self, user_id: str, report_type: str, description: str, priority: str = "medium"):
        self.id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.user_id = user_id
        self.report_type = report_type
        self.description = description
        self.priority = priority
        self.status = "open"
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.admin_notes = ""
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'report_type': self.report_type,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'admin_notes': self.admin_notes
        }
    
    @classmethod
    def from_dict(cls, data):
        report = cls(
            user_id=data['user_id'],
            report_type=data['report_type'],
            description=data['description'],
            priority=data['priority']
        )
        report.id = data['id']
        report.status = data['status']
        report.created_at = datetime.fromisoformat(data['created_at'])
        report.updated_at = datetime.fromisoformat(data['updated_at'])
        report.admin_notes = data['admin_notes']
        return report

class Chatbot:
    def __init__(self):
        self.conversations: Dict[str, List[ChatbotMessage]] = {}
        self.reports: Dict[str, Report] = {}
        self.keywords = {
            'order_status': ['order', 'track', 'shipping', 'delivery', 'status'],
            'product_help': ['product', 'item', 'specs', 'features', 'compare', 'laptop', 'computer', 'phone', 'smartphone', 'mobile', 'keyboard', 'mouse', 'headphones', 'headset', 'earbuds', 'tablet', 'ipad', 'accessories', 'cable', 'charger', 'speaker', 'monitor', 'screen', 'gaming', 'wireless', 'bluetooth', 'usb', 'camera', 'webcam', 'microphone', 'printer', 'scanner', 'router', 'modem', 'storage', 'ssd', 'hard drive', 'memory', 'ram', 'processor', 'cpu', 'graphics', 'gpu', 'motherboard', 'power supply', 'case', 'cooling', 'fan'],
            'return_refund': ['return', 'refund', 'exchange', 'damaged', 'wrong'],
            'payment_help': ['payment', 'card', 'pay', 'billing', 'charge'],
            'technical_support': ['bug', 'error', 'problem', 'issue', 'broken', 'not working'],
            'general_help': ['help', 'support', 'assist', 'question', 'how'],
            'report_issue': ['report', 'complaint', 'problem', 'issue', 'bug', 'broken']
        }
        
        self.responses = {
            'greeting': [
                "Hello! 👋 I'm your Electronics Store assistant. How can I help you today?",
                "Hi there! 🛍️ Welcome to Electronics Store. What can I assist you with?",
                "Greetings! I'm here to help with your electronics shopping needs. What would you like to know?"
            ],
            'order_status': [
                "I can help you track your order! Please provide your order ID or email address.",
                "To check your order status, I'll need your order number. You can find it in your order confirmation email.",
                "Let me help you track your order. Do you have your order ID handy?"
            ],
            'product_help': [
                "Great! I can help you find information about that product. You can browse our full selection at /products or tell me more about what you're looking for!",
                "Perfect! I'd be happy to help you with product information. You can view all our products at /products or ask me about specific features you need!",
                "Excellent choice! I can help you find the perfect product. Check out our products at /products or let me know what specific features you're interested in!"
            ],
            'return_refund': [
                "I understand you need help with a return or refund. Can you tell me more about the situation?",
                "I can guide you through our return process. What's the reason for the return?",
                "Let me help you with your return request. Do you have your order number?"
            ],
            'payment_help': [
                "I can help you with payment questions. What specific payment issue are you experiencing?",
                "Let me assist you with payment-related concerns. What would you like to know?",
                "I'm here to help with payment questions. What can I clarify for you?"
            ],
            'technical_support': [
                "I'm sorry to hear you're experiencing technical issues. Let me help you report this problem.",
                "I can help you report this technical issue. Can you provide more details about what's happening?",
                "Let me assist you with this technical problem. I'll help you create a support ticket."
            ],
            'report_issue': [
                "I can help you report this issue. Let me create a support ticket for you.",
                "I'll help you submit a report. Can you provide more details about the problem?",
                "Let me assist you with reporting this issue. I'll need some additional information."
            ],
            'fallback': [
                "I'm not sure I understood that. Could you rephrase or try asking about orders, products, returns, or payments?",
                "I didn't quite catch that. I can help with order tracking, product info, returns, payments, or technical support.",
                "I'm still learning! Try asking about your orders, products, returns, or payments."
            ],
            'goodbye': [
                "Thank you for chatting with me! Have a great day! 👋",
                "It was nice helping you! Feel free to come back if you need more assistance.",
                "Thanks for visiting Electronics Store! Take care! 🛍️"
            ]
        }
    
    def get_response(self, user_id: str, message: str) -> str:
        """Process user message and return appropriate response"""
        try:
            # Store user message
            self.add_message(user_id, message, "user")
            
            # Analyze message and get response
            response = self._analyze_message(message)
            
            # Store bot response
            self.add_message(user_id, response, "bot")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing chatbot message: {e}")
            return "I'm sorry, I'm experiencing some technical difficulties. Please try again later."
    
    def _analyze_message(self, message: str) -> str:
        """Analyze message content and return appropriate response"""
        message_lower = message.lower().strip()
        
        # Check for greetings
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
            return self._get_random_response('greeting')
        
        # Check for goodbyes
        if any(word in message_lower for word in ['bye', 'goodbye', 'thanks', 'thank you', 'exit']):
            return self._get_random_response('goodbye')
        
        # Check for specific product queries first
        product_response = self._handle_product_query(message_lower)
        if product_response:
            return product_response
        
        # Check for order status
        if any(word in message_lower for word in self.keywords['order_status']):
            return self._get_random_response('order_status')
        
        # Check for product help
        if any(word in message_lower for word in self.keywords['product_help']):
            return self._get_random_response('product_help')
        
        # Check for return/refund
        if any(word in message_lower for word in self.keywords['return_refund']):
            return self._get_random_response('return_refund')
        
        # Check for payment help
        if any(word in message_lower for word in self.keywords['payment_help']):
            return self._get_random_response('payment_help')
        
        # Check for technical support or reporting
        if any(word in message_lower for word in self.keywords['technical_support'] + self.keywords['report_issue']):
            return self._get_random_response('report_issue')
        
        # Check for general help
        if any(word in message_lower for word in self.keywords['general_help']):
            return ("I can help you with:\n"
                   "• Order tracking and status\n"
                   "• Product information and comparisons\n"
                   "• Returns and refunds\n"
                   "• Payment issues\n"
                   "• Technical support and bug reports\n"
                   "What would you like assistance with?")
        
        # Fallback response
        return self._get_random_response('fallback')
    
    def _handle_product_query(self, message: str) -> str:
        """Handle specific product queries with intelligent responses"""
        # Define product categories and their responses
        product_categories = {
            'laptop': {
                'keywords': ['laptop', 'computer', 'notebook'],
                'response': "Great choice! We have a wide selection of laptops including gaming laptops, business laptops, and everyday use computers. Check out our Laptops category at /products or tell me what you'll be using it for!"
            },
            'keyboard': {
                'keywords': ['keyboard', 'mechanical', 'wireless keyboard'],
                'response': "Excellent! We offer mechanical keyboards, wireless keyboards, and gaming keyboards. Our Keyboards category has options for every need. Visit /products or let me know if you prefer mechanical or wireless!"
            },
            'mouse': {
                'keywords': ['mouse', 'gaming mouse', 'wireless mouse'],
                'response': "Perfect! We have gaming mice, wireless mice, and ergonomic office mice. Check out our Mice category at /products. Are you looking for gaming performance or office comfort?"
            },
            'headphones': {
                'keywords': ['headphones', 'headset', 'earbuds', 'wireless headphones'],
                'response': "Awesome! We offer noise-cancelling headphones, gaming headsets, and wireless earbuds. Browse our Headphones category at /products. Do you need them for gaming, music, or calls?"
            },
            'phone': {
                'keywords': ['phone', 'smartphone', 'mobile', 'iphone', 'android'],
                'response': "Great! We have the latest smartphones with cutting-edge features. Check out our Smartphones category at /products. Are you looking for a specific brand or features?"
            },
            'tablet': {
                'keywords': ['tablet', 'ipad', 'android tablet'],
                'response': "Excellent choice! We offer iPads, Android tablets, and 2-in-1 convertible devices. Visit our Tablets category at /products. What size and features are you looking for?"
            },
            'accessories': {
                'keywords': ['accessories', 'cable', 'charger', 'usb', 'hub'],
                'response': "Perfect! We have cables, adapters, cases, and other essential accessories. Browse our Accessories category at /products. What specific accessory do you need?"
            }
        }
        
        # Check if message contains any product category keywords
        for category, info in product_categories.items():
            if any(keyword in message for keyword in info['keywords']):
                return info['response']
        
        return None
    
    def _get_random_response(self, response_type: str) -> str:
        """Get a random response from the specified category"""
        import random
        responses = self.responses.get(response_type, self.responses['fallback'])
        return random.choice(responses)
    
    def add_message(self, user_id: str, message: str, message_type: str = "user"):
        """Add a message to the conversation history"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        chat_message = ChatbotMessage(user_id, message, message_type)
        self.conversations[user_id].append(chat_message)
        
        # Keep only last 50 messages per user
        if len(self.conversations[user_id]) > 50:
            self.conversations[user_id] = self.conversations[user_id][-50:]
    
    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """Get conversation history for a user"""
        if user_id not in self.conversations:
            return []
        
        return [msg.to_dict() for msg in self.conversations[user_id]]
    
    def create_report(self, user_id: str, report_type: str, description: str, priority: str = "medium") -> str:
        """Create a new support report"""
        try:
            report = Report(user_id, report_type, description, priority)
            self.reports[report.id] = report
            
            logger.info(f"Created report {report.id} for user {user_id}")
            
            return (f"✅ Report created successfully!\n\n"
                   f"**Report ID:** {report.id}\n"
                   f"**Type:** {report_type}\n"
                   f"**Priority:** {priority}\n"
                   f"**Status:** Open\n\n"
                   f"Our support team will review your report and get back to you soon. "
                   f"You can check the status of your report using the Report ID.")
            
        except Exception as e:
            logger.error(f"Error creating report: {e}")
            return "I'm sorry, there was an error creating your report. Please try again."
    
    def get_user_reports(self, user_id: str) -> List[Dict]:
        """Get all reports for a user"""
        user_reports = [report for report in self.reports.values() if report.user_id == user_id]
        return [report.to_dict() for report in user_reports]
    
    def get_all_reports(self) -> List[Dict]:
        """Get all reports (for admin)"""
        return [report.to_dict() for report in self.reports.values()]
    
    def update_report_status(self, report_id: str, new_status: str, admin_notes: str = "") -> bool:
        """Update report status (admin only)"""
        if report_id in self.reports:
            report = self.reports[report_id]
            report.status = new_status
            report.admin_notes = admin_notes
            report.updated_at = datetime.now()
            return True
        return False

# Global chatbot instance
chatbot = Chatbot()

def save_chatbot_data():
    """Save chatbot data to file"""
    try:
        data = {
            'conversations': {
                user_id: [msg.to_dict() for msg in messages]
                for user_id, messages in chatbot.conversations.items()
            },
            'reports': {
                report_id: report.to_dict()
                for report_id, report in chatbot.reports.items()
            }
        }
        
        with open('chatbot_data.json', 'w') as f:
            json.dump(data, f, indent=4, default=str)
            
        logger.info("Chatbot data saved successfully")
        
    except Exception as e:
        logger.error(f"Error saving chatbot data: {e}")

def load_chatbot_data():
    """Load chatbot data from file"""
    try:
        if os.path.exists('chatbot_data.json'):
            with open('chatbot_data.json', 'r') as f:
                data = json.load(f)
            
            # Load conversations
            chatbot.conversations = {}
            for user_id, messages_data in data.get('conversations', {}).items():
                chatbot.conversations[user_id] = [
                    ChatbotMessage.from_dict(msg_data) for msg_data in messages_data
                ]
            
            # Load reports
            chatbot.reports = {}
            for report_id, report_data in data.get('reports', {}).items():
                chatbot.reports[report_id] = Report.from_dict(report_data)
            
            logger.info("Chatbot data loaded successfully")
            
    except Exception as e:
        logger.error(f"Error loading chatbot data: {e}")

# Load data on import
import os
load_chatbot_data() 