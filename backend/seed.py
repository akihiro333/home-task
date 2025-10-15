#!/usr/bin/env python3
"""Seed script to create demo data."""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Organization, User, Membership, Task
from app.services.auth import AuthService

async def seed_data():
    """Create seed data for development."""
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        print("Creating seed data...")
        
        # Create organizations
        acme_org = Organization(
            name="Acme Corporation",
            subdomain="acme"
        )
        beta_org = Organization(
            name="Beta Company",
            subdomain="beta"
        )
        db.add(acme_org)
        db.add(beta_org)
        await db.flush()
        
        # Create users
        users_data = [
            {"email": "admin@acme.com", "password": "admin123", "org": acme_org, "role": "admin"},
            {"email": "member@acme.com", "password": "member123", "org": acme_org, "role": "member"},
            {"email": "admin@beta.com", "password": "admin123", "org": beta_org, "role": "admin"},
            {"email": "member@beta.com", "password": "member123", "org": beta_org, "role": "member"},
        ]
        
        created_users = []
        for user_data in users_data:
            user = User(
                email=user_data["email"],
                password_hash=AuthService.hash_password(user_data["password"])
            )
            db.add(user)
            await db.flush()
            
            # Create membership
            membership = Membership(
                user_id=user.id,
                org_id=user_data["org"].id,
                role=user_data["role"]
            )
            db.add(membership)
            created_users.append((user, user_data["org"], user_data["role"]))
        
        await db.flush()
        
        # Create sample tasks
        tasks_data = [
            # Acme tasks
            {
                "org": acme_org,
                "title": "Set up project repository",
                "description": "Initialize Git repository and set up basic project structure",
                "status": "done",
                "assignee": next(u for u, o, r in created_users if o.id == acme_org.id and r == "admin"),
                "due_date": datetime.utcnow() - timedelta(days=2)
            },
            {
                "org": acme_org,
                "title": "Design user interface mockups",
                "description": "Create wireframes and mockups for the main application screens",
                "status": "doing",
                "assignee": next(u for u, o, r in created_users if o.id == acme_org.id and r == "member"),
                "due_date": datetime.utcnow() + timedelta(days=3)
            },
            {
                "org": acme_org,
                "title": "Implement authentication system",
                "description": "Build login, registration, and password reset functionality",
                "status": "todo",
                "assignee": next(u for u, o, r in created_users if o.id == acme_org.id and r == "admin"),
                "due_date": datetime.utcnow() + timedelta(days=7)
            },
            {
                "org": acme_org,
                "title": "Write API documentation",
                "description": "Document all API endpoints with examples and response schemas",
                "status": "todo",
                "assignee": None,
                "due_date": datetime.utcnow() + timedelta(days=10)
            },
            
            # Beta tasks
            {
                "org": beta_org,
                "title": "Market research analysis",
                "description": "Analyze competitor products and market positioning",
                "status": "done",
                "assignee": next(u for u, o, r in created_users if o.id == beta_org.id and r == "admin"),
                "due_date": datetime.utcnow() - timedelta(days=5)
            },
            {
                "org": beta_org,
                "title": "Customer feedback survey",
                "description": "Create and distribute survey to existing customers",
                "status": "doing",
                "assignee": next(u for u, o, r in created_users if o.id == beta_org.id and r == "member"),
                "due_date": datetime.utcnow() + timedelta(days=1)
            },
            {
                "org": beta_org,
                "title": "Product roadmap planning",
                "description": "Define features and timeline for next quarter",
                "status": "todo",
                "assignee": next(u for u, o, r in created_users if o.id == beta_org.id and r == "admin"),
                "due_date": datetime.utcnow() + timedelta(days=14)
            }
        ]
        
        for task_data in tasks_data:
            task = Task(
                org_id=task_data["org"].id,
                title=task_data["title"],
                description=task_data["description"],
                status=task_data["status"],
                assignee_id=task_data["assignee"].id if task_data["assignee"] else None,
                due_date=task_data["due_date"]
            )
            db.add(task)
        
        await db.commit()
        
        print("Seed data created successfully!")
        print("\nDemo accounts:")
        print("Acme Corporation (acme.example.local):")
        print("  - admin@acme.com / admin123 (admin)")
        print("  - member@acme.com / member123 (member)")
        print("\nBeta Company (beta.example.local):")
        print("  - admin@beta.com / admin123 (admin)")
        print("  - member@beta.com / member123 (member)")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())