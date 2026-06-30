import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { actsApi, searchApi, chatApi } from '../api/client';
import type { ActSummary, SearchHistoryItem, ConversationSummary } from '../types';
import './DashboardPage.css';

export default function DashboardPage() {
  const [acts, setActs] = useState<ActSummary[]>([]);
  const [recentSearches, setRecentSearches] = useState<SearchHistoryItem[]>([]);
  const [recentChats, setRecentChats] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadData() {
      try {
        const [actsData, searchData, chatData] = await Promise.all([
          actsApi.list(),
          searchApi.history(),
          chatApi.conversations(),
        ]);
        setActs(actsData);
        setRecentSearches(searchData.slice(0, 5));
        setRecentChats(chatData.slice(0, 5));
      } catch (err) {
        console.error(err);
        setError('Failed to load dashboard data. Is the backend running?');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="dashboard-page loading-state">
        <div className="spinner" />
        <p>Loading your dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-page error-state container">
        <div className="alert alert-error">
          <span>⚠️ {error}</span>
        </div>
      </div>
    );
  }

  const totalSections = acts.reduce((sum, act) => sum + act.total_sections, 0);

  return (
    <div className="dashboard-page container fade-in">
      <header className="dashboard-header">
        <h1>Welcome to LegalSense AI</h1>
        <p>AI-powered search, QA, and analysis for Indian Central Acts.</p>
      </header>

      {/* Metric Cards */}
      <section className="metrics-grid">
        <div className="card metric-card">
          <span className="metric-icon">📜</span>
          <div className="metric-info">
            <h3>{acts.length}</h3>
            <p>Ingested Acts</p>
          </div>
        </div>
        <div className="card metric-card">
          <span className="metric-icon">🧩</span>
          <div className="metric-info">
            <h3>{totalSections}</h3>
            <p>Total Sections</p>
          </div>
        </div>
        <div className="card metric-card">
          <span className="metric-icon">🔍</span>
          <div className="metric-info">
            <h3>{recentSearches.length}</h3>
            <p>Recent Searches</p>
          </div>
        </div>
        <div className="card metric-card">
          <span className="metric-icon">💬</span>
          <div className="metric-info">
            <h3>{recentChats.length}</h3>
            <p>Recent Chats</p>
          </div>
        </div>
      </section>

      {/* Main Grid */}
      <div className="dashboard-grid">
        {/* Ingested Acts List */}
        <section className="dashboard-section acts-section card">
          <div className="section-header">
            <h2>Ingested Acts</h2>
            <Link to="/acts" className="btn btn-ghost btn-sm">View All →</Link>
          </div>
          <div className="acts-list">
            {acts.slice(0, 6).map(act => (
              <div key={act.id} className="act-item">
                <div className="act-meta">
                  <h4>{act.title}</h4>
                  <span>Year: {act.year || 'N/A'} • {act.total_sections} sections</span>
                </div>
                <Link to={`/acts?act=${act.slug}`} className="btn btn-secondary btn-sm">Browse</Link>
              </div>
            ))}
          </div>
        </section>

        {/* Quick Actions & Recent Activity */}
        <div className="side-column">
          <section className="dashboard-section quick-actions card">
            <h2>Quick Actions</h2>
            <div className="actions-grid">
              <Link to="/search" className="btn btn-primary">
                🔍 New Legal Search
              </Link>
              <Link to="/chat" className="btn btn-secondary">
                💬 Start AI Consultation
              </Link>
            </div>
          </section>

          <section className="dashboard-section activity-section card">
            <h2>Recent Activity</h2>
            <div className="activity-tabs">
              <div className="activity-group">
                <h3>Recent Searches</h3>
                {recentSearches.length === 0 ? (
                  <p className="empty-text">No recent searches.</p>
                ) : (
                  <ul className="activity-list">
                    {recentSearches.map(s => (
                      <li key={s.id} className="activity-item">
                        <span className="activity-query">“{s.query}”</span>
                        <span className="activity-date">
                          {s.results_count} results • {new Date(s.created_at).toLocaleDateString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="activity-group">
                <h3>Recent Conversations</h3>
                {recentChats.length === 0 ? (
                  <p className="empty-text">No recent conversations.</p>
                ) : (
                  <ul className="activity-list">
                    {recentChats.map(c => (
                      <li key={c.id} className="activity-item">
                        <Link to={`/chat?id=${c.id}`} className="activity-link">
                          💬 {c.title}
                        </Link>
                        <span className="activity-date">
                          {new Date(c.updated_at).toLocaleDateString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
