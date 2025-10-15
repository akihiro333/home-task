from typing import Optional, List
from datetime import datetime
import base64
import json
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from ..database import get_db
from ..models.task import Task
from ..models.user import User
from ..middleware.auth import AuthMiddleware
from ..middleware.tenant import TenantMiddleware
from ..schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse,
    ExportJobResponse, JobStatusResponse
)
from ..redis_client import redis_client

router = APIRouter(tags=["tasks"])


def encode_cursor(task_id: int, created_at: datetime) -> str:
    """Encode cursor for pagination."""
    cursor_data = {
        "id": task_id,
        "created_at": created_at.isoformat()
    }
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()


def decode_cursor(cursor: str) -> tuple[int, datetime]:
    """Decode cursor for pagination."""
    try:
        cursor_data = json.loads(base64.b64decode(cursor).decode())
        return cursor_data["id"], datetime.fromisoformat(cursor_data["created_at"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cursor"
        )


@router.post("/organizations/{org_id}/tasks", response_model=TaskResponse)
async def create_task(
    org_id: int,
    task_data: TaskCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(AuthMiddleware.require_auth)
):
    # Verify org context
    current_org = TenantMiddleware.get_current_org(request)
    if current_org.id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization"
        )

    # Create task
    task = Task(
        org_id=org_id,
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        assignee_id=task_data.assignee_id,
        due_date=task_data.due_date
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Publish realtime update
    await redis_client.publish(
        f"org:{org_id}:tasks",
        json.dumps({
            "type": "task_created",
            "task": TaskResponse.from_orm(task).dict()
        })
    )

    return TaskResponse.from_orm(task)


@router.get("/organizations/{org_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    org_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(AuthMiddleware.require_auth),
    status_filter: Optional[str] = Query(None, alias="status"),
    assignee_id: Optional[int] = Query(None, alias="assignee"),
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, le=100)
):
    # Verify org context
    current_org = TenantMiddleware.get_current_org(request)
    if current_org.id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization"
        )

    # Build query
    query = select(Task).where(Task.org_id == org_id)

    # Apply filters
    if status_filter:
        query = query.where(Task.status == status_filter)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)

    # Apply cursor pagination
    if cursor:
        cursor_id, cursor_created_at = decode_cursor(cursor)
        query = query.where(
            or_(
                Task.created_at < cursor_created_at,
                and_(Task.created_at == cursor_created_at, Task.id < cursor_id)
            )
        )

    # Order and limit
    query = query.order_by(desc(Task.created_at), desc(Task.id)).limit(limit + 1)

    result = await db.execute(query)
    tasks = result.scalars().all()

    # Check if there are more results
    has_more = len(tasks) > limit
    if has_more:
        tasks = tasks[:-1]

    # Generate next cursor
    next_cursor = None
    if has_more and tasks:
        last_task = tasks[-1]
        next_cursor = encode_cursor(last_task.id, last_task.created_at)

    return TaskListResponse(
        tasks=[TaskResponse.from_orm(task) for task in tasks],
        next_cursor=next_cursor,
        has_more=has_more
    )


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(AuthMiddleware.require_auth)
):
    # Get task
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Verify org context
    current_org = TenantMiddleware.get_current_org(request)
    if task.org_id != current_org.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this task"
        )

    # Check permissions
    from ..middleware.auth import AuthMiddleware
    membership = await AuthMiddleware.get_user_membership(current_user, current_org.id, db)
    
    if membership.role != "admin" and task.assignee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify tasks you created or are assigned to"
        )

    # Update task
    update_data = task_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)

    # Publish realtime update
    await redis_client.publish(
        f"org:{current_org.id}:tasks",
        json.dumps({
            "type": "task_updated",
            "task": TaskResponse.from_orm(task).dict()
        })
    )

    return TaskResponse.from_orm(task)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(AuthMiddleware.require_auth)
):
    # Get task
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Verify org context
    current_org = TenantMiddleware.get_current_org(request)
    if task.org_id != current_org.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this task"
        )

    # Check permissions
    from ..middleware.auth import AuthMiddleware
    membership = await AuthMiddleware.get_user_membership(current_user, current_org.id, db)
    
    if membership.role != "admin" and task.assignee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete tasks you created or are assigned to"
        )

    # Delete task
    await db.delete(task)
    await db.commit()

    # Publish realtime update
    await redis_client.publish(
        f"org:{current_org.id}:tasks",
        json.dumps({
            "type": "task_deleted",
            "task_id": task_id
        })
    )

    return {"message": "Task deleted successfully"}


@router.post("/tasks/{task_id}/export", response_model=ExportJobResponse)
async def export_tasks(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(AuthMiddleware.require_auth)
):
    # Verify org context and permissions
    current_org = TenantMiddleware.get_current_org(request)
    
    # Import here to avoid circular imports
    from ..celery_app import export_tasks_task
    
    # Start export job
    job = export_tasks_task.delay(current_org.id, current_user.id)
    
    return ExportJobResponse(
        job_id=job.id,
        status="pending"
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(AuthMiddleware.require_auth)
):
    # Import here to avoid circular imports
    from ..celery_app import celery_app
    
    job = celery_app.AsyncResult(job_id)
    
    if job.state == "PENDING":
        status = "pending"
        result = None
        error = None
    elif job.state == "SUCCESS":
        status = "completed"
        result = job.result
        error = None
    elif job.state == "FAILURE":
        status = "failed"
        result = None
        error = str(job.info)
    else:
        status = job.state.lower()
        result = None
        error = None

    return JobStatusResponse(
        job_id=job_id,
        status=status,
        result=result,
        error=error
    )