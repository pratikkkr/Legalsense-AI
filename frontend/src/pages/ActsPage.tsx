import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { actsApi } from '../api/client';
import type { ActSummary, SectionSummary, SectionDetail } from '../types';
import './ActsPage.css';

export default function ActsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [acts, setActs] = useState<ActSummary[]>([]);
  const [selectedActSlug, setSelectedActSlug] = useState<string | null>(searchParams.get('act') || null);
  const [sections, setSections] = useState<SectionSummary[]>([]);
  const [selectedSectionNumber, setSelectedSectionNumber] = useState<string | null>(searchParams.get('sec') || null);
  const [sectionDetail, setSectionDetail] = useState<SectionDetail | null>(null);
  const [loadingActs, setLoadingActs] = useState(true);
  const [loadingSections, setLoadingSections] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Load all acts on mount
  useEffect(() => {
    actsApi.list()
      .then(data => {
        setActs(data);
        if (data.length > 0 && !selectedActSlug) {
          // Default to the first act in list if none set in url
          setSelectedActSlug(data[0].slug);
        }
      })
      .catch(err => console.error(err))
      .finally(() => setLoadingActs(false));
  }, []);

  // Update URL and reload sections when act slug changes
  useEffect(() => {
    const act = searchParams.get('act');
    if (act) {
      setSelectedActSlug(act);
      loadSections(act);
    } else if (selectedActSlug) {
      setSearchParams({ act: selectedActSlug });
    }
  }, [selectedActSlug, searchParams]);

  // Load detail when active section changes
  useEffect(() => {
    const sec = searchParams.get('sec');
    if (selectedActSlug && sec) {
      setSelectedSectionNumber(sec);
      loadSectionDetail(selectedActSlug, sec);
    } else {
      setSelectedSectionNumber(null);
      setSectionDetail(null);
    }
  }, [selectedSectionNumber, selectedActSlug, searchParams]);

  const loadSections = async (slug: string) => {
    setLoadingSections(true);
    try {
      const data = await actsApi.get(slug);
      setSections(data.sections);
      
      // Auto-select first section if no section parameter exists in URL
      const currentSec = searchParams.get('sec');
      if (data.sections.length > 0 && !currentSec) {
        setSearchParams({ act: slug, sec: data.sections[0].section_number });
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSections(false);
    }
  };

  const loadSectionDetail = async (actSlug: string, secNum: string) => {
    setLoadingDetail(true);
    try {
      const detail = await actsApi.getSection(actSlug, secNum);
      setSectionDetail(detail);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleActSelect = (slug: string) => {
    setSelectedActSlug(slug);
    setSearchParams({ act: slug });
  };

  const handleSectionSelect = (secNum: string) => {
    if (selectedActSlug) {
      setSelectedSectionNumber(secNum);
      setSearchParams({ act: selectedActSlug, sec: secNum });
    }
  };

  return (
    <div className="acts-page fade-in">
      {/* 1st column: Acts List */}
      <aside className="acts-column acts-sidebar">
        <h3 className="column-title">Central Acts</h3>
        {loadingActs ? (
          <div className="spinner-container"><div className="spinner" /></div>
        ) : (
          <div className="list-container">
            {acts.map(act => (
              <button
                key={act.id}
                className={`list-item act-button ${selectedActSlug === act.slug ? 'item-active' : ''}`}
                onClick={() => handleActSelect(act.slug)}
              >
                <span className="act-title">{act.title}</span>
                <span className="act-info">{act.total_sections} sections • {act.year || 'N/A'}</span>
              </button>
            ))}
          </div>
        )}
      </aside>

      {/* 2nd column: Sections List */}
      <aside className="acts-column sections-sidebar">
        <h3 className="column-title">Provisions</h3>
        {loadingSections ? (
          <div className="spinner-container"><div className="spinner" /></div>
        ) : (
          <div className="list-container">
            {sections.map(sec => (
              <button
                key={sec.id}
                className={`list-item section-button ${selectedSectionNumber === sec.section_number ? 'item-active' : ''}`}
                onClick={() => handleSectionSelect(sec.section_number)}
              >
                <span className="section-number">Section {sec.section_number}</span>
                <span className="section-title">{sec.title}</span>
              </button>
            ))}
          </div>
        )}
      </aside>

      {/* 3rd column: Section Reader Panel */}
      <section className="acts-reader">
        {loadingDetail ? (
          <div className="reader-loader"><div className="spinner" /><p>Fetching statutory text...</p></div>
        ) : sectionDetail ? (
          <article className="section-article container">
            <header className="section-header">
              <span className="source-act">{sectionDetail.act.title}</span>
              <h1>Section {sectionDetail.section_number}: {sectionDetail.title}</h1>
              {sectionDetail.chapter && <span className="chapter-tag">{sectionDetail.chapter}</span>}
            </header>
            
            {sectionDetail.has_state_amendment && (
              <div className="alert alert-success amendment-alert">
                ℹ️ This section contains local or State Amendments below.
              </div>
            )}

            <hr className="divider" />

            <div className="section-body">
              {sectionDetail.text}
            </div>
          </article>
        ) : (
          <div className="reader-placeholder">
            <span className="book-logo">📖</span>
            <h3>Select a provision to begin reading</h3>
            <p>Navigate through central acts and specific sections using the sidebar panel.</p>
          </div>
        )}
      </section>
    </div>
  );
}
