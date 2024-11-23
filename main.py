from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination, paginate, Page
import httpx
import random, string
from google.cloud import secretmanager

### logging set up# ##
import time
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Imports the Cloud Logging client library
import google.cloud.logging

# Instantiates a client
client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# you're running in and integrates the handler with the
# Python logging module. By default this captures all logs
# at INFO level and higher
client.setup_logging()

### create fastapi application ###
app = FastAPI()

### logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware on each resource that implements before and after logging for all methods/paths.
    reference: https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware

    Args:
        request (Request): The http request object
        call_next (function): A function call_next that will receive the request as a parameter.

    Returns:
        function: Then it returns the response generated by the corresponding path operation.
    """
    # generate a correlation id for each request
    cid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    logger.info(f"rid={cid} | request started | path={request.url.path}")
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = '{0:.2f}'.format(process_time)
    logger.info(f"cid={cid} | request completed in={formatted_process_time} ms | status_code={response.status_code}")
    
    return response

# enable CORS
origins = [
    "http://localhost",
    "http://localhost:8080",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_secret(resource_id: str) -> str:
    """
    Retrieve a secret from Google Secret Manager.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"{resource_id}/versions/latest"

    response = client.access_secret_version(request={"name": name})
    secret_payload = response.payload.data.decode("UTF-8")

    return secret_payload

POST_SERVICE_URL = get_secret("projects/745799261495/secrets/POST_SERVICE_URL")
COMMENT_SERVICE_URL = get_secret("projects/745799261495/secrets/COMMENT_SERVICE_URL")

@app.get("/")
async def root():
    return {"message": "Welcome to the main feed service!"}

async def fetch_all_comments():
    """
    Fetch all comments from the comment service and organize comment1 with nested comment2 replies.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(COMMENT_SERVICE_URL)
        response.raise_for_status()
        data = response.json()

        # Extract and structure comment1 and comment2 data
        comment1_data = data.get("comment1", [])
        comment2_data = data.get("comment2", [])
        # Create a dictionary to map comment1_id to their replies in comment2
        comment2_by_comment1_id = {}
        for reply in comment2_data:
            comment1_id = reply["comment1_id"]
            if comment1_id not in comment2_by_comment1_id:
                comment2_by_comment1_id[comment1_id] = []
            comment2_by_comment1_id[comment1_id].append({
                "id": reply["id"],
                "content": reply["content"],
                "writer_uni": reply["writter_uni"],  # Note: typo retained as in the original data
                "likes": reply["likes"]
            })

        # Attach replies from comment2 to their corresponding comment1
        structured_comments = []
        for comment in comment1_data:
            comment_id = comment["id"]
            structured_comments.append({
                "id": comment_id,
                "post_id": comment["post_id"],
                "content": comment["content"],
                "writer_uni": comment["writter_uni"],
                "likes": comment["likes"],
                "replies": comment2_by_comment1_id.get(comment_id, [])  # Attach replies
            })
        return structured_comments
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching comments: {e}")  # Log HTTP error
        raise HTTPException(status_code=e.response.status_code, detail="Error fetching comments.")
    except Exception as e:
        logger.error(f"Unexpected error fetching comments: {e}")  # Log unexpected error
        raise HTTPException(status_code=500, detail="An error occurred while fetching comments.")

@app.get("/main_feed", response_model=Page[dict])
async def main_feed():
    try:
        # Fetch all posts from the post service
        async with httpx.AsyncClient() as client:
            response = await client.get(POST_SERVICE_URL)
        response.raise_for_status()
        posts = response.json()

        # Fetch all comments once and filter them by post_id
        comments = await fetch_all_comments()
        # Attach filtered comments to each post
        for post in posts:
            post_id = post.get("pid")
            if post_id is not None:
                # Filter comments for the current post
                post["comments"] = [comment for comment in comments if comment["post_id"] == post_id]
        return paginate(posts)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching posts: {e}")
        raise HTTPException(status_code=e.response.status_code, detail="Error fetching posts.")
    except Exception as e:
        logger.error(f"Unexpected error fetching posts: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


add_pagination(app)


# if __name__ == "__main__":
#     uvicorn.run(app=app, host='0.0.0.0', port=8080)
