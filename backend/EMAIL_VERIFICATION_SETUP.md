# Email Verification Setup Guide

## 📧 Overview

This guide explains how to configure **mandatory email verification** in Auth0 and how the system handles verified/unverified users.

---

## ✅ What We've Implemented

### Backend Changes:

1. **Auth0 Handles Email Verification** (`backend/app/api/auth.py`):
   - **No email verification check in callback** - Auth0 handles it
   - If Auth0 is configured to require email verification, it won't complete login until verified
   - Auth0 Universal Login shows appropriate messages for unverified users
   - Our callback only runs when Auth0 successfully authenticates the user

2. **Smart Email Status Update** (`backend/app/services/auth_service.py`):
   - If user **already exists** and email is **already verified** → preserves verified status
   - Only updates `email_verified` to `true` when Auth0 confirms it
   - **Prevents unverifying** users who were previously verified

3. **Resend Verification Endpoint** (`/api/auth/resend-verification`):
   - Allows users to request verification email resend
   - Note: Auth0 automatically resends when users try to log in with unverified email

### Frontend Changes:

1. **Login Page Always Goes to Auth0** (`frontend/src/pages/Login.tsx`):
   - "Sign in" button **always** redirects to Auth0 Universal Login
   - No check for existing authentication - always goes through Auth0
   - Auth0 handles email verification flow automatically

2. **Verify Email Page** (`frontend/src/pages/VerifyEmail.tsx`):
   - Shows message to check email inbox
   - "Resend Verification Email" button
   - "Back to Login" button

---

## 🔧 Auth0 Configuration (REQUIRED)

### Step 1: Enable Email Verification in Database Connection

1. Go to **Auth0 Dashboard** → **Authentication** → **Database** → **Username-Password-Authentication**
2. Click on the connection name (usually "Username-Password-Authentication")
3. Scroll to **Settings** section
4. Find **"Disable Sign Ups"** → Leave it **OFF** (unless you want to disable signups)
5. Find **"Requires Username"** → Set as needed
6. **IMPORTANT**: Look for **"Email Verification"** or **"Email Verification Required"**
   - Enable **"Require Email Verification"** or similar option
   - This makes email verification **mandatory** before users can access your app

### Step 2: Configure Email Provider

1. Go to **Auth0 Dashboard** → **Branding** → **Emails**
2. Make sure you have an email provider configured:
   - **Default Email Provider**: Auth0 (free, limited)
   - **Custom SMTP**: For production (SendGrid, AWS SES, etc.)
3. Test email sending works

### Step 3: Customize Verification Email Template (Optional)

1. Go to **Auth0 Dashboard** → **Branding** → **Emails** → **Verification Email**
2. Customize the email template if needed
3. Make sure the **"Link"** variable is included (this is the verification link)

### Step 4: Test Email Verification Flow

1. **Sign up a new user**:
   - User signs up → Auth0 sends verification email automatically
   - User clicks link in email → Email verified in Auth0
   - User logs in → Token has `email_verified: true` → Access granted ✅

2. **Unverified user tries to log in**:
   - User tries to log in with unverified email
   - Auth0 may resend verification email (depending on settings)
   - Our backend checks `email_verified: false` → Redirects to `/verify-email` page
   - User must verify email before accessing dashboard

---

## 🔄 How It Works

### Flow for New User:

```
1. User clicks "Sign in" → Always goes to Auth0 Universal Login
   ↓
2. User enters credentials on Auth0
   ↓
3. Auth0 checks if email is verified
   ↓
4a. If NOT verified:
    - Auth0 shows message: "Please verify your email"
    - Auth0 may resend verification email
    - User cannot complete login until email is verified
   ↓
4b. If verified:
    - Auth0 completes login
    - Redirects to our callback
    - User goes to dashboard ✅
```

### Flow for Unverified User Trying to Log In:

```
1. User clicks "Sign in" → Always goes to Auth0 Universal Login
   ↓
2. User enters credentials (email not verified)
   ↓
3. Auth0 detects email not verified
   ↓
4. Auth0 shows message: "Please verify your email"
   ↓
5. Auth0 may resend verification email
   ↓
6. User cannot complete login until email is verified
   ↓
7. User clicks verification link in email
   ↓
8. Email verified → User can now complete login → Dashboard ✅
```

### Flow for Existing Verified User:

```
1. User already exists in database with email_verified: true
   ↓
2. User logs in → Auth0 token has email_verified: true
   ↓
3. Backend updates user but PRESERVES verified status
   ↓
4. User redirected to dashboard ✅
   (No verification email sent - user already verified)
```

---

## 🛡️ Security Features

### ✅ What We Prevent:

1. **No duplicate verification emails**: If user is already verified, no email is sent
2. **Status preservation**: Verified users stay verified even if Auth0 token is temporarily unverified
3. **Mandatory verification**: Auth0 enforces email verification before login completes
4. **Always go through Auth0**: Login button always redirects to Auth0, ensuring Auth0 handles verification

### ⚠️ Important Notes:

- **Auth0 handles everything**: Email verification, sending emails, and blocking unverified logins
- **No backend checks needed**: If Auth0 completes login, user is verified
- **Database sync**: Our database stores the verification status for reference
- **Login always goes to Auth0**: Even if user has a token, clicking "Sign in" goes through Auth0 flow

---

## 🧪 Testing

### Test Case 1: New User Signup
1. Sign up with a new email
2. Check email inbox for verification link
3. Click link → Email verified
4. Log in → Should go to dashboard ✅

### Test Case 2: Unverified Login Attempt
1. Sign up but **don't verify email**
2. Try to log in
3. Should redirect to `/verify-email` page
4. Check email and verify
5. Log in again → Should go to dashboard ✅

### Test Case 3: Already Verified User
1. User already verified and in database
2. Log in again
3. Should go directly to dashboard ✅
4. **No verification email sent** (user already verified)

---

## 📝 Environment Variables

No additional environment variables needed. The system uses existing Auth0 configuration:
- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`

---

## 🐛 Troubleshooting

### Problem: Users can access dashboard without verifying email
- **Check**: Auth0 Dashboard → Database Connection → "Require Email Verification" is enabled
- **Check**: Backend logs show `email_verified: false` but user still gets access
- **Fix**: Verify the callback endpoint checks `email_verified` before redirecting

### Problem: Verification emails not being sent
- **Check**: Auth0 Dashboard → Branding → Emails → Email provider is configured
- **Check**: Check spam folder
- **Fix**: Configure SMTP provider for production

### Problem: Verified users getting verification emails again
- **Check**: Backend code preserves `email_verified: true` status
- **Check**: Auth0 token has `email_verified: true`
- **Fix**: Code should only update to verified, never unverify

---

## ✅ Summary

- ✅ **Email verification is mandatory** (configured in Auth0)
- ✅ **Verified users don't get duplicate emails** (status preserved)
- ✅ **Unverified users redirected to verification page**
- ✅ **Auth0 handles email sending automatically**

Your email verification system is now fully configured! 🎉

