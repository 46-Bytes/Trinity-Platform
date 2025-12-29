# Chat Category Implementation - Complete Guide

## Overview

The chat feature now supports **multiple categories** with category-specific prompts, and **diagnostic context is included for ALL categories** (not just diagnostic category).

## Implementation Summary

### ✅ What's Implemented

1. **Category Selection (Frontend)**
   - User selects from 11 available categories
   - Categories match the prompt files in `backend/files/prompts/`
   - Only shows chat after diagnostic is completed

2. **Category Prompts (Backend)**
   - Loads category-specific prompts from `backend/files/prompts/category_prompt_{category}.md`
   - Handles category name variations (e.g., "finance" → "financial")
   - Falls back to defaults if file doesn't exist

3. **Diagnostic Context (Backend)**
   - **Included for ALL categories** (not just "diagnostic")
   - Includes:
     - Diagnostic Summary (`ai_analysis.summary`)
     - Diagnostic Advice (`ai_analysis.advisorReport`)
     - Q&A Extract (`user_responses` - full JSON)
   - Finds diagnostic by:
     1. Conversation link (if conversation linked to diagnostic)
     2. Engagement ID (if provided)
     3. User's most recent completed diagnostic

4. **Conversation History**
   - Last 50 messages included in LLM context
   - Messages ordered chronologically
   - Full conversation history maintained

## Available Categories

Based on prompt files in `backend/files/prompts/`:

1. **General** (`general`)
   - General business advisory
   - File: `category_prompt_general.md`

2. **Diagnostic** (`diagnostic`)
   - About diagnostic results
   - File: `category_prompt_diagnostic.md`

3. **Financial** (`financial`)
   - Financial clarity & reporting
   - File: `category_prompt_financial.md`

4. **Legal & Licensing** (`legal-licensing`)
   - Legal, compliance & property
   - File: `category_prompt_legal-licensing.md`

5. **Operations** (`operations`)
   - Owner dependency & operations
   - File: `category_prompt_operations.md`

6. **People & HR** (`human-resources`)
   - HR, culture and workforce planning
   - File: `category_prompt_human-resources.md`

7. **Customers & Products** (`customers`)
   - Product fit, margins, customers and pricing
   - File: `category_prompt_customers.md`

8. **Tax & Regulatory** (`tax`)
   - Tax, compliance & regulatory matters
   - File: `category_prompt_tax.md`

9. **Due Diligence** (`due-diligence`)
   - Data-room and vendor readiness
   - File: `category_prompt_due-diligence.md`

10. **Competitive Forces** (`competitive-forces`)
    - Market analysis and competitive positioning
    - File: `category_prompt_competitive-forces.md`

11. **Financial Documents** (`financial-docs`)
    - Financial document analysis
    - File: `category_prompt_financial-docs.md`

## Workflow

### Step 1: User Completes Diagnostic
```
User completes diagnostic → Status: "completed"
    ↓
Diagnostic automatically linked to conversation
    ↓
Chat becomes available
```

### Step 2: User Selects Category
```
User opens Chat Bot tab
    ↓
Checks if diagnostic is completed
    ↓
If YES → Shows category selector
If NO → Shows "Complete diagnostic first" message
    ↓
User selects category (e.g., "Financial")
    ↓
Creates/gets conversation for that category
```

### Step 3: User Sends Message
```
User types message and sends
    ↓
POST /api/chat/conversations/{id}/messages?engagement_id={id}
    ↓
Backend: ChatService.send_message()
    1. Saves user message
    2. Gets conversation history (last 50 messages)
    3. Builds GPT context:
       a. System prompt (base + user name)
       b. Category prompt (from category_prompt_{category}.md)
       c. Diagnostic context (for ALL categories):
          - Diagnostic Summary
          - Diagnostic Advice
          - Q&A Extract
       d. Conversation history (last 50 messages)
       e. Current user message
    4. Calls OpenAI API
    5. Saves assistant response
    6. Returns response
    ↓
Frontend displays response
```

