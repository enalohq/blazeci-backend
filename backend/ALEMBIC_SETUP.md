# 🗃️ Alembic Database Migration Setup

## ✅ **Alembic is now fully configured!**

Your project now has automatic database schema migration and versioning capabilities.

## 📁 **What was added:**

### **Configuration Files:**
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Environment configuration for SQLModel
- `alembic/versions/` - Migration files directory

### **Management Scripts:**
- `migrate.py` - CLI tool for migration management
- `lambda_migrate.py` - Lambda-specific migration utilities

### **Updated Files:**
- `app/db.py` - Now uses Alembic for database initialization
- `app/config.py` - Fixed encoding issues

## 🚀 **How to use:**

### **Development Commands:**

```bash
# Create a new migration after changing models
python migrate.py create "Add new field to User model"

# Apply all pending migrations
python migrate.py upgrade

# Apply specific migration
python migrate.py upgrade +1    # Apply next migration
python migrate.py upgrade abc123 # Apply to specific revision

# Rollback migrations
python migrate.py downgrade -1   # Rollback one migration
python migrate.py downgrade abc123 # Rollback to specific revision

# Check current status
python migrate.py status

# View migration history
python migrate.py history
```

### **Direct Alembic Commands:**
```bash
# Alternative to using migrate.py
.\.venv\Scripts\alembic revision --autogenerate -m "Migration message"
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic downgrade -1
.\.venv\Scripts\alembic history
.\.venv\Scripts\alembic current
```

## 🔄 **Workflow for Schema Changes:**

1. **Modify your models** in `app/models.py`
2. **Create migration:** `python migrate.py create "Describe your changes"`
3. **Review the generated migration** in `alembic/versions/`
4. **Apply migration:** `python migrate.py upgrade`
5. **Test your changes**

## 🌐 **Lambda Integration:**

### **Automatic Migration on Startup:**
Your `init_db()` function now automatically runs migrations when the app starts:
- ✅ **Development**: Migrations run on FastAPI startup
- ✅ **Lambda**: Migrations run when Lambda initializes
- ✅ **Fallback**: If migrations fail, falls back to basic table creation

### **Manual Lambda Migration:**
```python
from lambda_migrate import migrate_lambda_db
migrate_lambda_db()  # Run in Lambda if needed
```

## 📊 **Current Status:**

- ✅ **Initial migration created** (`4bf14ac880d4`)
- ✅ **Test migration created** (`f909172dbee7`) 
- ✅ **Database schema versioned**
- ✅ **Auto-migration on startup**

## 🔧 **Benefits You Now Have:**

### **Version Control:**
- ✅ Database schema is now version controlled
- ✅ Track all changes with migration history
- ✅ Safe rollback capabilities

### **Team Collaboration:**
- ✅ Consistent schema across all environments
- ✅ No more manual database updates
- ✅ Migrations can be committed to git

### **Production Safety:**
- ✅ Controlled schema updates
- ✅ Backup/rollback capabilities
- ✅ No data loss during schema changes

### **Multi-Environment:**
- ✅ Dev, staging, production consistency
- ✅ Automated deployment-time migrations
- ✅ Environment-specific configurations

## 📝 **Example Migration Workflow:**

```bash
# 1. Add a new field to your User model
# Edit app/models.py and add: newsletter_subscribed: bool = False

# 2. Generate migration
python migrate.py create "Add newsletter subscription to User"

# 3. Review the generated migration file
# Check alembic/versions/xxxxx_add_newsletter_subscription_to_user.py

# 4. Apply the migration
python migrate.py upgrade

# 5. Your database is now updated!
```

## 🚨 **Important Notes:**

- **Always review generated migrations** before applying
- **Test migrations in development** before production
- **Backup database** before major schema changes
- **Migrations are applied automatically** on app startup

## 🔍 **Troubleshooting:**

If migrations fail, the system will fall back to basic table creation. Check:
1. Database connectivity
2. Migration file syntax
3. Model import issues
4. Conflicting schema changes

Your database migrations are now fully automated and production-ready! 🎉