from fastapi import FastAPI, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from typing import Dict, Optional, Any, Union
import uuid
import time
import asyncio
from enum import Enum
import os
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
import sys
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Import the captcha solver
from captcha_solver import solve_captcha

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Captcha AI Solver Service",
    description="API service for solving captchas using captcha-ai-solver",
    version="0.1.0",
)

# Custom middleware to handle exceptions that could crash the server
class CrashProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except SystemExit:
            print("SystemExit was caught in middleware. Preventing server crash.")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error occurred during captcha solving."}
            )
        except Exception as e:
            print(f"Unhandled exception caught in middleware: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error occurred."}
            )

# Add the crash protection middleware first
app.add_middleware(CrashProtectionMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Task status enum
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Task storage (in-memory database)
# In a production environment, you would use a proper database
tasks = {}

# Models
class CaptchaTask(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: float
    captcha_type: str
    captcha_params: Dict[str, Any]
    solver_config: Dict[str, Any]
    proxy_config: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None

class CaptchaRequest(BaseModel):
    captcha_type: str
    captcha_params: Dict[str, Any]
    solver_config: Optional[Dict[str, Any]] = None
    proxy_config: Optional[Dict[str, Any]] = None

class TaskResponse(BaseModel):
    task_id: str

class TaskStatusResponse(BaseModel):
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None

class ProxyConfig(BaseModel):
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

# Function to solve captcha in background
async def solve_captcha_task(task_id: str):
    task = tasks[task_id]
    task.status = TaskStatus.PROCESSING
    
    # Set a timeout for the task
    timeout_seconds = 300  # 5 minutes timeout
    start_time = time.time()
    
    # Create a watchdog task to monitor and mark as failed if it takes too long
    asyncio.create_task(monitor_task_timeout(task_id, timeout_seconds))
    
    try:
        # Get the solver configuration, use default if not provided
        solver_config = task.solver_config or {}
        
        # Always use the WIT API key from the environment variables
        # The client doesn't need to provide it
        if "WIT_API_KEY" in os.environ:
            solver_config["wit_api_key"] = os.environ["WIT_API_KEY"]
        else:
            raise ValueError("WIT_API_KEY environment variable is not set")
        
        # Add proxy configuration if provided
        if task.proxy_config:
            solver_config["proxy"] = task.proxy_config
        
        # Call the captcha solver with basic parameters
        result = solve_captcha(
            captcha_type=task.captcha_type,
            captcha_params=task.captcha_params,
            solver_config=solver_config
        )
        
        # Handle the result format (v0.2.0+)
        # The result is a dict with 'success', 'token', and 'error' keys
        if result["success"]:
            task.result = result["token"]
            task.status = TaskStatus.COMPLETED
        else:
            task.status = TaskStatus.FAILED
            task.error = result["error"] or "Captcha solving failed - no error details provided"
    except SystemExit as e:
        # Handle SystemExit exceptions specifically
        task.error = "Captcha solving process terminated unexpectedly"
        task.status = TaskStatus.FAILED
        print(f"SystemExit caught in task {task_id}: {e}")
    except Exception as e:
        # Update task with error
        task.error = str(e)
        task.status = TaskStatus.FAILED
        print(f"Exception in task {task_id}: {e}")

# Monitor task timeout and mark as failed if it takes too long
async def monitor_task_timeout(task_id: str, timeout_seconds: int):
    start_time = time.time()
    while task_id in tasks and tasks[task_id].status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        if time.time() - start_time > timeout_seconds:
            if task_id in tasks:
                tasks[task_id].status = TaskStatus.FAILED
                tasks[task_id].error = f"Task timed out after {timeout_seconds} seconds"
                print(f"Task {task_id} timed out after {timeout_seconds} seconds")
            break
        await asyncio.sleep(5)  # Check every 5 seconds

# Routes
@app.post("/create_task", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(request: CaptchaRequest, background_tasks: BackgroundTasks):
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    
    # Create a new task
    task = CaptchaTask(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=time.time(),
        captcha_type=request.captcha_type,
        captcha_params=request.captcha_params,
        solver_config=request.solver_config or {},
        proxy_config=request.proxy_config
    )
    
    # Store the task
    tasks[task_id] = task
    
    # Start solving the captcha in the background
    background_tasks.add_task(solve_captcha_task, task_id)
    
    # Return the task ID
    return TaskResponse(task_id=task_id)

@app.get("/get_task_result/{task_id}", response_model=TaskStatusResponse)
async def get_task_result(task_id: str):
    # Check if the task exists
    if task_id not in tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    
    task = tasks[task_id]
    
    # If the task is still processing, return 202 Accepted
    if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": task.status}
        )
    
    # If the task is completed or failed, return the result or error
    return TaskStatusResponse(
        status=task.status,
        result=task.result,
        error=task.error
    )



# Clean up old tasks periodically and handle zombie tasks
async def cleanup_old_tasks():
    while True:
        current_time = time.time()
        expired_tasks = []
        zombie_tasks = []
        
        # Find tasks older than 1 hour that are completed or failed
        # Also find zombie tasks (stuck in processing for more than 10 minutes)
        for task_id, task in tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and 
                current_time - task.created_at > 3600):  # 1 hour
                expired_tasks.append(task_id)
            elif (task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING] and 
                  current_time - task.created_at > 600):  # 10 minutes
                zombie_tasks.append(task_id)
        
        # Remove expired tasks
        for task_id in expired_tasks:
            del tasks[task_id]
            print(f"Cleaned up completed/failed task {task_id}")
        
        # Mark zombie tasks as failed
        for task_id in zombie_tasks:
            if task_id in tasks:
                tasks[task_id].status = TaskStatus.FAILED
                tasks[task_id].error = "Task processing timed out"
                print(f"Marked zombie task {task_id} as failed")
        
        # Sleep for 1 minute before next cleanup
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    # Start the cleanup task when the application starts
    asyncio.create_task(cleanup_old_tasks())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True) 