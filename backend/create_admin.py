import asyncio
from app.core.settings import get_settings
from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.core.security import hash_password
from sqlalchemy import select

async def create_platform_admin():
    async with AsyncSessionLocal() as session:
        # Check if user already exists
        stmt = select(User).where(User.email == "platformadmin@test.com")
        existing = await session.scalar(stmt)
        
        if existing:
            print("✗ Platform admin already exists")
            return
        
        # Create platform admin user
        admin_user = User(
            email="platformadmin@test.com",
            full_name="Platform Admin",
            password_hash=hash_password("admin12345"),
            company_id=None,  # No company = platform admin
            role="platform_admin",
            is_active=True
        )
        
        session.add(admin_user)
        await session.commit()
        
        print("✓ Platform admin created:")
        print(f"  Email: platformadmin@test.com")
        print(f"  Password: admin12345")
        print(f"  Role: platform_admin")

asyncio.run(create_platform_admin())
