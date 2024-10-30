from fastapi import FastAPI, HTTPException
from fastapi_pagination import add_pagination, paginate, Page
import httpx
app = FastAPI()

POST_SERVICE_URL = "https://post-service-image-2-745799261495.us-east4.run.app/all_posts/"
COMMENT_SERVICE_URL = "http://3.236.180.227:8000/comments/get_all_comments/"

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
        print(f"HTTP error fetching comments: {e}")  # Log HTTP error
        raise HTTPException(status_code=e.response.status_code, detail="Error fetching comments.")
    except Exception as e:
        print(f"Unexpected error fetching comments: {e}")  # Log unexpected error
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
        print(f"HTTP error fetching posts: {e}")
        raise HTTPException(status_code=e.response.status_code, detail="Error fetching posts.")
    except Exception as e:
        print(f"Unexpected error fetching posts: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


add_pagination(app)

