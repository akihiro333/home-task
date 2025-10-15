import os
import csv
from datetime import datetime
from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models.task import Task
from .models.organization import Organization

# Create Celery app
celery_app = Celery(
    "taskmanager",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.celery_app"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
)

# Create sync database connection for Celery tasks
sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(sync_db_url)
SyncSessionLocal = sessionmaker(bind=sync_engine)


@celery_app.task(bind=True)
def export_tasks_task(self, org_id: int, user_id: int):
    """Export all tasks for an organization to CSV."""
    try:
        # Create exports directory
        exports_dir = "/exports"
        os.makedirs(exports_dir, exist_ok=True)
        
        # Get organization info
        with SyncSessionLocal() as db:
            org_result = db.execute(
                select(Organization).where(Organization.id == org_id)
            )
            org = org_result.scalar_one_or_none()
            
            if not org:
                raise Exception(f"Organization {org_id} not found")
            
            # Get all tasks for the organization
            tasks_result = db.execute(
                select(Task).where(Task.org_id == org_id).order_by(Task.created_at)
            )
            tasks = tasks_result.scalars().all()
            
            # Generate filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{org.subdomain}_{timestamp}.csv"
            filepath = os.path.join(exports_dir, filename)
            
            # Write CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'id', 'title', 'description', 'status', 'assignee_id',
                    'due_date', 'created_at', 'updated_at'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for task in tasks:
                    writer.writerow({
                        'id': task.id,
                        'title': task.title,
                        'description': task.description or '',
                        'status': task.status,
                        'assignee_id': task.assignee_id or '',
                        'due_date': task.due_date.isoformat() if task.due_date else '',
                        'created_at': task.created_at.isoformat(),
                        'updated_at': task.updated_at.isoformat()
                    })
            
            # Generate download URL (in production, this would be a signed URL)
            download_url = f"{settings.PUBLIC_URL}/exports/{filename}"
            
            # Log the download URL (simulate sending email)
            print(f"CSV export completed for org {org.subdomain}: {download_url}")
            
            return {
                "filename": filename,
                "download_url": download_url,
                "task_count": len(tasks)
            }
            
    except Exception as exc:
        print(f"Export task failed: {exc}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)