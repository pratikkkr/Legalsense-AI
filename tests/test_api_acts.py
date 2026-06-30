import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.models import ActMetadata, Section

@pytest.fixture
def sample_act_data():
    return {
        "slug": "test_act_1882",
        "title": "The Test Act, 1882",
        "year": 1882
    }

@pytest.mark.asyncio
async def test_acts_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict[str, str],
    sample_act_data: dict
):
    # Seed DB with mock Act and Section
    act = ActMetadata(
        slug=sample_act_data["slug"],
        title=sample_act_data["title"],
        year=sample_act_data["year"],
        total_sections=1
    )
    db_session.add(act)
    await db_session.flush()

    sec = Section(
        act_id=act.id,
        section_number="12",
        title="Provision Title",
        chapter="CHAPTER II",
        text="This is the full provision body text of section 12.",
        has_state_amendment=True
    )
    db_session.add(sec)
    await db_session.commit()

    # 1. Get acts list
    list_res = await client.get("/api/v1/acts", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    assert any(a["slug"] == sample_act_data["slug"] for a in list_res.json())

    # 2. Get act by slug
    get_res = await client.get(f"/api/v1/acts/{sample_act_data['slug']}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["title"] == sample_act_data["title"]
    assert len(get_res.json()["sections"]) == 1

    # 3. List sections
    sec_res = await client.get(f"/api/v1/acts/{sample_act_data['slug']}/sections", headers=auth_headers)
    assert sec_res.status_code == 200
    assert len(sec_res.json()) == 1
    assert sec_res.json()[0]["section_number"] == "12"

    # 4. Get section detail
    detail_res = await client.get(
        f"/api/v1/acts/{sample_act_data['slug']}/sections/12",
        headers=auth_headers
    )
    assert detail_res.status_code == 200
    assert detail_res.json()["text"] == sec.text
    assert detail_res.json()["has_state_amendment"] is True
