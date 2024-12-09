import io
import google.cloud.logging
from typing import Annotated
from fastapi import FastAPI, HTTPException, Request, UploadFile, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination, paginate, Page
import httpx
import random
import string

from middleware import SecurityTokenMiddleware

from service.gcloud_secret import get_secret
from service.main_feed import *

### logging set up# ##
import time
import logging
logger = logging.getLogger(__name__)

# * Imports the Cloud Logging client library

# Instantiates a client
client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# you're running in and integrates the handler with the
# Python logging module. By default this captures all logs
# at INFO level and higher
client.setup_logging()

### create fastapi application ###
app = FastAPI()

# Add middleware for checking user scopes
SECRET_KEY = get_secret(
    "projects/745799261495/secrets/SECURITY_MANAGER_SECRET_KEY")
REQUIRED_SCOPE = "mainfeed"

app.add_middleware(
    SecurityTokenMiddleware,
    secret_key=SECRET_KEY,
    required_scope=REQUIRED_SCOPE,
)

# Add middleware for logging
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
    logger.info(
        f"cid={cid} | request completed in={
            formatted_process_time} ms | status_code={response.status_code}"
    )

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

# get secrets
POST_SERVICE_URL = get_secret("projects/745799261495/secrets/POST_SERVICE_URL")
COMMENT_SERVICE_URL = get_secret(
    "projects/745799261495/secrets/COMMENT_SERVICE_URL")
STORAGE_SERVICE_URL = get_secret(
    "projects/745799261495/secrets/STORAGE_SERVICE_URL")


@app.get("/")
async def root():
    return {"message": "Welcome to the main feed service!"}


@app.get("/main_feed", response_model=Page[dict])
async def main_feed(
    # extract the token from the request header
    x_security_token: str = Header(...),
):
    # propagate to downtream service
    headers = {"X-Security-Token": x_security_token}
    try:
        # Fetch all posts from the post service
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{POST_SERVICE_URL}/all_posts/", headers=headers)
        response.raise_for_status()
        posts = response.json()

        # Fetch all comments once and filter them by post_id
        comments = await fetch_all_comments(f"{COMMENT_SERVICE_URL}/get_all_comments/")
        # Attach filtered comments to each post
        for post in posts:
            post_id = post.get("pid")
            if post_id is not None:
                # Filter comments for the current post
                post["comments"] = [
                    comment for comment in comments if comment["post_id"] == post_id]
        return paginate(posts)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching posts: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching posts: {e}")


@app.post("/user_post")
async def create_user_post(
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    image: UploadFile = None
):
    """
    Accept a user post with title, content, and an optional image attachment.
    """

    # Validate input
    if image and image.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=400, detail="Only JPEG or PNG images are allowed.")

    # Upload image to S3 bucket
    image_object_name = None
    if image:
        image_content = await image.read()
        files = {'image': (image.filename, io.BytesIO(
            image_content), image.content_type)}
        async with httpx.AsyncClient() as client:
            try:
                post_response = await client.post(f"{STORAGE_SERVICE_URL}/upload_image", files=files)
                image_object_name = post_response.json()['image_key']
                post_response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Failed to upload image: %s", str(exc))

    # Post Title and Content to Downstream Service
    post_payload = {"title": title,
                    "content": content,
                    "image_object_name": image_object_name,
                    }
    async with httpx.AsyncClient() as client:
        try:
            post_response = await client.post(f"{POST_SERVICE_URL}/posts/", json=post_payload)
            post_response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to post title and content: %s", str(exc))

    post_data = post_response.json()

    return {
        "message": "User post created successfully.",
        "image_object_key": image_object_name,
        "post_data": post_data
    }


add_pagination(app)
