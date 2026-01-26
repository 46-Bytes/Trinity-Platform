"""
Auth0 Management API integration for user management.
"""
import logging
import requests
import secrets
import string
import re
import time
from typing import Optional, Dict
from datetime import datetime, timedelta
from ..config import settings
from .email_service import EmailService
import json

logger = logging.getLogger(__name__)


class Auth0Management:
    """Helper class for Auth0 Management API operations."""
    
    _access_token = None
    _token_expiry = None
    
    @classmethod
    def get_management_token(cls) -> str:
        """
        Get Auth0 Management API access token.
        Caches token and refreshes when expired.
        
        Returns:
            str: Access token for Management API
        """
        # Return cached token if still valid
        if cls._access_token and cls._token_expiry and datetime.utcnow() < cls._token_expiry:
            return cls._access_token
        
        # Request new token
        token_url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
        
        payload = {
            "client_id": settings.AUTH0_MANAGEMENT_CLIENT_ID,
            "client_secret": settings.AUTH0_MANAGEMENT_CLIENT_SECRET,
            "audience": settings.AUTH0_MANAGEMENT_API_AUDIENCE,
            "grant_type": "client_credentials"
        }
        
        try:
            response = requests.post(token_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            cls._access_token = data["access_token"]
            
            # Set expiry to 5 minutes before actual expiry for safety
            expires_in = data.get("expires_in", 86400)  # Default 24 hours
            cls._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 300)
            
            logger.info("✅ Auth0 Management API token obtained successfully")
            return cls._access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to get Management API token: {e}")
            raise Exception(f"Failed to authenticate with Auth0 Management API: {e}")
    
    @classmethod
    def create_user(
        cls,
        email: str,
        role: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict:
        """
        Create a new user in Auth0 and send password setup email.
        
        This is for ADMIN-INVITED users only (Flow 2).
        Self-signup users (Flow 1) go through normal Auth0 Universal Login.
        
        Args:
            email: User's email address
            role: User's role (will be stored in app_metadata)
            first_name: User's first name (optional)
            last_name: User's last name (optional)
            
        Returns:
            Dict: Created user data from Auth0
            
        Raises:
            Exception: If user creation fails
        """
        token = cls.get_management_token()
        
        # Generate a secure temporary password
        # User will set their own password via the password change email
        # This password is never shared with the user
        alphabet = string.ascii_letters + string.digits + string.punctuation
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # Generate initial username from email (part before @)
        # User can change this when they set their password via the password change email
        # Auth0 requires username to meet length criteria (typically 1-15 chars, minimum 1)
        email_prefix = email.split('@')[0] if '@' in email else email
        
        # Clean and validate email prefix
        email_prefix = email_prefix.strip()
        
        # Generate username ensuring it meets Auth0 requirements (min 1 char, max 15 chars)
        # Remove any invalid characters (keep only alphanumeric, underscore, hyphen, dot)
        email_prefix = re.sub(r'[^a-zA-Z0-9._-]', '', email_prefix)
        
        # If email prefix is empty or too short, create a valid username
        # Auth0 typically requires username to be at least 1 char, but we'll ensure 3+ for compatibility
        if not email_prefix or len(email_prefix) < 1:
            # Generate username from email domain or use fallback
            if '@' in email:
                domain_part = email.split('@')[1].split('.')[0][:6] if '.' in email.split('@')[1] else email.split('@')[1][:6]
                domain_part = re.sub(r'[^a-zA-Z0-9._-]', '', domain_part)
                initial_username = f"user{domain_part}"[:15] if domain_part else f"user{email.split('@')[0][:8]}"[:15]
            else:
                # Use timestamp-based username as last resort
                timestamp_suffix = str(int(time.time()))[-8:]  # Last 8 digits
                initial_username = f"user{timestamp_suffix}"[:15]
        elif len(email_prefix) < 3:
            # If prefix is 1-2 chars, pad it to ensure minimum length of 3
            if '@' in email:
                domain_part = email.split('@')[1].split('.')[0][:2] if '.' in email.split('@')[1] else email.split('@')[1][:2]
                domain_part = re.sub(r'[^a-zA-Z0-9._-]', '', domain_part)
                initial_username = f"{email_prefix}{domain_part}"[:15] if domain_part else f"{email_prefix}xx"[:15]
            else:
                # Use prefix + short numeric suffix
                suffix = str(int(time.time()))[-2:]  # Last 2 digits
                initial_username = f"{email_prefix}{suffix}"[:15]
        else:
            # Use email prefix, but truncate to 15 chars (Auth0 typical max)
            initial_username = email_prefix[:15]
        
        # Final validation: ensure username is valid (at least 3 chars for safety, max 15)
        initial_username = initial_username.strip()
        if not initial_username or len(initial_username) < 3:
            # Absolute fallback - ensure at least 3 characters
            timestamp_suffix = str(int(time.time()))[-12:]  # Last 12 digits
            initial_username = f"usr{timestamp_suffix}"[:15]
        
        logger.info(f"Generated username for {email}: {initial_username} (length: {len(initial_username)})")
        
        # Prepare user data
        user_data = {
            "email": email,
            "username": initial_username,  # Initial username from email, user can change it later
            "connection": "Username-Password-Authentication",  # Your Auth0 DB connection name
            "password": temp_password,  # Required by Auth0, but user will change it via email
            "email_verified": False,
            "verify_email": False,  # Don't send verification email
            "app_metadata": {
                "role": role
            }
        }
        
        # Add optional fields
        if first_name:
            user_data["given_name"] = first_name
        if last_name:
            user_data["family_name"] = last_name
        
        # Create user in Auth0
        create_url = f"https://{settings.AUTH0_DOMAIN}/api/v2/users"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(create_url, json=user_data, headers=headers)
            response.raise_for_status()
            
            user = response.json()
            auth0_user_id = user["user_id"]
            
            
            # Build user name for email personalization
            user_name = None
            if first_name or last_name:
                name_parts = []
                if first_name:
                    name_parts.append(first_name)
                if last_name:
                    name_parts.append(last_name)
                user_name = " ".join(name_parts)
            
            # Send password setup email via custom Gmail SMTP
            try:
                cls.send_password_setup_email(
                    auth0_user_id, 
                    email=email,
                    user_name=user_name
                )
            except Exception as email_error:
                # Log the error but don't fail user creation
                # The user exists in Auth0, they just need to request password reset manually
                raise
            
            return user
            
        except requests.exceptions.HTTPError as e:
            error_detail = e.response.json() if e.response.content else str(e)
            
            # Handle specific error cases
            if e.response.status_code == 409:
                raise Exception(f"User with email {email} already exists in Auth0")
            
            raise Exception(f"Failed to create user in Auth0: {error_detail}")
    
    @classmethod
    def send_password_setup_email(
        cls, 
        auth0_user_id: str, 
        email: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> Dict:
        """
        Send password change/setup email to user using custom Gmail SMTP.
        
        This method:
        1. Creates a password change ticket via Auth0 Management API (to get the reset URL)
        2. Sends a custom email using Gmail SMTP with the password reset link
        
        Args:
            auth0_user_id: Auth0 user ID (format: auth0|xxxxx)
            email: User's email address (required)
            user_name: User's name for personalization (optional)
            
        Returns:
            Dict: Response containing ticket URL and email status
        """
        if not email:
            raise Exception("Email address is required to send password setup email")
        
        token = cls.get_management_token()
        
        # Step 1: Create password change ticket via Auth0 Management API
        ticket_url = f"https://{settings.AUTH0_DOMAIN}/api/v2/tickets/password-change"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "result_url": f"{settings.FRONTEND_URL}/login",
            "user_id": auth0_user_id,
            "ttl_sec": 432000,
            "mark_email_as_verified": True,
            "includeEmailInRedirect": False
        }

        try:
            # Create password change ticket
            response = requests.post(ticket_url, headers=headers, json=payload)
            
            if not response.ok:
                error_detail = "Unknown error"
                try:
                    error_json = response.json()
                    error_detail = error_json.get("message", error_json.get("error", str(response.text)))
                except:
                    error_detail = response.text or f"HTTP {response.status_code}"
                
                raise Exception(
                    f"Failed to create password change ticket: {response.status_code} - {error_detail}"
                )
            
            result = response.json()
            ticket_link = result.get('ticket', None)
            
            if not ticket_link:
                raise Exception("Failed to get ticket URL from Auth0 response")
            
            logger.info(f"✅ Password change ticket created")
            logger.info(f"Ticket URL: {ticket_link}")
            
            # Step 2: Send custom email via Gmail SMTP
            logger.info(f"\nStep 2: Sending custom email via Gmail SMTP...")
            email_sent = EmailService.send_password_setup_email(
                recipient_email=email,
                password_reset_url=ticket_link,
                user_name=user_name
            )
            
            if not email_sent:
                raise Exception("Failed to send email via Gmail SMTP")
            
            return {
                "ticket": ticket_link,
                "email_sent": True,
                "email_provider": "Gmail SMTP"
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_json = e.response.json()
                    error_msg = error_json.get("message", error_json.get("error", error_msg))
                except:
                    error_msg = e.response.text or error_msg
            logger.error(f"❌ Failed to send password setup email: {error_msg}")
            raise Exception(f"Failed to send password setup email: {error_msg}")
    
    @classmethod
    def update_user_role(cls, auth0_user_id: str, role: str) -> Dict:
        """
        Update user's role in Auth0 app_metadata.
        
        Args:
            auth0_user_id: Auth0 user ID
            role: New role value
            
        Returns:
            Dict: Updated user data
        """
        token = cls.get_management_token()
        
        update_url = f"https://{settings.AUTH0_DOMAIN}/api/v2/users/{auth0_user_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "app_metadata": {
                "role": role
            }
        }
        
        try:
            response = requests.patch(update_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update user role in Auth0: {e}")