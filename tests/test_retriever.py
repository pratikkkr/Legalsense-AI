from unittest.mock import MagicMock, patch

from backend.chains.embedding import chunk_section
from backend.chains.retriever import HybridRetriever


def test_chunk_section():
    # Long section text split test
    section = {
        "source": "The Contract Act, 1872",
        "section": "10",
        "title": "Consent",
        "chapter": "CHAPTER I",
        "text": "word " * 1500, # 1500 words, exceeds chunk limit of 1000
        "has_state_amendment": False
    }
    
    chunks = chunk_section(section, chunk_size=1000, chunk_overlap=200)
    assert len(chunks) == 2
    assert chunks[0]["chunk_index"] == 0
    assert chunks[1]["chunk_index"] == 1
    assert chunks[0]["act_slug"] == "the_contract_act_1872"
    assert chunks[1]["section_number"] == "10"

@patch("backend.chains.retriever.get_qdrant_client")
@patch("backend.chains.retriever.embed_query")
def test_retriever_query(mock_embed, mock_get_client):
    mock_embed.return_value = [0.1] * 384
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    # Setup mock query response payload
    mock_point = MagicMock()
    mock_point.score = 0.92
    mock_point.payload = {
        "text": "Chunk text body",
        "act_title": "The Title Act",
        "act_slug": "the_title_act",
        "section_number": "5",
        "section_title": "Title 5",
        "chapter": "CHAPTER I",
        "chunk_index": 0,
        "has_state_amendment": False
    }
    mock_client.query_points.return_value = MagicMock(points=[mock_point])
    
    retriever = HybridRetriever(top_k=5, score_threshold=0.5)
    res = retriever.retrieve("test query")
    
    assert len(res.chunks) == 1
    assert res.chunks[0].score == 0.92
    assert res.chunks[0].section_number == "5"
    assert res.chunks[0].act_title == "The Title Act"
