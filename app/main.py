from fastapi import FastAPI, HTTPException
from fastapi_pagination import add_pagination, paginate, Page
from fastapi_pagination.paginator import paginate
import httpx
import asyncio
app = FastAPI()

POST_SERVICE_URL = "https://post-service-image-2-745799261495.us-east4.run.app/all_posts/"
COMMENT_SERVICE_URL = "https://comment-service-url.com/get_comments/"
@app.get("/")
async def root():
    return {"message": "Welcome to the main feed service!"}

async def fetch_comments(post_id: int):
    #Fetch comments
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{COMMENT_SERVICE_URL}?post_id={post_id}")
        response.raise_for_status()
        comments = response.json()
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
        # Paginate the list of posts using `paginate`
        posts = response.json()
        # Fetch comments asynchronously for each post
        tasks = []
        for post in posts:
            post_id = post.get("pid")
            if post_id is not None:
                tasks.append(fetch_comments(post_id))

            # Gather all comments for posts
        comments_data = await asyncio.gather(*tasks)

            # Combine posts with their comments
        for post, comments in zip(posts, comments_data):
            post["comments"] = comments
        return paginate(posts)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail="Error fetching posts.")
    except Exception:
        raise HTTPException(status_code=500,
                            detail="An unexpected error occurred.")


# Apply pagination to the entire FastAPI app
add_pagination(app)
