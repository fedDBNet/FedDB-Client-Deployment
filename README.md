# FedDB Client Deployment
Deployment is currently being offered via a python script that, based on yaml file input and a given template folder, will generate a folder
containing a docker compose file, nginx config and multiple env files. Then, a simple docker
compose command can start the local database instance or the global platform components.

## Prerequisite
Deployment is done using docker compose. Therefore, [Docker](https://www.docker.com/)
and [docker compose](https://docs.docker.com/compose/) should be installed. Furthermore, a helper
script to generate the necessary env and yaml files exist. For this, 
[python3](https://www.python.org/) is required.

## Keycloak
Most images depend on KeyCloak for authorization and have authorization activated. 
There are two globally deployed KeyCloak instances that can be used for development purposes.
These are also currently used in development deployments.

If you want to setup your own KeyCloak instance [click here](https://www.keycloak.org/docs/latest/server_admin/#:~:text=Keycloak%20is%20a%20single%20sign,have%20deployed%20in%20their%20organization) is some general information about how Keycloak works.

### Deployment of the development version
You can use the python script at `deployment/deployment_helper.py`. This will based on the
template folders generate a deployment folder for you.
For configuration options, check the `deployment/deployment_helper_conf.yml` file.
