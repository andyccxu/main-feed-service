import openai
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

### Logging setup ###
import time
import logging
logger = logging.getLogger(__name__)

# * Imports the Cloud Logging client library

# Instantiates a client
client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
client.setup_logging()

# OpenAI API Key
OPENAI_API_KEY = "openai-api-key"  

### Create FastAPI application ###
app = FastAPI()
add_pagination(app)

# Add middleware for checking user scopes
SECRET_KEY = get_secret("projects/745799261495/secrets/SECURITY_MANAGER_SECRET_KEY")
REQUIRED_SCOPE = "mainfeed"

app.add_middleware(
    SecurityTokenMiddleware,
    secret_key=SECRET_KEY,
    required_scope=REQUIRED_SCOPE,
)

# Add middleware for logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    cid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    logger.info(f"cid={cid} | request started | path={request.url.path}")
    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    formatted_process_time = '{0:.2f}'.format(process_time)
    logger.info(
        f"cid={cid} | request completed in={formatted_process_time} ms | status_code={response.status_code}"
    )

    return response

# Enable CORS
origins = [
    "http://localhost",
    "http://localhost:5173",
    "https://ui-app-745799261495.us-east4.run.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get secrets
POST_SERVICE_URL = get_secret("projects/745799261495/secrets/POST_SERVICE_URL")
COMMENT_SERVICE_URL = get_secret("projects/745799261495/secrets/COMMENT_SERVICE_URL")
STORAGE_SERVICE_URL = get_secret("projects/745799261495/secrets/STORAGE_SERVICE_URL")


@app.post("/user_post")
async def create_user_post(
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    image: UploadFile = None
):
    """
    Accept a user post with title, content, and an optional image attachment.
    Perform grammar check for the post content using OpenAI API.
    """

    # Validate input
    if image and image.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=400, detail="Only JPEG or PNG images are allowed."
        )

    # Grammar check using OpenAI API
    def grammar_check(content: str) -> str:
        """
        Check and correct grammar using OpenAI's GPT model.
        Reject content if it contains unhealthy elements.

        Args:
            content (str): The original post content.

        Returns:
            str: The grammar-corrected content.
        """
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not set.")

        try:
            # Prepare the payload for OpenAI GPT API
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {
                        "role": "user",
                        "content": (
                            "Correct the grammar and spelling of this text, but keep the meaning unchanged. "
                            "Do not change anything if there's no error. If the text contains inappropriate or unhealthy content "
                            "(e.g., violence, explicit language), respond with 'Unhealthy Content Detected'.\n\n"
                            f"Text: {content}"
                        )
                    },
                ],
                "max_tokens": 500,
                "temperature": 0.5,
            }

            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }

            # Send the request to OpenAI API
            with httpx.Client() as client:
                response = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            # Validate the response structure
            choices = result.get("choices")
            if not choices or "message" not in choices[0]:
                raise ValueError("Invalid response structure from OpenAI API.")

            # Extract corrected content
            corrected_content = choices[0]["message"]["content"].strip()

            # If unhealthy content is detected, raise an error
            if "Unhealthy Content Detected" in corrected_content:
                raise HTTPException(
                    status_code=400,
                    detail="The post contains unhealthy or inappropriate content."
                )
            return corrected_content

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during grammar check: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=500, detail="Error occurred while checking grammar."
            )
        except Exception as e:
            logger.error(f"Unexpected error during grammar check: {str(e)}")
            raise HTTPException(
                status_code=500, detail="An unexpected error occurred while checking grammar."
            )

    # Perform grammar check
    corrected_content = grammar_check(content)

    # Upload image to S3 bucket if provided
    image_object_name = None
    if image:
        image_content = await image.read()
        files = {'image': (image.filename, io.BytesIO(image_content), image.content_type)}
        async with httpx.AsyncClient() as client:
            try:
                post_response = await client.post(f"{STORAGE_SERVICE_URL}/upload_image", files=files)
                post_response.raise_for_status()
                image_object_name = post_response.json()['image_key']
            except httpx.HTTPError as exc:
                logger.error(f"Failed to upload image: {str(exc)}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to upload the image to the storage service."
                )

    # Post Title and Corrected Content to Downstream Service
    post_payload = {
        "title": title,
        "content": corrected_content,
        "image_object_name": image_object_name,
    }
    async with httpx.AsyncClient() as client:
        try:
            post_response = await client.post(f"{POST_SERVICE_URL}/posts/", json=post_payload)
            post_response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(f"Failed to post title and content: {str(exc)}")
            raise HTTPException(
                status_code=500, detail="Failed to save the post to the downstream service."
            )

    post_data = post_response.json()

    return {
        "message": "User post created successfully.",
        "image_object_key": image_object_name,
        "post_data": post_data,
        "corrected_content": corrected_content
    }
