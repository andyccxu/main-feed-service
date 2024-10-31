# W4153 Main Feed Service

This service provides an endpoint for querying content for the main feed of our Columbia Forum app. 
This is a composite service that uses two downstream services (comments and posts).


## Deployment

This service is deployed using `gcloud run deploy --source .` and the service URL is 

```
https://main-feed-service-nr6j26ghda-uk.a.run.app
```
