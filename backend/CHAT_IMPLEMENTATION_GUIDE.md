# Chat Feature Implementation Guide

## Overview

This document explains the complete chatbot feature implementation, adapted from the PHP/Laravel system to Python/FastAPI + React.

## Architecture

### 1. Database Models

#### Conversation Model (`backend/app/models/conversation.py`)
- Represents a chat session with Trinity AI
- Fields:
  - `id`: UUID primary key
  - `user_id`: Foreign key to users
  - `category`: Conversation category (general, diagnostic, finance, etc.)
  - `title`: Optional conversation title
  - `created_at`, `updated_at`: Timestamps
- Relationships:
  - `user`: Many-to-one with User
  - `messages`: One-to-many with Message
  - `diagnostics`: One-to-many with Diagnostic

#### Message Model (`backend/app/models/message.py`)
- Represents a single message in a conversation
- Fields:
  - `id`: UUID primary key
  - `conversation_id`: Foreign key to conversations
  - `role`: "user" or "assistant"
  - `message`: Message content (Text)
  - `response_data`: JSONB for raw GPT response data
  - `metadata`: JSONB for additional metadata
  - `created_at`, `updated_at`: Timestamps
- Relationships:
  - `conversation`: Many-to-one with Conversation

#### Diagnostic Model Updates
- Added `conversation_id` field to link diagnostics to conversations
- When diagnostic completes, it's automatically linked to a conversation

### 2. Service Layer

#### ChatService (`backend/app/services/chat_service.py`)

**Key Methods:**

1. **`get_or_create_conversation(user_id, category, diagnostic_id=None)`**
   - Gets existing conversation or creates new one
   - For diagnostic category, reuses existing diagnostic conversation if available
   - Links diagnostic to conversation if provided

2. **`send_message(conversation_id, user_id, message_text, limit=50)`**
   - Saves user message
   - Builds GPT context (system prompt, category prompt, diagnostic context, conversation history)
   - Calls OpenAI to generate response
   - Saves assistant message
   - Returns assistant message

3. **`_build_gpt_context(conversation, previous_messages, current_message)`**
   - Builds the complete message context for GPT
   - Includes:
     - System prompt (base + user name + category prompt + diagnostic context)
     - Conversation history (last N messages)
     - Current user message

4. **`_build_system_prompt(conversation)`**
   - Builds system prompt with:
     - Base system prompt (from `system_prompt.md`)
     - User name
     - Category-specific prompt (from `category_prompt_{category}.md`)
     - Diagnostic context (if conversation linked to completed diagnostic)

5. **`_get_diagnostic_context(conversation)`**
   - If conversation linked to completed diagnostic:
     - Includes diagnostic summary
     - Includes diagnostic advice (advisorReport)
     - Includes Q&A extract (user_responses)

### 3. API Endpoints (`backend/app/api/chat.py`)

**Routes:**
- `GET /api/chat/conversations` - List all conversations for user
- `POST /api/chat/conversations` - Create new conversation
- `GET /api/chat/conversations/{conversation_id}` - Get conversation details
- `GET /api/chat/conversations/{conversation_id}/messages` - Get messages
- `POST /api/chat/conversations/{conversation_id}/messages` - Send message
- `POST /api/chat/messages/{message_id}/create-task` - Create task from message
- `POST /api/chat/messages/{message_id}/create-note` - Create note from message

### 4. Diagnostic Integration

**When Diagnostic Completes:**
1. Diagnostic status → "completed"
2. Diagnostic automatically linked to conversation (category: "diagnostic")
3. If diagnostic conversation exists, reuse it; otherwise create new one
4. Future chat messages in that conversation will include diagnostic context

**Diagnostic Context Includes:**
- Diagnostic summary (from `ai_analysis.summary`)
- Diagnostic advice (from `ai_analysis.advisorReport`)
- Q&A extract (from `user_responses`)

## Workflow

### Step 1: Diagnostic Completion
```
User completes diagnostic → 
Diagnostic status = "completed" → 
ChatService.get_or_create_conversation(category="diagnostic", diagnostic_id=...) →
Conversation created/linked → 
Diagnostic.conversation_id set
```

### Step 2: User Opens Chat
```
User navigates to /chat →
GET /api/chat/conversations →
Returns list of conversations →
User selects conversation or creates new one
```

### Step 3: User Sends Message
```
User types message →
POST /api/chat/conversations/{id}/messages →
ChatService.send_message() →
1. Save user message
2. Build GPT context:
   - System prompt (base + category + diagnostic context)
   - Conversation history (last 50 messages)
   - Current message
3. Call OpenAI
4. Save assistant message
5. Return assistant message
```

### Step 4: Create Task/Note from Message
```
User clicks "Create Task" on assistant message →
POST /api/chat/messages/{id}/create-task →
ChatService.create_task_from_message() →
Task created in engagement →
Returns success
```

## Prompt Files Structure

Create these prompt files in `backend/files/prompts/`:

1. **`system_prompt.md`** - Base system prompt for Trinity
2. **`category_prompt_general.md`** - General category prompt
3. **`category_prompt_diagnostic.md`** - Diagnostic category prompt
4. **`category_prompt_finance.md`** - Finance category prompt
5. **`category_prompt_legal.md`** - Legal category prompt
6. **`category_prompt_operations.md`** - Operations category prompt

## Database Migration

You'll need to create a migration to add the new tables:

```python
# alembic migration
def upgrade():
    op.create_table(
        'conversations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), ForeignKey('users.id')),
        sa.Column('category', String(50), nullable=False),
        sa.Column('title', String(255), nullable=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    
    op.create_table(
        'messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', UUID(as_uuid=True), ForeignKey('conversations.id')),
        sa.Column('role', String(20), nullable=False),
        sa.Column('message', Text, nullable=False),
        sa.Column('response_data', JSONB, nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    
    op.add_column('diagnostics', sa.Column('conversation_id', UUID(as_uuid=True), ForeignKey('conversations.id'), nullable=True))
```

## Frontend Implementation (Next Steps)

1. Create chat page component
2. Create conversation list sidebar
3. Create message list component
4. Create message input component
5. Add "Chat with Trinity" button to diagnostic completion screen
6. Add "Create Task" and "Create Note" buttons to assistant messages

## Testing

1. Complete a diagnostic
2. Verify conversation is created and linked
3. Open chat interface
4. Send a message
5. Verify GPT response includes diagnostic context
6. Create task/note from message
7. Verify task/note is created in engagement

## Notes

- Conversation history is limited to last 50 messages by default (configurable)
- Diagnostic context is only included if diagnostic status is "completed"
- Each user can have multiple conversations (one per category)
- Diagnostic conversations are reused if they exist

