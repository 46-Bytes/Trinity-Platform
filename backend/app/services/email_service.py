"""
Email service for sending emails via SMTP (Gmail).
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""
    
    @staticmethod
    def send_password_setup_email(
        recipient_email: str,
        password_reset_url: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send password setup email to a user.
        
        Args:
            recipient_email: User's email address
            password_reset_url: URL for password reset (from Auth0 ticket)
            user_name: User's name (optional, defaults to email)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Set Up Your Password - Trinity Platform'
            msg['From'] = settings.SMTP_FROM_EMAIL
            msg['To'] = recipient_email
            
            # Use name if provided, otherwise use email
            display_name = user_name or recipient_email.split('@')[0]
            
            # Create HTML email body
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background-color: #f9f9f9;
                        border-radius: 8px;
                        padding: 30px;
                        margin: 20px 0;
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        color: #2563eb;
                        margin: 0;
                    }}
                    .content {{
                        background-color: white;
                        padding: 25px;
                        border-radius: 6px;
                        margin: 20px 0;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 30px;
                        background-color: #2563eb;
                        color: white !important;
                        text-decoration: none;
                        border-radius: 6px;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .button:hover {{
                        background-color: #1d4ed8;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 30px;
                        color: #666;
                        font-size: 12px;
                    }}
                    .link {{
                        color: #2563eb;
                        word-break: break-all;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to Trinity Platform</h1>
                    </div>
                    
                    <div class="content">
                        <p>Hello {display_name},</p>
                        
                        <p>You've been invited to join Trinity Platform! To get started, please set up your password by clicking the button below:</p>
                        
                        <div style="text-align: center;">
                            <a href="{password_reset_url}" class="button">Set Up Password</a>
                        </div>
                        
                        <p>Or copy and paste this link into your browser:</p>
                        <p><a href="{password_reset_url}" class="link">{password_reset_url}</a></p>
                        
                        <p><strong>This link will expire in 5 days.</strong></p>
                        
                        <p>If you didn't request this invitation, please ignore this email.</p>
                        
                        <p>Best regards,<br>The Trinity Platform Team</p>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated email. Please do not reply to this message.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Create plain text version
            text_body = f"""
Welcome to Trinity Platform!

Hello {display_name},

You've been invited to join Trinity Platform! To get started, please set up your password by visiting the link below:

{password_reset_url}

This link will expire in 5 days.

If you didn't request this invitation, please ignore this email.

Best regards,
The Trinity Platform Team
            """
            
            # Attach both versions
            text_part = MIMEText(text_body, 'plain')
            html_part = MIMEText(html_body, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()  # Enable TLS encryption
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            return True
            
        except smtplib.SMTPException as e:
            return False
        except Exception as e:
            return False
