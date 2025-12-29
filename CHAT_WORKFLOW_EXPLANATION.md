# Chat Feature - Complete Workflow Explanation

## Overview

This document explains how the chat feature works from start to finish, including all steps, data flow, and what happens at each stage.

## Complete Workflow: From Start to Finish

### Phase 1: Diagnostic Completion (Prerequisite)

```
User completes diagnostic
    ↓
Diagnostic status changes to "completed"
    ↓
DiagnosticService automatically:
    1. Links diagnostic to conversation
    2. Creates conversation with category="diagnostic"
    3. Sets diagnostic.conversation_id = conversation.id
```

**Logs:**
- `✅ Diagnostic processing completed`
- `✅ Linked diagnostic {id} to conversation {id}`

---

### Phase 2: User Opens Chat Interface

```
User navigates to Engagement Details → Chat Bot tab
    ↓
Frontend: EngagementChatbot component mounts
    ↓
Frontend checks diagnostic status:
    GET /api/diagnostics/engagement/{engagementId}
    ↓
If diagnostic.status === "completed":
    ✅ Shows category selector
If diagnostic.status !== "completed":
    ❌ Shows "Complete diagnostic first" message
```

**Logs:**
- Frontend: `Checking diagnostic status for engagement: {engagementId}`
- Frontend: `Diagnostic completed: {true/false}`

---

### Phase 3: User Selects Category

```
User sees category selector with 11 options:
    - General, Diagnostic, Financial, Legal & Licensing, etc.
    ↓
User selects a category (e.g., "Financial")
    ↓
Frontend: initializeConversation("financial")
    ↓
Frontend: POST /api/chat/conversations
    Body: {
        category: "financial",
        diagnostic_id: "{completed_diagnostic_id}" (if diagnostic category)
    }
```

**Backend Logs:**
```
🚀 API: Creating/getting conversation
   User ID: {user_id}
   Category: financial
   Diagnostic ID: {diagnostic_id}
```

**Backend Processing:**
```
ChatService.get_or_create_conversation()
    ↓
Step 1: Check if conversation exists for this diagnostic (if diagnostic category)
    ↓
Step 2: Check for most recent diagnostic conversation (if diagnostic category)
    ↓
Step 3: Create new conversation
    - user_id = current_user.id
    - category = "financial"
    - title = "Financial Chat"
    ↓
Step 4: Link diagnostic to conversation (if diagnostic_id provided)
    ↓
Returns: Conversation object
```

**Logs:**
```
🔍 Getting or creating conversation
   User ID: {user_id}
   Category: financial
   Diagnostic ID: {diagnostic_id}
✅ Created new conversation: {conversation_id}
   Title: Financial Chat
✅ Linked diagnostic {diagnostic_id} to conversation {conversation_id}
```

**Frontend:**
```
Receives conversation object
    ↓
Stores: conversation = { id, category, ... }
    ↓
Loads existing messages:
    GET /api/chat/conversations/{conversation_id}/messages
    ↓
If no messages:
    Shows welcome message for selected category
If messages exist:
    Displays all messages in chronological order
```

---

### Phase 4: User Sends Message

```
User types message: "What are my financial weaknesses?"
    ↓
User clicks Send or presses Enter
    ↓
Frontend: handleSendMessage()
    ↓
Frontend: POST /api/chat/conversations/{conversation_id}/messages?engagement_id={engagementId}
    Body: {
        message: "What are my financial weaknesses?"
    }
```

**Backend API Logs:**
```
🚀 API: Sending message to conversation
   Conversation ID: {conversation_id}
   User ID: {user_id}
   Message length: 35 characters
   Engagement ID: {engagement_id}
```

**Backend Processing (ChatService.send_message()):**

#### Step 1: Verify Conversation
```
📨 STEP 1: Starting send_message
   Conversation ID: {conversation_id}
   User ID: {user_id}
   Engagement ID: {engagement_id}

📨 STEP 2: Verifying conversation ownership
   Checks: Conversation exists AND belongs to user
```

**Logs:**
```
✅ Conversation verified: category=financial, user_id={user_id}
```

#### Step 2: Save User Message
```
📨 STEP 3: Saving user message to database
   Creates Message object:
   - conversation_id = {conversation_id}
   - role = "user"
   - message = "What are my financial weaknesses?"
   ↓
   Saves to database
   ↓
   Commits transaction
```

**Logs:**
```
✅ User message saved: message_id={message_id}
```

#### Step 3: Get Conversation History
```
📨 STEP 4: Retrieving conversation history (limit=50)
   Query: SELECT * FROM messages 
          WHERE conversation_id = {conversation_id}
          ORDER BY created_at ASC
          LIMIT 50
```

