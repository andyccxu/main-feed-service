from fastapi import FastAPI, HTTPException
from fastapi_pagination import add_pagination, paginate, Page
from fastapi_pagination.paginator import paginate
import httpx

app = FastAPI()

POST_SERVICE_URL = "http://localhost:8000/all_posts/"


@app.get("/main_feed", response_model=Page[dict])
async def main_feed():
    try:
        # Fetch all posts from the post service
        async with httpx.AsyncClient() as client:
            response = await client.get(POST_SERVICE_URL)
        response.raise_for_status()

        # Paginate the list of posts using `paginate`
        posts = response.json()
        return paginate(posts)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail="Error fetching posts.")
    except Exception:
        raise HTTPException(status_code=500,
                            detail="An unexpected error occurred.")


# Apply pagination to the entire FastAPI app
add_pagination(app)
