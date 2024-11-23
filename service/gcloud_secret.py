from google.cloud import secretmanager


def get_secret(resource_id: str) -> str:
    """
    Retrieve a secret from Google Secret Manager.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"{resource_id}/versions/latest"

    response = client.access_secret_version(request={"name": name})
    secret_payload = response.payload.data.decode("UTF-8")

    return secret_payload