## Context Sent to LLM

For **EVERY** chat message, the LLM receives:

```python
[
    {
        "role": "system",
        "content": """
            [Base System Prompt from system_prompt.md]
            
            The user's name is {user.name}.
            
            [Category Prompt from category_prompt_{category}.md]
            
            [Diagnostic Context - FOR ALL CATEGORIES]
            Use the following information from the user's completed diagnostic to respond...
            
            Diagnostic Summary:
            {diagnostic.ai_analysis.summary}
            
            Diagnostic Advice:
            {diagnostic.ai_analysis.advisorReport}
            
            Diagnostic Q&A Data:
            {json.dumps(diagnostic.user_responses, indent=2)}
        """
    },
    {
        "role": "user",
        "content": "[Previous message 1]"
    },
    {
        "role": "assistant",
        "content": "[Previous response 1]"
    },
    // ... (up to 50 previous messages)
    {
        "role": "user",
        "content": "[Current user message]"
    }
]
```

## Key Points

### ✅ Diagnostic Context for ALL Categories
- **Not just "diagnostic" category** - ALL categories get diagnostic context
- This means when user chats about "Financial" or "Legal", the LLM still has access to:
  - Their diagnostic summary
  - Their diagnostic advice
  - Their Q&A responses

### ✅ Category-Specific Prompts
- Each category loads its specific prompt from `category_prompt_{category}.md`
- Prompts guide the LLM on how to respond for that category
- Handles variations (e.g., "finance" → "financial")

### ✅ Conversation History
- Last 50 messages included in context
- Maintains conversation continuity
- Messages ordered chronologically

### ✅ Diagnostic Completion Requirement
- Chat is only available after diagnostic is completed
- Frontend checks diagnostic status before showing chat
- Backend includes diagnostic context for all categories

## Files Modified

### Backend
- `backend/app/services/chat_service.py`
  - Updated `_get_diagnostic_context()` to accept `engagement_id`
  - Updated to find diagnostic by engagement if not linked to conversation
  - Updated `_get_category_prompt()` to handle all category variations
  - Updated `_build_system_prompt()` to include diagnostic context for ALL categories
  - Updated `send_message()` to accept `engagement_id` parameter

- `backend/app/api/chat.py`
  - Updated `send_message()` endpoint to accept `engagement_id` query parameter
  - Passes `engagement_id` to `ChatService.send_message()`

### Frontend
- `frontend/src/components/engagement/chatbot/EngagementChatbot.tsx`
  - Updated `ChatCategory` type to include all 11 categories
  - Updated `CATEGORY_OPTIONS` to show all available categories
  - Updated welcome messages for all categories
  - Updated message sending to include `engagement_id` in URL

## Testing Checklist

- [x] Chat only available after diagnostic completion
- [x] Category selector shows all 11 categories
- [x] Category prompts load correctly from files
- [x] Diagnostic context included for ALL categories
- [x] Conversation history included (last 50 messages)
- [x] Engagement ID passed to backend for diagnostic lookup
- [x] Welcome messages match selected category

## Example Flow

1. **User completes diagnostic** → Status: "completed"
2. **User opens Chat Bot tab** → Sees category selector
3. **User selects "Financial"** → Creates conversation with category="financial"
4. **User sends message**: "What are my financial weaknesses?"
5. **Backend builds context**:
   - System prompt (base + user name)
   - Financial category prompt (from `category_prompt_financial.md`)
   - **Diagnostic context** (summary, advice, Q&A)
   - Conversation history (if any)
   - Current message
6. **LLM responds** with financial advice referencing diagnostic data
7. **Response saved** and displayed to user

## Summary

✅ **All categories are implemented**
✅ **Diagnostic context included for ALL categories**
✅ **Category prompts loaded from files**
✅ **Conversation history included**
✅ **Chat only available after diagnostic completion**

The implementation matches your requirements!

