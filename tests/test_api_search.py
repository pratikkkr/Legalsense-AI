import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from backend.chains.retriever import RetrievedChunk

@pytest.mark.asyncio
async def test_search_endpoint(client: AsyncClient, auth_headers: dict[str, str]):
    mock_chunks = [
        RetrievedChunk(
            text="Mock provision text content for testing search",
            act_title="The Mock Act, 1996",
            act_slug="the_mock_act_1996",
            section_number="3",
            section_title="Mock Title",
            chapter="CHAPTER I",
            chunk_index=0,
            score=0.85
        )
    ]
    
    # Mock search retriever retrieve method
    with patch("backend.services.search_service.HybridRetriever.retrieve") as mock_retrieve:
        mock_retrieve.return_value = MagicMock(chunks=mock_chunks)
        
        search_req = {
            "query": "mock test query",
            "top_k": 5
        }
        res = await client.post("/api/v1/search", json=search_req, headers=auth_headers)
        assert res.status_code == 200
        
        data = res.json()
        assert data["query"] == search_req["query"]
        assert len(data["results"]) == 1
        assert data["results"][0]["section_number"] == "3"
        assert data["results"][0]["score"] == 0.85
        
        # Test search history retrieval
        hist_res = await client.get("/api/v1/search/history", headers=auth_headers)
        assert hist_res.status_code == 200
        assert len(hist_res.json()) >= 1
        assert hist_res.json()[0]["query"] == search_req["query"]
