import re
from backend.core.config import get_settings
from scripts.ingest.parse_act import clean_text, split_into_sections, OMITTED_SECTION_RE

def test_clean_text():
    # Glued footnote section header fix
    dirty_text = "\n1151. Section title — body text"
    cleaned = clean_text(dirty_text)
    assert "151. Section title" in cleaned

def test_omitted_section_regex():
    # Standard bracketed omitted section title
    txt1 = "\n49. [Composition of Cyber Appellate Tribunal.]—Omitted by the Finance Act, 2017\n\n50. Next section"
    assert OMITTED_SECTION_RE.search(txt1) is not None
    
    # Footnote-glued bracketed omitted section title (the s.130A bug we fixed)
    txt2 = "\n7[130A. Transfer of policy of marine insurance.] Rep. by the Marine Insurance Act, 1963\n\n131. Next section"
    assert OMITTED_SECTION_RE.search(txt2) is not None

def test_split_into_sections():
    op_text = (
        "PRELIMINARY\n"
        "1. Short title.—(1) This Act may be called the Test Act.\n"
        "2. Definitions.—(1) In this Act, unless the context otherwise requires—\n"
        "“goods” means physical things.\n"
    )
    sections = split_into_sections(op_text, "Test Act")
    assert len(sections) == 2
    assert sections[0]["section"] == "1"
    assert sections[0]["title"] == "Short title"
    assert "Test Act" in sections[0]["text"]
    assert sections[1]["section"] == "2"
    assert sections[1]["title"] == "Definitions"
