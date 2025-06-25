# Main script to run the organizr api, startup scripts, start the different routers

import logging
import setup
import database
from fastapi import FastAPI
from routers import users, calendar, apps

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database connection
db_connection = database.get_connection()
db_cursor = db_connection.cursor()

# Check if the database is set up, if not, create it and the necessary tables and the admin user
setup.setup_database()

# Initialize FastAPI app
app = FastAPI(title="Organizr-API", version="0.3.2")

# Include routers
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
app.include_router(apps.router, prefix="/apps", tags=["apps"])

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
