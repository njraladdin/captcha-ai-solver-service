import requests
import time
import json
import sys
import argparse

# API endpoint
BASE_URL = "http://localhost:8000"

# Default captcha parameters
DEFAULT_WEBSITE_URL = "https://2captcha.com/demo/recaptcha-v2"
DEFAULT_WEBSITE_KEY = "6LfD3PIbAAAAAJs_eEHvoOl75_83eXSqpPSRFJ_u"

# Proxy configuration (optional)
PROXY_HOST = ""  # Add your proxy host here if needed
PROXY_PORT = 0   # Add your proxy port here if needed
PROXY_USERNAME = ""  # Add your proxy username here if needed
PROXY_PASSWORD = ""  # Add your proxy password here if needed

def create_task(captcha_type, captcha_params, solver_config=None, proxy_config=None):
    """Create a new captcha solving task."""
    url = f"{BASE_URL}/create_task"
    
    payload = {
        "captcha_type": captcha_type,
        "captcha_params": captcha_params
    }
    
    if solver_config:
        payload["solver_config"] = solver_config
    
    if proxy_config:
        payload["proxy_config"] = proxy_config
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 201:
        return response.json()["task_id"]
    else:
        print(f"Error creating task: {response.status_code}")
        print(response.text)
        return None

def get_task_result(task_id, max_attempts=60, delay=2):
    """Get the result of a captcha solving task."""
    url = f"{BASE_URL}/get_task_result/{task_id}"
    
    for attempt in range(max_attempts):
        response = requests.get(url)
        
        if response.status_code == 202:
            # Task is still processing
            print(f"Task is {response.json()['status']}... (attempt {attempt+1}/{max_attempts})")
            time.sleep(delay)
            continue
        
        if response.status_code == 200:
            result = response.json()
            if result["status"] == "completed":
                if result["result"] is None:
                    print("Task completed but returned no result (solver failure)")
                    return None
                print("Task completed successfully!")
                return result["result"]
            else:
                print(f"Task failed: {result['error']}")
                return None
        
        print(f"Unexpected response: {response.status_code}")
        print(response.text)
        return None
    
    print("Max attempts reached. Task is still processing.")
    return None

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Captcha AI Solver Client')
    parser.add_argument('--website', type=str, default=DEFAULT_WEBSITE_URL,
                        help=f'Website URL (default: {DEFAULT_WEBSITE_URL})')
    parser.add_argument('--key', type=str, default=DEFAULT_WEBSITE_KEY,
                        help=f'reCAPTCHA site key (default: {DEFAULT_WEBSITE_KEY})')
    parser.add_argument('--proxy-host', type=str, default=PROXY_HOST,
                        help='Proxy host (optional)')
    parser.add_argument('--proxy-port', type=int, default=PROXY_PORT,
                        help='Proxy port (optional)')
    parser.add_argument('--proxy-user', type=str, default=PROXY_USERNAME,
                        help='Proxy username (optional)')
    parser.add_argument('--proxy-pass', type=str, default=PROXY_PASSWORD,
                        help='Proxy password (optional)')
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Example captcha parameters
    captcha_params = {
        "website_url": args.website,
        "website_key": args.key
    }
    
    # Empty solver config - the server will use the WIT API key from .env
    solver_config = {}
    
    # Proxy config
    proxy_config = None
    if args.proxy_host and args.proxy_port:
        proxy_config = {
            "host": args.proxy_host,
            "port": args.proxy_port
        }
        if args.proxy_user:
            proxy_config["username"] = args.proxy_user
        if args.proxy_pass:
            proxy_config["password"] = args.proxy_pass
    
    # Create a new task
    print("Creating captcha solving task...")
    task_id = create_task("recaptcha_v2", captcha_params, solver_config, proxy_config)
    
    if not task_id:
        print("Failed to create task.")
        return
    
    print(f"Task created with ID: {task_id}")
    
    # Get the result
    print("Waiting for result...")
    result = get_task_result(task_id)
    
    if result:
        print(f"Captcha token: {result[:30]}...")

if __name__ == "__main__":
    main() 