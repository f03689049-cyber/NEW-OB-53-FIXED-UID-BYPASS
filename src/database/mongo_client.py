from pymongo import MongoClient
from datetime import datetime

# MongoDB Atlas configuration
MONGO_URI = "mongodb+srv://63mxs8:xanlj@cluster0.h5nldwx.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "uidbypass"
COLLECTION_NAME = "subscriptions"

class MongoDBClient:
    def __init__(self):
        """Initialize MongoDB connection"""
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.db = self.client[DB_NAME]
            self.collection = self.db[COLLECTION_NAME]
            
            # Test connection
            self.client.server_info()
            print("[MONGODB] Connected successfully")
        except Exception as e:
            print(f"[MONGODB] Connection failed: {e}")
            self.client = None
    
    def get_subscription(self, uid: str):
        """Get subscription from MongoDB by UID"""
        if not self.client:
            return None
        
        try:
            return self.collection.find_one({"uid": uid})
        except Exception as e:
            print(f"[MONGODB] Error: {e}")
            return None
    
    def check_subscription(self, uid: str) -> dict:
        """Check subscription validity"""
        uid = uid.strip()
        sub = self.get_subscription(uid)
        
        if not sub:
            return {"valid": False, "reason": "not_found", "expiry_date": "N/A"}
        
        # Check status
        if sub.get("status") != "active":
            return {"valid": False, "reason": "inactive", "expiry_date": sub.get("expiry_date", "N/A")}
        
        # Check expiry
        try:
            expiry = datetime.strptime(sub["expiry_date"], "%Y-%m-%d")
            if datetime.now() > expiry:
                return {"valid": False, "reason": "expired", "expiry_date": sub["expiry_date"]}
            
            return {"valid": True, "reason": "active", "expiry_date": sub["expiry_date"]}
        except:
            return {"valid": False, "reason": "invalid_date", "expiry_date": "N/A"}
