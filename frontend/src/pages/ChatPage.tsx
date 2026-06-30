import { useEffect, useState, useRef } from 'react';
import type { FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { chatApi, actsApi } from '../api/client';
import type { ConversationSummary, Message, Citation, SectionDetail } from '../types';
import './ChatPage.css';

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentId, setCurrentId] = useState<string | null>(searchParams.get('id') || null);
  const [citationModal, setCitationModal] = useState<Citation | null>(null);
  const [citationDetail, setCitationDetail] = useState<SectionDetail | null>(null);
  const [citationLoading, setCitationLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load conversations list
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversation details when active ID changes
  useEffect(() => {
    const id = searchParams.get('id');
    setCurrentId(id);
    if (id) {
      loadMessages(id);
    } else {
      setMessages([]);
    }
  }, [searchParams]);

  // Scroll to bottom on message list change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Load section detail when citation modal is opened
  useEffect(() => {
    if (citationModal) {
      loadCitationDetail(citationModal);
    } else {
      setCitationDetail(null);
    }
  }, [citationModal]);

  const loadConversations = async () => {
    try {
      const data = await chatApi.conversations();
      setConversations(data);
    } catch (err) {
      console.error(err);
    }
  };

  const loadMessages = async (id: string) => {
    try {
      const data = await chatApi.conversation(id);
      setMessages(data.messages);
    } catch (err) {
      console.error(err);
    }
  };

  const loadCitationDetail = async (citation: Citation) => {
    setCitationLoading(true);
    try {
      // Find matching Act slug by title similarity (simple slugify fallback)
      const slug = citation.act_title.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/(^_+|_+$)/g, '');
      const detail = await actsApi.getSection(slug, citation.section_number);
      setCitationDetail(detail);
    } catch (err) {
      console.error(err);
    } finally {
      setCitationLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input;
    setInput('');
    setLoading(true);

    // Optimistic user message update
    const userMsg: Message = {
      id: Math.random().toString(),
      role: 'user',
      content: userText,
      citations: null,
      model_used: null,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);

    try {
      const res = await chatApi.send(userText, currentId || undefined);
      
      // Update active ID and route if new conversation
      if (!currentId) {
        setSearchParams({ id: res.conversation_id });
      }

      setMessages(prev => [...prev, res.message]);
      await loadConversations();
    } catch (err) {
      console.error(err);
      // Append error message to chat window
      const errMsg: Message = {
        id: Math.random().toString(),
        role: 'system',
        content: '⚠️ Failed to connect to LegalSense AI. Please check that the server is active.',
        citations: null,
        model_used: null,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const startNewConversation = () => {
    setSearchParams({});
  };

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this conversation?')) return;
    try {
      await chatApi.deleteConversation(id);
      if (currentId === id) {
        setSearchParams({});
      }
      await loadConversations();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="chat-page fade-in">
      {/* Left Sidebar: Conversations */}
      <aside className="chat-sidebar">
        <div className="chat-sidebar-header">
          <button className="btn btn-primary new-chat-btn" onClick={startNewConversation}>
            ➕ New Consultation
          </button>
        </div>
        <div className="conversations-list">
          {conversations.map(conv => (
            <div
              key={conv.id}
              className={`conv-item ${currentId === conv.id ? 'conv-item-active' : ''}`}
              onClick={() => setSearchParams({ id: conv.id })}
            >
              <div className="conv-title-row">
                <span className="conv-title">💬 {conv.title}</span>
                <button
                  className="btn-delete"
                  onClick={e => handleDeleteConversation(conv.id, e)}
                  title="Delete conversation"
                >
                  ✕
                </button>
              </div>
              <span className="conv-meta">
                {conv.message_count} messages • {new Date(conv.updated_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Chat Panel */}
      <section className="chat-main">
        {messages.length === 0 && !loading ? (
          <div className="chat-welcome container">
            <span className="welcome-logo">⚖️</span>
            <h2>LegalSense AI Assistant</h2>
            <p>
              Ask any questions about Indian Central Acts. The AI will cross-reference
              statutes, cite sections, and explain details.
            </p>
            <div className="quick-questions">
              <button className="btn btn-secondary btn-sm" onClick={() => setInput('What are the rules of acceptance under the Indian Contract Act?')}>
                "Contract acceptance rules?"
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => setInput('What does section 66A of the IT Act say and is it valid?')}>
                "Section 66A validity?"
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => setInput('What constitutes sexual harassment at the workplace?')}>
                "Workplace harassment criteria?"
              </button>
            </div>
          </div>
        ) : (
          <div className="messages-container">
            {messages.map(msg => (
              <div key={msg.id} className={`message-row ${msg.role === 'user' ? 'msg-user' : 'msg-ai'}`}>
                <div className="message-bubble card">
                  <div className="message-content">{msg.content}</div>

                  {/* Render citations if any */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="citations-block">
                      <h4>Statutory References:</h4>
                      <div className="citations-list">
                        {msg.citations.map((cite, idx) => (
                          <button
                            key={idx}
                            className="btn btn-secondary btn-sm citation-btn"
                            onClick={() => setCitationModal(cite)}
                          >
                            📖 Section {cite.section_number}, {cite.act_title}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {msg.model_used && (
                    <span className="message-model">Answered by {msg.model_used}</span>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="message-row msg-ai">
                <div className="message-bubble card loading-bubble">
                  <div className="loading-dots">
                    <span>.</span><span>.</span><span>.</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input Form Box */}
        <div className="chat-input-bar">
          <form onSubmit={handleSubmit} className="chat-form container">
            <input
              type="text"
              className="input chat-input"
              placeholder="Ask a legal question... e.g., 'What are the penalties for computer source code hacking?'"
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={loading}
              required
            />
            <button type="submit" className="btn btn-primary send-btn" disabled={loading}>
              Send
            </button>
          </form>
        </div>
      </section>

      {/* Citation Modal / Side Drawer */}
      {citationModal && (
        <div className="modal-overlay" onClick={() => setCitationModal(null)}>
          <div className="modal-content card glass fade-in" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Statutory Text</h3>
              <button className="btn btn-ghost modal-close" onClick={() => setCitationModal(null)}>
                ✕
              </button>
            </div>
            <hr />
            <div className="modal-body">
              {citationLoading ? (
                <div className="modal-spinner">
                  <div className="spinner" />
                  <p>Fetching full section text...</p>
                </div>
              ) : citationDetail ? (
                <div>
                  <h4 className="modal-section-title">
                    {citationDetail.act.title}
                  </h4>
                  <h5 className="modal-section-header">
                    Section {citationDetail.section_number}: {citationDetail.title}
                  </h5>
                  {citationDetail.chapter && (
                    <span className="modal-chapter">{citationDetail.chapter}</span>
                  )}
                  <p className="modal-text">{citationDetail.text}</p>
                </div>
              ) : (
                <p className="modal-error">
                  Could not load full text for Section {citationModal.section_number} of {citationModal.act_title}.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
