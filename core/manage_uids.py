import requests
import json
import time

# ==========================================
#              CONFIGURATION
# ==========================================
# Your actual website from C:\Users\1nOnlySahil\Desktop\uidbypass\UID\app.py
API_URL = 'https://raw.githubusercontent.com/UIDBYPASS/uidbypass/main/uidbypass/raw/uid'
# KEY from app.py line 54
INTERNAL_KEY = 'rifat11'
# ==========================================

def make_request(method, endpoint, params=None):
    url = f"{API_URL}{endpoint}"
    # Adding the key as a query parameter as seen in app.py
    if params is None:
        params = {}
    params['key'] = INTERNAL_KEY
    
    try:
        response = requests.get(url, params=params)
        
        print("\n" + "="*40)
        print(f"Status Code: {response.status_code}")
        print(response.text)
        print("="*40 + "\n")
    except Exception as e:
        print(f"\n[!] Error: {e}\n")

def main():
    print("=== UID BYPASS UID Management Loop ===")
    print(f"Connected to: {API_URL}")
    
    while True:
        print("\nOptions:")
        print("1. Add User")
        print("2. Remove User")
        print("3. Update User (Change Validity)")
        print("4. Get Raw UID List")
        print("5. Exit")
        
        choice = input("\nSelect an option (1-5): ").strip()
        
        if choice == '1':
            uid = input("Enter UID: ").strip()
            days = input("Enter Days: ").strip()
            if uid and days:
                make_request('GET', '/uid/add', params={'uid': uid, 'validity': days})
            else:
                print("UID and Days are required!")
                
        elif choice == '2':
            uid = input("Enter UID to remove: ").strip()
            if uid:
                make_request('GET', '/uid/remove', params={'uid': uid})
            else:
                print("UID is required!")

        elif choice == '3':
            uid = input("Enter UID to update: ").strip()
            days = input("Enter new Days: ").strip()
            if uid and days:
                make_request('GET', '/uid/update', params={'uid': uid, 'validity': days})
            else:
                print("UID and Days are required!")
                
        elif choice == '4':
            make_request('GET', '/raw/uid')
                
        elif choice == '5':
            print("Exiting...")
            break
        else:
            print("Invalid selection, try again.")

if __name__ == "__main__":
    main()
