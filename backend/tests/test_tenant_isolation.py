import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User, Membership, Task
from app.services.auth import AuthService


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, db_session: AsyncSession):
    """Test that tenant isolation prevents cross-org access."""
    
    # Create two organizations
    org1 = Organization(name="Org 1", subdomain="org1")
    org2 = Organization(name="Org 2", subdomain="org2")
    db_session.add(org1)
    db_session.add(org2)
    await db_session.flush()
    
    # Create users for each org
    user1 = User(email="user1@example.com", password_hash=AuthService.hash_password("pass"))
    user2 = User(email="user2@example.com", password_hash=AuthService.hash_password("pass"))
    db_session.add(user1)
    db_session.add(user2)
    await db_session.flush()
    
    # Create memberships
    membership1 = Membership(user_id=user1.id, org_id=org1.id, role="admin")
    membership2 = Membership(user_id=user2.id, org_id=org2.id, role="admin")
    db_session.add(membership1)
    db_session.add(membership2)
    await db_session.flush()
    
    # Create tasks for each org
    task1 = Task(org_id=org1.id, title="Task 1", status="todo")
    task2 = Task(org_id=org2.id, title="Task 2", status="todo")
    db_session.add(task1)
    db_session.add(task2)
    await db_session.commit()
    
    # Create tokens for each user
    token1 = AuthService.create_access_token({
        "user_id": user1.id,
        "org_id": org1.id,
        "role": "admin"
    })
    token2 = AuthService.create_access_token({
        "user_id": user2.id,
        "org_id": org2.id,
        "role": "admin"
    })
    
    # User 1 should only see tasks from org 1
    response = await client.get(
        f"/organizations/{org1.id}/tasks",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["title"] == "Task 1"
    
    # User 1 should not be able to access org 2 tasks
    response = await client.get(
        f"/organizations/{org2.id}/tasks",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert response.status_code == 403
    
    # User 2 should only see tasks from org 2
    response = await client.get(
        f"/organizations/{org2.id}/tasks",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["title"] == "Task 2"
    
    # User 2 should not be able to access org 1 tasks
    response = await client.get(
        f"/organizations/{org1.id}/tasks",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response.status_code == 403