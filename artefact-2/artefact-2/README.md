This project consists of five (5) microservices:

- A studygroup service,
- a studysession service,
- a todo service,
- a user service
- and a user interface service.

and as a secret 6th service it downloads an image of postgres from the docker repository as well.

When started through docker-compose all 6 services should run independendly of each other,
but communicate through http API calls.

To run the application, simply use the command "docker-compose up --build"
