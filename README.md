# W4153 Main Feed Service

This composite service provides endpoints for the UI app to interact with our downstream services and display its main feed page.

Please check out the OpenAPI documentation [here](https://main-feed-service-745799261495.us-east4.run.app/docs).


To run this service locally, use

```shell
uvicorn main:app --reload 
```

## Deployment

The deployed gateway URL is 

```
https://gw21-9im5mh4n.uk.gateway.dev
```

You can access all the endpoints in this service by visiting this API gateway and providing the required token.
Please see `test_GW_Auth.ipynb` notebook on how to generate a token and visit this service.

Update: `test_GW_Auth.ipynb` shows how to get a Google id token to pass the authentication of the gateway. However, we have added our own JWT token for authorization in the `X-Security-Token` header. So visiting main-feed service endpoints without this header will lead to an error.