**Logs:**
```
✅ Retrieved {count} previous messages
```

#### Step 4: Build GPT Context
```
📨 STEP 5: Building GPT context
   - Conversation category: financial
   - Previous messages: {count}
   - Engagement ID: {engagement_id}
```

**Sub-step 4a: Build System Prompt**

**Logs:**
```
🔧 Building system prompt for category: financial
```

**4a.1: Load Base System Prompt**
```
🔧 Loading base system prompt
   Tries: load_prompt("system_prompt")
   ↓
   If file exists:
       ✅ Base system prompt loaded from file ({length} characters)
   If file doesn't exist:
       ⚠️ Using default prompt
```

**4a.2: Add User Name**
```
🔧 Adding user name to prompt
   Query: SELECT * FROM users WHERE id = {user_id}
   ↓
   If user.name exists:
       ✅ User name added: {user_name}
   If not:
       ⚠️ User name not available
```

**4a.3: Load Category Prompt**
```
🔧 Loading category prompt for: financial
   Tries: load_prompt("category_prompt_financial")
   ↓
   If file exists:
       ✅ Category prompt loaded from: category_prompt_financial.md ({length} characters)
   If file doesn't exist:
       🔧 Trying normalized category: financial
       ⚠️ Using default prompt
```

**4a.4: Load Diagnostic Context**
```
🔧 Loading diagnostic context (engagement_id: {engagement_id})
```

**Finding Diagnostic:**
```
🔧 Step 1: Looking for diagnostic linked to conversation {conversation_id}
   Query: SELECT * FROM diagnostics 
          WHERE conversation_id = {conversation_id} 
          AND status = 'completed'
   ↓
   If found:
       ✅ Found diagnostic linked to conversation: {diagnostic_id}
   If not:
       ℹ️ No diagnostic linked to conversation
```

```
🔧 Step 2: Looking for diagnostic by engagement_id: {engagement_id}
   Query: SELECT * FROM diagnostics 
          WHERE engagement_id = {engagement_id} 
          AND status = 'completed'
   ↓
   If found:
       ✅ Found diagnostic by engagement: {diagnostic_id}
   If not:
       ℹ️ No diagnostic found for engagement
```

```
🔧 Step 3: Looking for any completed diagnostic for user {user_id}
   Query: SELECT * FROM diagnostics 
          WHERE created_by_user_id = {user_id} 
          AND status = 'completed'
          ORDER BY completed_at DESC
   ↓
   If found:
       ✅ Found user's most recent diagnostic: {diagnostic_id}
   If not:
       ℹ️ No completed diagnostic found for user
```

**Extracting Diagnostic Data:**
```
✅ Diagnostic found: {diagnostic_id}, building context

🔧 Extracting diagnostic summary
   From: diagnostic.ai_analysis.summary
   ↓
   If exists:
       ✅ Summary added ({length} characters)
   If not:
       ⚠️ No summary in ai_analysis

🔧 Extracting diagnostic advice
   From: diagnostic.ai_analysis.advisorReport
   ↓
   If exists:
       ✅ Advice added ({length} characters)
   If not:
       ⚠️ No advisorReport in ai_analysis

🔧 Extracting Q&A data
   From: diagnostic.user_responses
   ↓
   If exists:
       ✅ Q&A data added ({length} characters)
       (Full JSON of all user responses)
   If not:
       ⚠️ No user_responses available
```

**Logs:**
```
✅ Diagnostic context built: {total_length} total characters
   - Parts included: {count}
```

**Final System Prompt:**
```
✅ System prompt built: total length = {length} characters
```

**Sub-step 4b: Add Conversation History**
```
🔧 Step 2: Adding conversation history ({count} messages)
   For each message:
       - role: "user" or "assistant"
       - content: message text
   ↓
   Adds to messages array
```

**Sub-step 4c: Add Current Message**
```
🔧 Step 3: Adding current user message
   Current message: "What are my financial weaknesses?"
```

**Final Context:**
```
✅ GPT context built: {total_messages} total messages
   - System message: {length} characters
   - Conversation history: {count} messages
   - Current message: {length} characters
```

**Logs:**
```
✅ GPT context built: {count} total messages
```

#### Step 5: Call OpenAI API
```
📨 STEP 6: Calling OpenAI API
   Model: gpt-4o
   Temperature: 0.7
   Messages: {count} messages
   ↓
   OpenAI API call (async, non-blocking)
   ↓
   Waits for response
```

