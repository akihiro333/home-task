import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User, Membership, Task
from app.services.auth import AuthService


@pytest.mark.asyncio
async def test_task_pagination(client: AsyncClient, db_session: AsyncSession):
    """Test task pagination with cursor."""
    
    # Create test data
    org = Organization(name="Test Org", subdomain="test")
    db_session.add(org)
    await db_session.flush()
    
    user = User(email="test@example.com", password_hash=AuthService.hash_password("pass"))
    db_session.add(user)
    await db_session.flush()
    
    membership = Membership(user_id=user.id, org_id=org.id, role="admin")
    db_session.add(membership)
    await db_session.flush()
    
    # Create multiple tasks
    tasks = []
    for i in range(25):
        task = Task(
            org_id=org.id,
            title=f"Task {i+1}",
            status="todo"
        )
        tasks.append(task)
        db_session.add(task)
    
    await db_session.commit()
    
    # Create auth token
    token = AuthService.create_access_token({
        "user_id": user.id,
        "org_id": org.id,
        "role": "admin"
    })
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get first page
    response = await client.get(
        f"/organizations/{org.id}/tasks?limit=10",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 10
    assert data["has_more"] is True
    assert data["next_cursor"] is not None
    
    # Get second page using cursor
    response = await client.get(
        f"/organizations/{org.id}/tasks?limit=10&cursor={data['next_cursor']}",
        headers=headers
    )
    assert response.status_code == 200
    data2 = response.json()
    assert len(data2["tasks"]) == 10
    assert data2["has_more"] is True
    
    # Ensure no duplicate tasks between pages
    page1_ids = {task["id"] for task in data["tasks"]}
    page2_ids = {task["id"] for task in data2["tasks"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_task_filtering(client: AsyncClient, db_session: AsyncSession):
    """Test task filtering by status and assignee."""
    
    # Create test data
    org = Organization(name="Test Org", subdomain="test")
    db_session.add(org)
    await db_session.flush()
    
    user1 = User(email="user1@example.com", password_hash=AuthService.hash_password("pass"))
    user2 = User(email="user2@example.com", password_hash=AuthService.hash_password("pass"))
    db_session.add(user1)
    db_session.add(user2)
    await db_session.flush()
    
    membership1 = Membership(user_id=user1.id, org_id=org.id, role="admin")
    membership2 = Membership(user_id=user2.id, org_id=org.id, role="member")
    db_session.add(membership1)
    db_session.add(membership2)
    await db_session.flush()
    
    # Create tasks with different statuses and assignees
    tasks_data = [
        {"title": "Todo Task 1", "status": "todo", "assignee_id": user1.id},
        {"title": "Todo Task 2", "status": "todo", "assignee_id": user2.id},
        {"title": "Doing Task 1", "status": "doing", "assignee_id": user1.id},
        {"title": "Done Task 1", "status": "done", "assignee_id": user2.id},
    ]
    
    for task_data in tasks_data:
        task = Task(org_id=org.id, **task_data)
        db_session.add(task)
    
    await db_session.commit()
    
    # Create auth token
    token = AuthService.create_access_token({
        "user_id": user1.id,
        "org_id": org.id,
        "role": "admin"
    })
    headers = {"Authorization": f"Bearer {token}"}
    
    # Filter by status
    response = await client.get(
        f"/organizations/{org.id}/tasks?status=todo",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 2
    assert all(task["status"] == "todo" for task in data["tasks"])
    
    # Filter by assignee
    response = await client.get(
        f"/organizations/{org.id}/tasks?assignee={user1.id}",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 2
    assert all(task["assignee_id"] == user1.id for task in data["tasks"])
    
    # Filter by both status and assignee
    response = await client.get(
        f"/organizations/{org.id}/tasks?status=todo&assignee={user1.id}",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["status"] == "todo"
    assert data["tasks"][0]["assignee_id"] == user1.id


@pytest.mark.asyncio
async def test_task_permissions(client: AsyncClient, db_session: AsyncSession):
    """Test task permissions for admin vs member roles."""
    
    # Create test data
    org = Organization(name="Test Org", subdomain="test")
    db_session.add(org)
    await db_session.flush()
    
    admin_user = User(email="admin@example.com", password_hash=AuthService.hash_password("pass"))
    member_user = User(email="member@example.com", password_hash=AuthService.hash_password("pass"))
    db_session.add(admin_user)
    db_session.add(member_user)
    await db_session.flush()
    
    admin_membership = Membership(user_id=admin_user.id, org_id=org.id, role="admin")
    member_membership = Membership(user_id=member_user.id, org_id=org.id, role="member")
    db_session.add(admin_membership)
    db_session.add(member_membership)
    await db_session.flush()
    
    # Create a task assigned to member
    task = Task(
        org_id=org.id,
        title="Member Task",
        status="todo",
        assignee_id=member_user.id
    )
    db_session.add(task)
    await db_session.commit()
    
    # Create tokens
    admin_token = AuthService.create_access_token({
        "user_id": admin_user.id,
        "org_id": org.id,
        "role": "admin"
    })
    member_token = AuthService.create_access_token({
        "user_id": member_user.id,
        "org_id": org.id,
        "role": "member"
    })
    
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}
    
    # Admin should be able to update any task
    response = await client.put(
        f"/tasks/{task.id}",
        json={"title": "Updated by Admin"},
        headers=admin_headers
    )
    assert response.status_code == 200
    
    # Member should be able to update their assigned task
    response = await client.put(
        f"/tasks/{task.id}",
        json={"title": "Updated by Member"},
        headers=member_headers
    )
    assert response.status_code == 200
    
    # Create another task not assigned to member
    other_task = Task(
        org_id=org.id,
        title="Other Task",
        status="todo",
        assignee_id=admin_user.id
    )
    db_session.add(other_task)
    await db_session.commit()
    
    # Member should not be able to update task they're not assigned to
    response = await client.put(
        f"/tasks/{other_task.id}",
        json={"title": "Unauthorized Update"},
        headers=member_headers
    )
    assert response.status_code == 403