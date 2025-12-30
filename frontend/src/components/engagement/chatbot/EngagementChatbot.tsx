import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ChatMessage } from './ChatMessage';
import { Send, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface Conversation {
  id: string;
  category: string;
  title?: string;
  created_at: string;
  updated_at: string;
}

type ChatCategory = 
  | 'general' 
  | 'financial' 
  | 'legal-licensing' 
  | 'operations' 
  | 'human-resources' 
  | 'customers' 
  | 'tax' 
  | 'due-diligence'
  | 'brand-ip-intangibles';

interface EngagementChatbotProps {
  engagementId: string;
}

const CATEGORY_OPTIONS: { value: ChatCategory; label: string; description: string }[] = [
  { value: 'general', label: 'General', description: 'General business advisory' },
  { value: 'financial', label: 'Financial', description: 'Financial clarity & reporting' },
  { value: 'legal-licensing', label: 'Legal & Licensing', description: 'Legal, compliance & property' },
  { value: 'operations', label: 'Operations', description: 'Owner dependency & operations' },
  { value: 'human-resources', label: 'People & HR', description: 'HR, culture and workforce planning' },
  { value: 'customers', label: 'Customers & Products', description: 'Product fit, margins, customers and pricing' },
  { value: 'tax', label: 'Tax & Regulatory', description: 'Tax, compliance & regulatory matters' },
  { value: 'due-diligence', label: 'Due Diligence', description: 'Data-room and vendor readiness' },
  { value: 'brand-ip-intangibles', label: 'Brand, IP & Intangibles', description: 'Branding assets, trademarks and intangible value' },
];

export function EngagementChatbot({ engagementId }: EngagementChatbotProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<ChatCategory>('general');
  const [error, setError] = useState<string | null>(null);
  const [showCategorySelector, setShowCategorySelector] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize conversation when category is selected
  const initializeConversation = async (category: ChatCategory) => {
    setIsInitializing(true);
    setError(null);
    setShowCategorySelector(false);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      // Step 1: Get or create conversation
      const conversationResponse = await fetch(
        `${API_BASE_URL}/api/chat/conversations`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            category: category,
          }),
        }
      );

      if (!conversationResponse.ok) {
        const errorData = await conversationResponse.json().catch(() => ({ detail: 'Failed to get or create conversation' }));
        throw new Error(errorData.detail || 'Failed to get or create conversation');
      }

      const conversationData = await conversationResponse.json();
      console.log('Conversation created/retrieved:', conversationData);
      
      // Ensure conversation ID is a string
      if (!conversationData.id) {
        throw new Error('Conversation ID is missing from response');
      }
      
      // Convert ID to string if needed
      const conversationId = String(conversationData.id);
      const updatedConversation = {
        ...conversationData,
        id: conversationId,
      };
      
      setConversation(updatedConversation);

      // Step 2: Load existing messages
      const messagesResponse = await fetch(
        `${API_BASE_URL}/api/chat/conversations/${conversationId}/messages`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (messagesResponse.ok) {
        const messagesData = await messagesResponse.json();
        const formattedMessages: Message[] = messagesData.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.message,
          timestamp: new Date(msg.created_at),
        }));

        // If no messages exist, add welcome message
        if (formattedMessages.length === 0) {
          const welcomeMessages: Partial<Record<ChatCategory, string>> = {
            general: 'Hello! I\'m Trinity AI, your business advisor assistant. I can help you with general business questions, provide advice, and assist with various business matters. How can I help you today?',
            financial: 'Hello! I\'m Trinity AI, your financial advisor assistant. I can help you with financial matters, analysis, budgeting, and financial planning. How can I help you today?',
            'legal-licensing': 'Hello! I\'m Trinity AI, your legal and compliance advisor assistant. I can help you with legal matters, compliance questions, and regulatory guidance. How can I help you today?',
            operations: 'Hello! I\'m Trinity AI, your operations advisor assistant. I can help you with business operations, process improvements, and operational efficiency. How can I help you today?',
            'human-resources': 'Hello! I\'m Trinity AI, your people and HR advisor assistant. I can help you with HR policies, workforce planning, culture, and people management. How can I help you today?',
            customers: 'Hello! I\'m Trinity AI, your customer and product advisor assistant. I can help you with product fit, margins, customer relationships, and pricing strategies. How can I help you today?',
            tax: 'Hello! I\'m Trinity AI, your tax and regulatory advisor assistant. I can help you with tax matters, compliance, and regulatory requirements. How can I help you today?',
            'due-diligence': 'Hello! I\'m Trinity AI, your due diligence advisor assistant. I can help you prepare for due diligence, organize your data room, and ensure vendor readiness. How can I help you today?',
            'brand-ip-intangibles': 'Hello! I\'m Trinity AI, your brand and IP advisor assistant. I can help you with branding assets, trademarks, patents, proprietary software, and intangible value. How can I help you today?',
          };
          
          const welcomeMessage = welcomeMessages[category] || welcomeMessages.general || 'Hello! I\'m Trinity AI, your business advisor assistant. How can I help you today?';

          formattedMessages.push({
            id: 'welcome',
            role: 'assistant',
            content: welcomeMessage,
            timestamp: new Date(),
          });
        }

        setMessages(formattedMessages);
      }
    } catch (err) {
      console.error('Error initializing chat:', err);
      setError(err instanceof Error ? err.message : 'Failed to initialize chat');
      toast.error('Failed to initialize chat. Please try again.');
      setShowCategorySelector(true);
    } finally {
      setIsInitializing(false);
    }
  };

  // Handle category change
  const handleCategoryChange = (category: ChatCategory) => {
    setSelectedCategory(category);
    setConversation(null);
    setMessages([]);
    initializeConversation(category);
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading || !conversation) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    // Optimistically add user message
    setMessages(prev => [...prev, userMessage]);
    const messageText = input.trim();
    setInput('');
    setIsLoading(true);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      if (!conversation.id) {
        throw new Error('Conversation ID is missing');
      }

      // Send message to backend
      // Ensure conversation ID is a string
      const conversationId = String(conversation.id);
      const url = `${API_BASE_URL}/api/chat/conversations/${conversationId}/messages?engagement_id=${engagementId}`;
      
      console.log('Sending message to:', url);
      console.log('Conversation ID:', conversationId);
      console.log('Engagement ID:', engagementId);
      console.log('Conversation object:', conversation);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: messageText,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { detail: errorText || `HTTP ${response.status}: Failed to send message` };
        }
        
        console.error('Error response:', errorData);
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to send message`);
      }

      const data = await response.json();
      console.log('Message response:', data);

      // Add assistant response
      const aiMessage: Message = {
        id: data.id,
        role: 'assistant',
        content: data.message || 'I apologize, but I encountered an error. Please try again.',
        timestamp: new Date(data.created_at),
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message. Please try again.';
      toast.error(errorMessage);
      
      // Remove the optimistic user message and add error message
      setMessages(prev => {
        const filtered = prev.filter(msg => msg.id !== userMessage.id);
        return [
          ...filtered,
          {
            id: Date.now().toString(),
            role: 'assistant',
            content: 'I\'m sorry, I\'m having trouble connecting right now. Please try again in a moment.',
            timestamp: new Date(),
          },
        ];
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Show category selector if not initialized
  if (showCategorySelector && !conversation) {
    return (
      <div className="flex flex-col h-[calc(100vh-300px)] max-h-[700px]">
        <div className="border-b pb-4 mb-6">
          <h3 className="text-lg font-semibold">Trinity AI Assistant</h3>
          <p className="text-sm text-muted-foreground">
            Select a conversation category to start chatting
          </p>
        </div>

        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-md space-y-4">
            <div className="space-y-2">
              <Label htmlFor="category">Select Conversation Category</Label>
              <Select value={selectedCategory} onValueChange={(value) => handleCategoryChange(value as ChatCategory)}>
                <SelectTrigger id="category">
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      <div className="flex flex-col">
                        <span className="font-medium">{option.label}</span>
                        <span className="text-xs text-muted-foreground">{option.description}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={() => initializeConversation(selectedCategory)}
              className="w-full"
            >
              Start Conversation
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Show loading state while initializing
  if (isInitializing) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-300px)] max-h-[700px]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mb-4" />
        <p className="text-sm text-muted-foreground">Loading chat...</p>
      </div>
    );
  }

  // Show error state
  if (error && !conversation) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-300px)] max-h-[700px]">
        <Alert variant="destructive" className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <p className="font-semibold mb-2">Failed to initialize chat</p>
            <p className="text-sm mb-4">{error}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setError(null);
                setShowCategorySelector(true);
              }}
            >
              Try Again
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-300px)] max-h-[700px]">
      {/* Chat Header */}
      <div className="border-b pb-4 mb-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Trinity AI Assistant</h3>
            <p className="text-sm text-muted-foreground">
              {CATEGORY_OPTIONS.find(c => c.value === conversation?.category)?.description || 'Chat with Trinity AI'}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setConversation(null);
              setMessages([]);
              setShowCategorySelector(true);
            }}
          >
            Change Category
          </Button>
        </div>
        {conversation && (
          <div className="mt-2">
            <span className="text-xs px-2 py-1 bg-muted rounded-md">
              {CATEGORY_OPTIONS.find(c => c.value === conversation.category)?.label || conversation.category}
            </span>
          </div>
        )}
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto mb-4 space-y-4 pr-4">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        
        {isLoading && (
          <div className="flex gap-3 mb-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
            <div className="bg-muted rounded-lg px-4 py-3">
              <p className="text-sm text-muted-foreground">Trinity AI is thinking...</p>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t pt-4">
        <div className="flex gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask Trinity AI anything about your diagnostic results..."
            className="min-h-[60px] max-h-[120px] resize-none"
            disabled={isLoading || !conversation}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!input.trim() || isLoading || !conversation}
            size="icon"
            className="h-[60px] w-[60px]"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

