from fastapi import FastAPI, HTTPException
from fastapi_pagination import add_pagination, paginate, Page
import httpx
app = FastAPI()

POST_SERVICE_URL = "https://post-service-image-2-745799261495.us-east4.run.app/all_posts/"
COMMENT_SERVICE_URL = "https://comment-service-url.com/get_comments/"

@app.get("/")
async def root():
    return {"message": "Welcome to the main feed service!"}

async def fetch_all_comments():
    #Fetch all comments from the comment service.
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(COMMENT_SERVICE_URL)
        response.raise_for_status()
        comments = response.json()
        # Ensure required fields are included
        return [
            {
                "id": comment["id"],
                "post_id": comment["post_id"],
                "writer_uni": comment["writer_uni"],
                "likes": comment["likes"]
            }
            for comment in comments
        ]
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Error fetching comments.")
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred while fetching comments.")

@app.get("/main_feed", response_model=Page[dict])
async def main_feed():
    try:
        # Fetch all posts from the post service
        async with httpx.AsyncClient() as client:
            response = await client.get(POST_SERVICE_URL)
        response.raise_for_status()
        posts = response.json()
        # Fetch all comments once and filter them  by post_id
        comments = await fetch_all_comments()
        # Attach filtered comments to each post
        for post in posts:
            post_id = post.get("pid")
            if post_id is not None:
                # Filter comments for the current post
                post["comments"] = [comment for comment in comments if comment["post_id"] == post_id]
        return paginate(posts)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Error fetching posts.")
    except Exception:
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# Apply pagination to FastAPI app
add_pagination(app)
