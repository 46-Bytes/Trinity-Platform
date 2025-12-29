# Chat Feature Frontend-Backend Integration

## Overview

The chat feature has been fully integrated between the frontend and backend. Users can now chat with Trinity AI about their diagnostic results, but **only after completing a diagnostic**.

## Integration Summary

### ✅ Backend Components (Already Implemented)

1. **Database Models**
   - `Conversation` - Chat sessions with categories
   - `Message` - Individual messages (user/assistant)
   - `Diagnostic.conversation_id` - Links diagnostics to conversations

2. **Services**
   - `ChatService` - Handles conversation management, message sending, GPT context building
   - `DiagnosticService` - Automatically links conversations when diagnostics complete

3. **API Endpoints** (`/api/chat`)
   - `GET /api/chat/conversations` - List user conversations
   - `POST /api/chat/conversations` - Create/get conversation
   - `GET /api/chat/conversations/{id}/messages` - Get messages
   - `POST /api/chat/conversations/{id}/messages` - Send message
   - `POST /api/chat/messages/{id}/create-task` - Create task from message
   - `POST /api/chat/messages/{id}/create-note` - Create note from message

4. **Router Registration**
   - Chat router is registered in `backend/app/main.py`

### ✅ Frontend Components (Updated)

1. **EngagementChatbot Component** (`frontend/src/components/engagement/chatbot/EngagementChatbot.tsx`)
   - ✅ Checks if diagnostic is completed before allowing chat
   - ✅ Gets or creates conversation for the diagnostic
   - ✅ Loads existing messages on initialization
   - ✅ Sends messages to correct API endpoints
   - ✅ Handles errors gracefully
   - ✅ Shows appropriate loading/error states

## Workflow

### 1. User Opens Chat Tab

```
User navigates to Engagement Details → Chat Bot tab
    ↓
Frontend checks: GET /api/diagnostics/engagement/{engagementId}
    ↓
Checks if any diagnostic has status="completed"
    ↓
If NO → Shows "Chat not available" message
If YES → Proceeds to initialize chat
```

### 2. Chat Initialization

```
Step 1: Check Diagnostic Status
    GET /api/diagnostics/engagement/{engagementId}
    ↓
    Find diagnostic with status="completed"
    
Step 2: Get or Create Conversation
    POST /api/chat/conversations
    Body: {
        category: "diagnostic",
        diagnostic_id: "{completed_diagnostic_id}"
    }
    ↓
    Backend: ChatService.get_or_create_conversation()
    - Checks if conversation exists for this diagnostic
    - If exists, returns it
    - If not, creates new conversation and links diagnostic
    
Step 3: Load Existing Messages
    GET /api/chat/conversations/{conversation_id}/messages
    ↓
    Returns all messages in chronological order
    ↓
    If no messages, shows welcome message
```

### 3. User Sends Message

```
User types message and clicks Send
    ↓
Frontend: Optimistically adds user message to UI
    ↓
POST /api/chat/conversations/{conversation_id}/messages
Body: {
    message: "user's message text"
}
    ↓
Backend: ChatService.send_message()
    1. Saves user message to database
    2. Gets conversation history (last 50 messages)
    3. Builds GPT context:
       - System prompt (base + category + diagnostic context)
       - Conversation history
       - Current user message
    4. Calls OpenAI API
    5. Saves assistant response
    6. Returns assistant message
    ↓
Frontend: Adds assistant response to UI
```

## Key Features

### 1. Diagnostic Completion Requirement

**Frontend Check:**
- Component checks if diagnostic is completed before allowing chat
- Shows informative message if diagnostic not completed
- Only proceeds if `status === 'completed'`

**Backend Link:**
- When diagnostic completes, `DiagnosticService` automatically:
  - Creates/gets conversation with `category="diagnostic"`
  - Links diagnostic to conversation: `diagnostic.conversation_id = conversation.id`

### 2. Conversation Management

**Automatic Creation:**
- Conversation is created automatically when diagnostic completes
- Frontend uses `POST /api/chat/conversations` to get or create conversation
- Backend `get_or_create_conversation()` handles:
  - Reusing existing diagnostic conversation if available
  - Creating new conversation if needed
  - Linking diagnostic to conversation

### 3. Message History

**Loading:**
- Frontend loads all existing messages on initialization
- Messages are displayed in chronological order
- Welcome message shown if no messages exist

**Persistence:**
- All messages are saved to database
- Conversation history is maintained across sessions
- Last 50 messages included in GPT context

### 4. GPT Context

**What's Included:**
1. **System Prompt:**
   - Base prompt (Trinity AI identity)
   - User's name
   - Category-specific prompt
   - **Diagnostic context** (if linked):
     - Diagnostic summary
     - Advisor report
     - Q&A extract (user responses)

2. **Conversation History:**
   - Last 50 messages (user + assistant)

3. **Current Message:**
   - User's current question

### 5. Error Handling

**Frontend:**
- Shows loading state during initialization
- Shows error if diagnostic not completed
- Shows error if conversation creation fails
- Handles API errors gracefully
- Removes optimistic messages on error

**Backend:**
- Validates conversation ownership
- Handles OpenAI API errors
- Returns appropriate HTTP status codes

## API Endpoints Used

### Diagnostic Endpoints
- `GET /api/diagnostics/engagement/{engagementId}` - Check diagnostic status

### Chat Endpoints
- `POST /api/chat/conversations` - Get or create conversation
- `GET /api/chat/conversations/{id}/messages` - Load messages
- `POST /api/chat/conversations/{id}/messages` - Send message

## State Management

### Frontend State
```typescript
- messages: Message[] - Chat messages
- conversation: Conversation | null - Current conversation
- input: string - User input text
- isLoading: boolean - Sending message state
- isInitializing: boolean - Initialization state
- diagnosticCompleted: boolean - Diagnostic completion status
- error: string | null - Error message
```

## UI States

1. **Initializing:** Shows loading spinner
2. **Diagnostic Not Completed:** Shows informative alert
3. **Error:** Shows error alert
4. **Ready:** Shows chat interface with messages and input

## Testing Checklist

- [x] Chat router registered in main.py
- [x] Frontend checks diagnostic completion
- [x] Conversation get/create works
- [x] Messages load correctly
- [x] Sending messages works
- [x] Error handling works
- [x] Diagnostic automatically links to conversation on completion

## Files Modified

### Frontend
- `frontend/src/components/engagement/chatbot/EngagementChatbot.tsx` - Complete rewrite

### Backend
- No changes needed (already implemented)

## Next Steps (Optional Enhancements)

1. **Task/Note Creation from Messages:**
   - Add "Create Task" button to assistant messages
   - Add "Create Note" button to assistant messages
   - Use endpoints: `/api/chat/messages/{id}/create-task` and `/api/chat/messages/{id}/create-note`

2. **Real-time Updates:**
   - Consider WebSocket for real-time message updates
   - Currently uses polling/refresh

3. **Message Actions:**
   - Copy message
   - Regenerate response
   - Edit message

4. **Conversation Management:**
   - Show conversation list
   - Switch between conversations
   - Delete conversations

## Summary

✅ **Chat feature is fully connected!**

- Frontend properly checks diagnostic completion
- Conversation is automatically created when diagnostic completes
- Messages are sent to correct API endpoints
- GPT context includes diagnostic data
- Error handling is in place
- All routers, services, and models are connected

Users can now chat with Trinity AI about their diagnostic results once they complete a diagnostic!

