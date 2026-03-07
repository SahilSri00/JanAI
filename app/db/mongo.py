from motor.motor_asyncio import AsyncIOMotorClient
import os
import structlog
from typing import Optional, Dict, List
from datetime import datetime

log = structlog.get_logger()

# MongoDB connection
client: Optional[AsyncIOMotorClient] = None
db = None

# Collections
documents_collection = None
schemes_collection = None
users_collection = None
progress_collection = None


async def connect_to_mongo():
    """Initialize MongoDB connection on app startup."""
    global client, db, documents_collection, schemes_collection, users_collection, progress_collection
    
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    
    try:
        client = AsyncIOMotorClient(mongodb_uri)
        db = client.cais_db
        
        # Initialize collections
        documents_collection = db.documents
        schemes_collection = db.schemes
        users_collection = db.users
        progress_collection = db.progress
        
        # Test connection
        await client.admin.command('ping')
        log.info("mongodb.connected", uri=mongodb_uri.split('@')[-1])  # hide credentials
    except Exception as e:
        log.exception("mongodb.connection_failed", error=str(e))
        raise


async def close_mongo_connection():
    """Close MongoDB connection on app shutdown."""
    global client
    if client:
        client.close()
        log.info("mongodb.disconnected")


async def save_document(document_data: Dict) -> str:
    """Save document processing result to MongoDB."""
    document_data["created_at"] = datetime.utcnow()
    document_data["updated_at"] = datetime.utcnow()
    
    result = await documents_collection.insert_one(document_data)
    log.info("mongodb.document_saved", document_id=document_data["document_id"])
    return str(result.inserted_id)


async def get_document(document_id: str) -> Optional[Dict]:
    """Retrieve document by ID."""
    doc = await documents_collection.find_one({"document_id": document_id})
    if doc:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
    return doc


async def update_document(document_id: str, update_data: Dict) -> bool:
    """Update document fields."""
    update_data["updated_at"] = datetime.utcnow()
    
    result = await documents_collection.update_one(
        {"document_id": document_id},
        {"$set": update_data}
    )
    return result.modified_count > 0


async def list_user_documents(user_id: str, limit: int = 50, skip: int = 0) -> List[Dict]:
    """List all documents for a user."""
    cursor = documents_collection.find(
        {"user_id": user_id}
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    documents = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        documents.append(doc)
    
    return documents


async def save_progress(progress_data: Dict) -> str:
    """Save user progress on action items."""
    progress_data["updated_at"] = datetime.utcnow()
    
    # Upsert: update if exists, insert if not
    result = await progress_collection.update_one(
        {
            "document_id": progress_data["document_id"],
            "user_id": progress_data.get("user_id")
        },
        {"$set": progress_data},
        upsert=True
    )
    
    log.info("mongodb.progress_saved", document_id=progress_data["document_id"])
    return str(result.upserted_id) if result.upserted_id else "updated"


async def get_progress(document_id: str, user_id: str = None) -> Optional[Dict]:
    """Get progress for a document."""
    query = {"document_id": document_id}
    if user_id:
        query["user_id"] = user_id
    
    progress = await progress_collection.find_one(query)
    if progress:
        progress["_id"] = str(progress["_id"])
    return progress