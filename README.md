# Captcha AI Solver Service

A FastAPI service for solving reCAPTCHA v2 using the [captcha-ai-solver](https://github.com/njraladdin/captcha-ai-solver) library. This service provides a simple API for submitting captcha solving tasks and retrieving results.

## Requirements

- Python 3.7+
- Windows OS (required by the captcha-ai-solver library)
- Admin privileges (required by the captcha-ai-solver library for host file modifications)
- Wit.ai API key for audio challenges

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/captcha-ai-solver-service.git
cd captcha-ai-solver-service
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on the `.env.example` file:
```bash
cp .env.example .env
```

4. Edit the `.env` file and add your Wit.ai API key:
```
WIT_API_KEY=your_wit_api_key_here
```

## Running the Service

Run the service with:

```bash
python main.py
```

The API will be available at http://localhost:8000

## API Documentation

Once the service is running, you can access the Swagger UI documentation at http://localhost:8000/docs

### Endpoints

#### Create a Captcha Solving Task

```
POST /create_task
```

Request body:
```json
{
  "captcha_type": "recaptcha_v2",
  "captcha_params": {
    "website_url": "https://www.google.com/recaptcha/api2/demo",
    "website_key": "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"
  },
  "solver_config": {},
  "proxy_config": {
    "host": "proxy.example.com",
    "port": 8080,
    "username": "user",
    "password": "pass"
  }
}
```

Response:
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### Get Task Result

```
GET /get_task_result/{task_id}
```

Response (task in progress - 202 Accepted):
```json
{
  "status": "processing"
}
```

Response (task completed - 200 OK):
```json
{
  "status": "completed",
  "result": "03AGdBq24PBCbwiDRaS_MJ...",
  "error": null
}
```

Response (task failed - 200 OK):
```json
{
  "status": "failed",
  "result": null,
  "error": "Error message"
}
```

## Notes

- The Wit.ai API key must be set in the `.env` file. The service will not start without it.
- This service uses an in-memory database to store tasks. In a production environment, you should use a proper database.
- The service implements automatic task cleanup for completed/failed tasks older than 1 hour.
- The captcha-ai-solver library requires Windows and admin privileges to run.

### Using Mobile Proxies

This service supports the use of mobile proxies for solving captchas. To use a mobile proxy, include the `proxy_config` field in your request with the following parameters:

- `host`: The proxy host address
- `port`: The proxy port number
- `username`: (Optional) Username for proxy authentication
- `password`: (Optional) Password for proxy authentication

Example of using the example client with a mobile proxy:

```bash
python example_client.py --proxy-host proxy.example.com --proxy-port 8080 --proxy-user user --proxy-pass pass
``` 