**Logs:**
```
✅ OpenAI response received
   - Model: gpt-4o
   - Response length: {length} characters
   - Tokens used: {tokens}
   - Prompt tokens: {prompt_tokens}
   - Completion tokens: {completion_tokens}
```

**If Error:**
```
❌ Error calling OpenAI: {error_message}
   Returns: "I apologize, but I'm having trouble processing your request..."
```

#### Step 6: Save Assistant Message
```
📨 STEP 7: Saving assistant message to database
   Creates Message object:
   - conversation_id = {conversation_id}
   - role = "assistant"
   - message = "{AI response text}"
   - response_data = {
       model: "gpt-4o",
       tokens_used: {count},
       prompt_tokens: {count},
       completion_tokens: {count}
     }
   - message_metadata = { model: "gpt-4o" }
   ↓
   Saves to database
   ↓
   Commits transaction
```

**Logs:**
```
✅ Assistant message saved: message_id={message_id}
```

#### Step 7: Update Conversation Timestamp
```
📨 STEP 8: Updating conversation timestamp
   conversation.updated_at = datetime.utcnow()
   ↓
   Commits transaction
```

**Logs:**
```
✅ Conversation updated: updated_at={timestamp}
🎉 Message processing complete!
```

**API Response:**
```
✅ API: Message sent successfully
   Assistant message ID: {message_id}
   Response length: {length} characters
```

**Returns to Frontend:**
```json
{
  "id": "{message_id}",
  "conversation_id": "{conversation_id}",
  "role": "assistant",
  "message": "{AI response text}",
  "response_data": { ... },
  "metadata": { ... },
  "created_at": "{timestamp}",
  "updated_at": "{timestamp}"
}
```

---

### Phase 5: Frontend Displays Response

```
Frontend receives assistant message
    ↓
Adds to messages array
    ↓
Displays in chat UI
    ↓
Auto-scrolls to bottom
    ↓
User sees response
```

---

## Complete Context Sent to LLM

For **EVERY** message, the LLM receives this structure:

```python
[
    {
        "role": "system",
        "content": """
            [Base System Prompt from system_prompt.md]
            - Trinity AI identity and role
            - Instructions for behavior
            
            The user's name is {user.name}.
            
            [Category Prompt from category_prompt_{category}.md]
            - Category-specific instructions
            - Scope and conversational rules
            - Example: Financial mode, Legal mode, etc.
            
            [Diagnostic Context - FOR ALL CATEGORIES]
            Use the following information from the user's completed diagnostic to respond...
            
            Diagnostic Summary:
            {diagnostic.ai_analysis.summary}
            - High-level overview
            - Key findings
            - Critical issues
            
            Diagnostic Advice:
            {diagnostic.ai_analysis.advisorReport}
            - Full advisor report (HTML/text)
            - Module findings
            - Task recommendations
            
            Diagnostic Q&A Data:
            {json.dumps(diagnostic.user_responses, indent=2)}
            - Complete JSON of all 200+ question responses
            - All user answers
            - Full diagnostic data
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
    // ... (up to 50 previous messages, chronologically ordered)
    {
        "role": "user",
        "content": "[Current user message]"
    }
]
```

---

## Key Points

### ✅ Diagnostic Context for ALL Categories
- **Not just "diagnostic" category**
- **ALL categories** (Financial, Legal, Operations, etc.) get diagnostic context
- This means the LLM always has access to:
  - Diagnostic summary
  - Diagnostic advice
  - Full Q&A responses

### ✅ Category-Specific Prompts
- Each category loads its specific prompt file
- Prompts guide LLM behavior for that category
- Example: Financial mode focuses on cash-flow, EBITDA, etc.

### ✅ Conversation History
- Last 50 messages included
- Maintains conversation continuity
- LLM can reference previous exchanges

### ✅ Error Handling
- Comprehensive logging at each step
- Graceful error handling
- User-friendly error messages

---

## Summary

**Complete Flow:**
1. User completes diagnostic → Chat becomes available
2. User selects category → Conversation created/retrieved
3. User sends message → Backend:
   - Saves user message
   - Gets conversation history
   - Builds GPT context (system + category + diagnostic + history)
   - Calls OpenAI
   - Saves assistant response
4. Frontend displays response
5. Process repeats for each message

**Context Includes:**
- Base system prompt
- User's name
- Category-specific prompt
- **Diagnostic context (for ALL categories)**
- Conversation history (last 50 messages)
- Current user message

**Logging:**
- Every step is logged with emojis for easy identification
- Detailed information at each stage
- Error logging with stack traces
- Token usage and response metrics

The chat feature is fully functional with comprehensive logging! 🎉

