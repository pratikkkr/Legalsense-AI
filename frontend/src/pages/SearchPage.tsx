import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { searchApi, actsApi } from '../api/client';
import type { ActSummary, SearchResultItem } from '../types';
import './SearchPage.css';

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [actFilter, setActFilter] = useState(searchParams.get('act') || '');
  const [acts, setActs] = useState<ActSummary[]>([]);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedResult, setSelectedResult] = useState<SearchResultItem | null>(null);
  const [totalHits, setTotalHits] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);

  // Load acts list on mount
  useEffect(() => {
    actsApi.list()
      .then(setActs)
      .catch(err => console.error('Failed to load acts', err));
  }, []);

  // Perform search when query params change
  useEffect(() => {
    const q = searchParams.get('q');
    const act = searchParams.get('act');
    if (q) {
      setQuery(q);
      setActFilter(act || '');
      performSearch(q, act || undefined);
    }
  }, [searchParams]);

  const performSearch = async (q: string, act?: string) => {
    setLoading(true);
    setError('');
    setSelectedResult(null);
    try {
      const res = await searchApi.search(q, act);
      setResults(res.results);
      setTotalHits(res.total);
      setElapsedMs(res.elapsed_ms);
    } catch (err) {
      console.error(err);
      setError('Failed to perform vector search. Ensure backend and vector store are running.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const params: Record<string, string> = { q: query };
    if (actFilter) params.act = actFilter;
    setSearchParams(params);
  };

  return (
    <div className="search-page container fade-in">
      <header className="search-header">
        <h1>Legal Document Search</h1>
        <p>Semantic search powered by embeddings across Indian Central Acts.</p>
      </header>

      {/* Search Input Bar */}
      <form onSubmit={handleSubmit} className="search-form card glass">
        <div className="search-inputs">
          <div className="input-group flex-grow">
            <input
              type="text"
              className="input search-input"
              placeholder="Search legal concepts, e.g., 'breach of contract damages' or 'cyber security regulations'"
              value={query}
              onChange={e => setQuery(e.target.value)}
              required
            />
          </div>
          <div className="input-group act-select-group">
            <select
              className="input act-select"
              value={actFilter}
              onChange={e => setActFilter(e.target.value)}
            >
              <option value="">All Acts</option>
              {acts.map(act => (
                <option key={act.id} value={act.slug}>
                  {act.title}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary search-btn" disabled={loading}>
            {loading ? <span className="spinner" /> : 'Search'}
          </button>
        </div>
      </form>

      {error && <div className="alert alert-error search-error">{error}</div>}

      {/* Main Results Container */}
      <div className="search-layout">
        <div className="results-column">
          {query && !loading && (
            <div className="results-summary">
              Found {totalHits} sections in {elapsedMs.toFixed(1)} ms
            </div>
          )}

          {results.length === 0 && query && !loading && !error && (
            <div className="empty-state card">
              <span className="empty-icon">🔍</span>
              <h3>No matching sections found</h3>
              <p>Try rephrasing your search query or removing the Act filter.</p>
            </div>
          )}

          <div className="results-list">
            {results.map(item => (
              <div
                key={`${item.act_slug}-${item.section_number}`}
                className={`result-item card ${selectedResult?.section_number === item.section_number && selectedResult?.act_slug === item.act_slug ? 'result-item-selected' : ''}`}
                onClick={() => setSelectedResult(item)}
              >
                <div className="result-meta">
                  <span className="badge badge-accent">Score: {item.score.toFixed(3)}</span>
                  <span className="result-act-title">{item.act_title}</span>
                </div>
                <h3 className="result-title">
                  Section {item.section_number}: {item.section_title}
                </h3>
                {item.chapter && <span className="result-chapter">{item.chapter}</span>}
                <p className="result-snippet">{item.text_snippet}...</p>
              </div>
            ))}
          </div>
        </div>

        {/* Preview / Detail Side Panel */}
        <div className="detail-column">
          {selectedResult ? (
            <div className="detail-panel card glass fade-in">
              <div className="detail-header">
                <span className="detail-act">{selectedResult.act_title}</span>
                <h2>Section {selectedResult.section_number}: {selectedResult.section_title}</h2>
                {selectedResult.chapter && <span className="detail-chapter">{selectedResult.chapter}</span>}
              </div>
              <hr className="detail-divider" />
              <div className="detail-body">
                <p>{selectedResult.text_snippet}</p>
              </div>
            </div>
          ) : (
            <div className="detail-placeholder card">
              <span className="placeholder-icon">📄</span>
              <p>Select a search result to view its full text preview.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
