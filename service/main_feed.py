from fastapi import HTTPException
import httpx
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_all_comments(COMMENT_SERVICE_URL):
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
                # Note: typo retained as in the original data
                "writer_uni": reply["writter_uni"],
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
                # Attach replies
                "replies": comment2_by_comment1_id.get(comment_id, [])
            })
        return structured_comments
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching comments: {e}")  # Log HTTP error
        raise HTTPException(status_code=e.response.status_code,
                            detail="Error fetching comments.")
    except Exception as e:
        logger.error(f"Unexpected error fetching comments: {
                     e}")  # Log unexpected error
        raise HTTPException(
            status_code=500, detail="An error occurred while fetching comments.")
