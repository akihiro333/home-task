import pytest
import os
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User, Membership, Task
from app.services.auth import AuthService
from app.celery_app import export_tasks_task


@pytest.mark.asyncio
async def test_export_tasks_celery(db_session: AsyncSession):
    """Test Celery task export functionality."""
    
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
    
    # Create test tasks
    tasks_data = [
        {"title": "Task 1", "status": "todo", "description": "First task"},
        {"title": "Task 2", "status": "doing", "description": "Second task"},
        {"title": "Task 3", "status": "done", "description": "Third task"},
    ]
    
    for task_data in tasks_data:
        task = Task(org_id=org.id, assignee_id=user.id, **task_data)
        db_session.add(task)
    
    await db_session.commit()
    
    # Mock the sync database session for Celery
    with patch('app.celery_app.SyncSessionLocal') as mock_session:
        # Create a mock session that returns our test data
        mock_db = mock_session.return_value.__enter__.return_value
        
        # Mock organization query
        mock_org_result = type('MockResult', (), {})()
        mock_org_result.scalar_one_or_none = lambda: org
        mock_db.execute.return_value = mock_org_result
        
        # Mock tasks query - need to handle multiple calls
        def mock_execute(query):
            # Check if it's the organization query or tasks query
            query_str = str(query)
            if "organizations" in query_str:
                result = type('MockResult', (), {})()
                result.scalar_one_or_none = lambda: org
                return result
            else:  # tasks query
                result = type('MockResult', (), {})()
                # Create mock task objects
                mock_tasks = []
                for i, task_data in enumerate(tasks_data):
                    mock_task = type('MockTask', (), {
                        'id': i + 1,
                        'title': task_data['title'],
                        'description': task_data['description'],
                        'status': task_data['status'],
                        'assignee_id': user.id,
                        'due_date': None,
                        'created_at': type('MockDateTime', (), {'isoformat': lambda: '2024-01-01T00:00:00'})(),
                        'updated_at': type('MockDateTime', (), {'isoformat': lambda: '2024-01-01T00:00:00'})()
                    })()
                    mock_tasks.append(mock_task)
                
                result.scalars = lambda: type('MockScalars', (), {'all': lambda: mock_tasks})()
                return result
        
        mock_db.execute.side_effect = mock_execute
        
        # Create temporary exports directory
        os.makedirs("/tmp/exports", exist_ok=True)
        
        # Mock the exports directory
        with patch('app.celery_app.os.makedirs'), \
             patch('app.celery_app.os.path.join', side_effect=lambda *args: "/tmp/exports/test_export.csv"):
            
            # Run the export task
            result = export_tasks_task(org.id, user.id)
            
            # Verify the result
            assert "filename" in result
            assert "download_url" in result
            assert "task_count" in result
            assert result["task_count"] == 3
            assert "test" in result["filename"]  # Should contain org subdomain


@pytest.mark.asyncio 
async def test_celery_eager_mode():
    """Test that Celery can run in eager mode for testing."""
    from app.celery_app import celery_app
    
    # Configure Celery for eager execution
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    
    # Test that we can import and configure the task
    assert export_tasks_task is not None
    assert hasattr(export_tasks_task, 'delay')
    assert hasattr(export_tasks_task, 'apply_async')