# The base image for python. There are countless official images.
# Alpine just sounded cool.
#
FROM python:3.12-alpine


# Look in the code. This is an environment variable
# passed to the application.
#
ENV WHEREAMI=DOCKER

ENV PORT 8080

# The directory in the container where the app will run.
#
WORKDIR /app

# Copy the requirements.txt file from the project directory into the working
# directory and install the requirements.
#
COPY ./requirements.txt /app
RUN pip install -r requirements.txt

# Copy over the files.
#
COPY . .

# Expose/publish port 5002 for the container.
#
EXPOSE ${PORT}

# As an example here we're running the web service with one worker on uvicorn.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
# test locally
# uvicorn main:app --reload
