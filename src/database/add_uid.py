from pymongo import MongoClient
from datetime import datetime, timedelta

# MongoDB Atlas configuration (same as mongo_client.py)
MONGO_URI = "ur monogo db uri"
DB_NAME = "uidbypass"
COLLECTION_NAME = "subscriptions"


def add_uid(uid: str, days: int = 30, status: str = "active"):
    """
    Add a new UID to the database with subscription details
    
    Args:
        uid: The UID to add
        days: Number of days for subscription (default: 30)
        status: Subscription status (default: "active")
    """
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Test connection
        client.server_info()
        print("[MONGODB] Connected successfully")
        
        # Calculate expiry date
        expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Check if UID already exists
        existing = collection.find_one({"uid": uid.strip()})
        if existing:
            print(f"[WARNING] UID '{uid}' already exists in database!")
            print(f"[INFO] Current expiry: {existing.get('expiry_date', 'N/A')}")
            print(f"[INFO] Current status: {existing.get('status', 'N/A')}")
            
            # Ask if user wants to update
            update = input("Do you want to update this UID? (y/n): ").strip().lower()
            if update == 'y':
                collection.update_one(
                    {"uid": uid.strip()},
                    {"$set": {
                        "status": status,
                        "expiry_date": expiry_date,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }}
                )
                print(f"[SUCCESS] UID '{uid}' updated successfully!")
                print(f"[INFO] New expiry date: {expiry_date}")
            else:
                print("[CANCELLED] No changes made.")
            return
        
        # Create new subscription document
        subscription = {
            "uid": uid.strip(),
            "status": status,
            "expiry_date": expiry_date,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Insert into database
        result = collection.insert_one(subscription)
        print(f"[SUCCESS] UID '{uid}' added successfully!")
        print(f"[INFO] Document ID: {result.inserted_id}")
        print(f"[INFO] Expiry date: {expiry_date}")
        print(f"[INFO] Status: {status}")
        
    except Exception as e:
        print(f"[ERROR] Failed to add UID: {e}")
    finally:
        if 'client' in locals():
            client.close()


def delete_uid(uid: str):
    """Delete a UID from the database"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        client.server_info()
        
        result = collection.delete_one({"uid": uid.strip()})
        if result.deleted_count > 0:
            print(f"[SUCCESS] UID '{uid}' deleted successfully!")
        else:
            print(f"[WARNING] UID '{uid}' not found in database.")
            
    except Exception as e:
        print(f"[ERROR] Failed to delete UID: {e}")
    finally:
        if 'client' in locals():
            client.close()


def list_all_uids():
    """List all UIDs in the database"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        client.server_info()
        
        uids = collection.find({})
        print("\n" + "="*60)
        print("ALL SUBSCRIPTIONS IN DATABASE")
        print("="*60)
        
        count = 0
        for doc in uids:
            count += 1
            print(f"\n[{count}] UID: {doc.get('uid', 'N/A')}")
            print(f"    Status: {doc.get('status', 'N/A')}")
            print(f"    Expiry: {doc.get('expiry_date', 'N/A')}")
            print(f"    Created: {doc.get('created_at', 'N/A')}")
        
        if count == 0:
            print("[INFO] No subscriptions found in database.")
        else:
            print(f"\n[TOTAL] {count} subscription(s) found.")
        print("="*60 + "\n")
            
    except Exception as e:
        print(f"[ERROR] Failed to list UIDs: {e}")
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    print("\n" + "="*50)
    print("UID SUBSCRIPTION MANAGER")
    print("="*50)
    print("\n1. Add new UID")
    print("2. Delete UID")
    print("3. List all UIDs")
    print("4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == "1":
        uid = input("Enter UID to add: ").strip()
        days = input("Enter subscription days (default 30): ").strip()
        if not days:
            days = 30
        else:
            days = int(days)
        add_uid(uid, days)
        
    elif choice == "2":
        uid = input("Enter UID to delete: ").strip()
        confirm = input(f"Are you sure you want to delete '{uid}'? (y/n): ").strip().lower()
        if confirm == 'y':
            delete_uid(uid)
        else:
            print("[CANCELLED] No changes made.")
            
    elif choice == "3":
        list_all_uids()
        
    elif choice == "4":
        print("Goodbye!")
        
    else:
        print("[ERROR] Invalid option.")
