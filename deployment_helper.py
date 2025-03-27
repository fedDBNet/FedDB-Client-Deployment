'''
This is used to create a folder that can be used for easy deployment via docker of the
fedDB project. It can be used for the local db instance as well as for the global platform.

The script will:
1. read in the config via config file or interactively
2. use that to set a dictionary for the enviroment variables and one for placeholders
3. check the corresponding template folder, copies the files into the requested
    destination folder and replaces the placeholders with the values from the dict.
    if the placeholder is of the form $$<placeholder>:+<replacement_value>$$, then the whole string
    between the $$ will be replaced with a blank string if the value is false and with
    the replacement_value if the value is true.
4. will create an env file with the env vars from the dict and dump it into the destination folder
'''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# standard lib, all good
from typing import Dict, Any, Tuple
import re
import os
import shutil
import argparse

# pesky third party lib, why the fuck is there no yaml support in the stdlib :(
try:
    import yaml
except ImportError:
    print("You don't seem to have the yaml library installed. Please run:\npip install pyyaml")
    exit()

def interactive_mode(mode) -> Dict[Any, Any]:
    """
    Receive the configuration parameters interactively.
    First ask for an conf file path, if not available ask for the parameters.
    """
    raise NotImplementedError("Interactive mode is not implemented yet.")

def get_conf(mode: str) -> Dict[Any, Any]:
    """
    Get the configuration parameters neccessary for the deployment.
    """
    if os.path.exists('deployment_helper_conf.yml'):
        use_conf = input('A configuration file already exists. Do you want to use it? (y/n): ')
        if use_conf.lower() == 'y':
            with open('deployment_helper_conf.yml', 'r') as f:
                conf = yaml.safe_load(f)
                if mode not in conf:
                    raise ValueError(f'The configuration for mode {mode} is missing.')
                return conf[mode]

    print('Interactive mode:')
    conf = interactive_mode(mode)
    return conf

def map_conf_to_env_placeholders(conf: Dict[Any, Any], mode:str) -> Tuple[Dict[Any, Any], Dict[Any, Any], str]:
    """
    Map the configuration parameters given as input to this script to the bigger set of env
    variables and placeholders that are used for the deployment. Then uses depending on the mode
    the specific mapping function to further continue this process
    """
    host_ip_to_listen_on = '0.0.0.0'
    host_ip_from_container = 'host.docker.internal'
    domain = conf['domain']
    if 'http' == domain[:4] or 'ws' == domain[:2] or '/' in domain:
        raise ValueError(f'The domain {domain} is not valid. Only the domain please, no protocol or path.')
    destination_folder = conf['resultfolder']
    if mode == 'local':
        env_vars, placeholders = local_map_conf_to_env_placeholders(conf, host_ip_to_listen_on, host_ip_from_container, domain)
    elif mode == 'platform':
        env_vars, placeholders = platform_map_conf_to_env_placeholders(conf, host_ip_to_listen_on, host_ip_from_container, domain)
    else:
        raise ValueError(f'The mode {mode} is not known.')

    # extra host is only needed on linux
    if os.name == 'posix':
        if mode == 'local':
            env_vars['FEDDB_EXTRA_HOST'] = 'host.docker.internal:host-gateway'
        else:
            env_vars['FEDDB_PLATFORM_EXTRA_HOST'] = 'host.docker.internal:host-gateway'
    # same for both modes
    env_vars['COMPOSE_PROJECT_NAME'] = domain
    return env_vars, placeholders, destination_folder


def platform_map_conf_to_env_placeholders(conf: Dict[Any, Any],
                                          host_ip_to_listen_on: str,
                                          host_ip_from_container: str,
                                          domain: str) -> Tuple[Dict[Any, Any], Dict[Any, Any]]:
    """
    Map the configuration parameters given as input to this script to the bigger set of env
    variables and placeholders that are used for the global platform deployment.

    Input:
        - conf: The configuration parameters given as input to this script.
    Output: (env_vars, placeholders, destination_folder)
        - env_vars: The environment variables that need to be set.
          Key is the name of the env var and value is the value.
        - placeholders: The placeholders that need to be replaced in the deployment files.
          Key is the placeholder and value is the value to replace the placeholder with.
        - destination_folder: The name of the folder that should be created for the deployment.
    """
    env_mapping = {}
    placeholder_mapping = {}
    placeholder_mapping["$$GLOBAL_DOMAIN_NO_PROTOCOL$$"] = domain
    env_mapping['FEDDB_GLOBAL_DOMAIN'] = domain

    # ports related settings
    # default settings
    placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_LEARNING_API_USE_ENV_PORTS$$'] = False
    placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_LEARNING_DB_USE_ENV_PORTS$$'] = False
    placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_DATAMODELER_API_USE_ENV_PORTS$$'] = False
    placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_FRONTEND_USE_ENV_PORTS$$'] = False
    ## global learning api
    global_learning_internal_port = 8080
    env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_INTERNAL_PORT'] = global_learning_internal_port
    placeholder_mapping["$$FEDDB_PLATFORM_GLOBAL_LEARNING_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
        f"global-learning-management-api:{global_learning_internal_port}"
    env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = \
        f"global-learning-management-api:{global_learning_internal_port}"
    ## global learning db
    global_learning_db_internal_port = 3306
    env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_DB_INTERNAL_PORT'] = global_learning_db_internal_port
    ## global datamodeler api
    global_datamodeler_internal_port = 8000
    env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_INTERNAL_PORT'] = global_datamodeler_internal_port
    placeholder_mapping["$$FEDDB_PLATFORM_GLOBAL_DATAMODELER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
        f"global-datamodeler-api:{global_datamodeler_internal_port}"
    env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = \
        f"global-datamodeler-api:{global_datamodeler_internal_port}"
    ## global datamodeler db
    global_datamodeler_db_internal_port_http = 7474
    global_datamodeler_db_internal_port_bolt = 7687
    env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_DB_INTERNAL_PORT_HTTP'] = global_datamodeler_db_internal_port_http
    env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_DB_INTERNAL_PORT_BOLT'] = global_datamodeler_db_internal_port_bolt
    # doesnt need exposed service, has hardcoded internal connection
    ## global frontend
    global_frontend_internal_port = 80
    env_mapping['FEDDB_PLATFORM_GLOBAL_FRONTEND_INTERNAL_PORT'] = global_frontend_internal_port
    placeholder_mapping["$$FEDDB_PLATFORM_GLOBAL_FRONTEND_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
        f"global-frontend:{global_frontend_internal_port}"
    env_mapping['FEDDB_PLATFORM_GLOBAL_FRONTEND_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = \
        f"global-frontend:{global_frontend_internal_port}"

    if 'expose-services' in conf:
        # global learning api
        if 'global-learning-api-external-port' in conf['expose-services']:
            global_learning_external_port = conf['expose-services']['global-learning-api-external-port']
            env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_EXTERNAL_PORT'] = global_learning_external_port
            env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = \
                f'{host_ip_from_container}:{global_learning_external_port}'
            placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_LEARNING_API_USE_ENV_PORTS$$'] = True
            placeholder_mapping["$$FEDDB_PLATFORM_GLOBAL_LEARNING_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"{host_ip_from_container}:{global_learning_external_port}"

        # global learning db
        if 'global-learning-db-external-port' in conf['expose-services']:
            global_learning_db_external_port = conf['expose-services']['global-learning-db-external-port']
            env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_DB_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_PLATFORM_GLOBAL_LEARNING_DB_EXTERNAL_PORT'] = global_learning_db_external_port
            placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_LEARNING_DB_USE_ENV_PORTS$$'] = True
            # other services should still use the internal network connection

        # global datamodeler api
        if 'global-datamodeler-external-port' in conf['expose-services']:
            global_datamodeler_external_port = conf['expose-services']['global-datamodeler-external-port']
            env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_EXTERNAL_PORT'] = global_datamodeler_external_port
            env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = \
                f'{host_ip_from_container}:{global_datamodeler_external_port}'
            placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_DATAMODELER_API_USE_ENV_PORTS$$'] = True
            placeholder_mapping["$$FEDDB_PLATFORM_GLOBAL_DATAMODELER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"{host_ip_from_container}:{global_datamodeler_external_port}"

        # global datamodeler db
        if 'global-datamodeler-db-external-port-http' in conf['expose-services'] or \
            'global-datamodeler-db-external-port-bolt' in conf['expose-services']:
            try:
                global_datamodeler_db_external_port_http = conf['expose-services']['global-datamodeler-db-external-port-http']
                global_datamodeler_db_external_port_bolt = conf['expose-services']['global-datamodeler-db-external-port-bolt']
            except KeyError:
                raise ValueError("Both external ports for the global datamodeler db need to be provided. (bolt and http)")

            env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_DB_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_DB_EXTERNAL_PORT_HTTP'] = global_datamodeler_db_external_port_http
            env_mapping['FEDDB_PLATFORM_GLOBAL_DATAMODELER_DB_EXTERNAL_PORT_BOLT'] = global_datamodeler_db_external_port_bolt
            placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_DATAMODELER_DB_USE_ENV_PORTS$$'] = True
            # other services should still use the internal network connection

        # global frontend
        if 'global-frontend-external-port' in conf['expose-services']:
            global_frontend_external_port = conf['expose-services']['global-frontend-external-port']
            env_mapping['FEDDB_PLATFORM_GLOBAL_FRONTEND_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_PLATFORM_GLOBAL_FRONTEND_EXTERNAL_PORT'] = global_frontend_external_port
            placeholder_mapping['$$FEDDB_PLATFORM_GLOBAL_FRONTEND_USE_ENV_PORTS$$'] = True
            placeholder_mapping["$$FEDDB_PLATFORM_GLOBAL_FRONTEND_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"{host_ip_from_container}:{global_frontend_external_port}"

    if 'use-internal-nginx' in conf:
        nginx_internal_port = 80
        nginx_external_port = conf['use-internal-nginx']['nginx-external-port']
        env_mapping['COMPOSE_PROFILES'] = 'use-internal-nginx'
        env_mapping['FEDDB_PLATFORM_MAIN_ACCESS_ADDRESS'] = host_ip_to_listen_on
        env_mapping['FEDDB_PLATFORM_MAIN_ACCESS_PORT'] = nginx_external_port
        env_mapping['FEDDB_PLATFORM_NGINX_INTERNAL_PORT'] = nginx_internal_port
        placeholder_mapping["$$FEDDB_PLATFORM_NGINX_INTERNAL_PORT$$"] = nginx_internal_port

    # set the other vars
    env_mapping['FEDDB_PLATFORM_FRONTEND_IMAGE'] = conf['frontend-image']
    env_mapping['GLOBAL_KEYCLOAK_URL'] = conf['keycloak-address']
    env_mapping['FEDDB_GLOBAL_ADDRESS'] = domain
    env_mapping['FEDDB_GLOBAL_NETWORK_NAME'] = f'{domain}-platform-net'
    env_mapping['FEDDB_GLOBAL_IMAGE_TAG'] = conf['image-tag']
    env_mapping['FEDDB_PLATFORM_WATCHTOWER_LABEL'] = "com.centurylinklabs.watchtower.enable=true"

    return env_mapping, placeholder_mapping


def local_map_conf_to_env_placeholders(conf: Dict[Any, Any],
                                       host_ip_to_listen_on: str,
                                       host_ip: str,
                                       domain: str) -> Tuple[Dict[Any, Any], Dict[Any, Any]]:
    """
    Map the configuration parameters given as input to this script to the bigger set of env
    variables and placeholders that are used for the local database instance deployment.

    Input:
        - conf: The configuration parameters given as input to this script.
        - host_ip_to_listen_on: The ip address that should be used for the local host.
        - host_ip: The ip address that should be used for listening on the host. Should be
            0.0.0.0 or other services can't connect to the services.
        - domain: The domain that should be used for the deployment.
    Output: (env_vars, placeholders, destination_folder)
        - env_vars: The environment variables that need to be set.
          Key is the name of the env var and value is the value.
        - placeholders: The placeholders that need to be replaced in the deployment files.
          Key is the placeholder and value is the value to replace the placeholder with.
    """
    env_mapping = {}
    placeholder_mapping = {}

    placeholder_mapping['$$LOCAL_DOMAIN_NO_PROTOCOL$$'] = domain
    env_mapping['FEDDB_MAIN_ACCESS_PORT'] = 443 # default HTTPS port

    # ports related things
    # default settings
    placeholder_mapping['$$FEDDB_FRONTEND_USE_ENV_PORTS$$'] = False
    placeholder_mapping['$$FEDDB_DATA_IMPORTER_USE_ENV_PORTS$$'] = False
    placeholder_mapping['$$FEDDB_HARMONIZED_API_USE_ENV_PORTS$$'] = False
    placeholder_mapping['$$FEDDB_META_API_USE_ENV_PORTS$$'] = False
    placeholder_mapping['$$FEDDB_META_API_DB_USE_ENV_PORTS$$'] = False
    ## frontend
    frontend_internal_port = 80
    placeholder_mapping["$$FEDDB_FRONTEND_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"instance-manager-frontend:{frontend_internal_port}"
    env_mapping['FEDDB_FRONTEND_INTERNAL_PORT'] = frontend_internal_port
    env_mapping['FEDDB_FRONTEND_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f"instance-manager-frontend:{frontend_internal_port}"
    ## data importer
    dataimporter_internal_port = 8000
    placeholder_mapping["$$FEDDB_DATAIMPORTER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"dataimporter-api:{dataimporter_internal_port}"
    env_mapping['FEDDB_DATAIMPORTER_INTERNAL_PORT'] = dataimporter_internal_port
    env_mapping['FEDDB_DATAIMPORTER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f"dataimporter-api:{dataimporter_internal_port}"
    ## harmonized-api
    harmonizer_internal_port = 8000
    placeholder_mapping["$$FEDDB_HARMONIZED_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"harmonized-api:{harmonizer_internal_port}"
    env_mapping['FEDDB_HARMONIZED_API_INTERNAL_PORT'] = harmonizer_internal_port
    env_mapping['FEDDB_HARMONIZED_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f"harmonized-api:{harmonizer_internal_port}"
    ## meta-api
    meta_api_internal_port = 8000
    placeholder_mapping["$$FEDDB_META_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"client-meta-api:{meta_api_internal_port}"
    env_mapping['FEDDB_META_API_INTERNAL_PORT'] = meta_api_internal_port
    env_mapping['FEDDB_META_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f"client-meta-api:{meta_api_internal_port}"
    ## meta-api-db
    meta_api_db_internal_port = 3306
    env_mapping['FEDDB_META_API_DB_INTERNAL_PORT'] = meta_api_db_internal_port
    env_mapping['FEDDB_META_API_DB_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f"client-meta-api-db:{meta_api_db_internal_port}"

    ## expose services if wanted
    if 'expose-services' in conf:
        # frontend
        if 'frontend-external-port' in conf['expose-services']:
            frontend_external_port = conf['expose-services']['frontend-external-port']
            env_mapping['FEDDB_FRONTEND_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_FRONTEND_EXTERNAL_PORT'] = frontend_external_port
            env_mapping['FEDDB_FRONTEND_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f'{host_ip}:{frontend_external_port}'
            placeholder_mapping['$$FEDDB_FRONTEND_USE_ENV_PORTS$$'] = True
            placeholder_mapping["$$FEDDB_FRONTEND_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"{host_ip}:{frontend_external_port}"

        # data importer
        if 'dataimporter-external-port' in conf['expose-services']:
            dataimporter_external_port = conf['expose-services']['dataimporter-external-port']
            env_mapping['FEDDB_DATAIMPORTER_EXPOSED_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_DATAIMPORTER_EXTERNAL_PORT'] = dataimporter_external_port
            env_mapping['FEDDB_DATAIMPORTER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f'{host_ip}:{dataimporter_external_port}'
            placeholder_mapping['$$FEDDB_DATA_IMPORTER_USE_ENV_PORTS$$'] = True
            placeholder_mapping["$$FEDDB_DATAIMPORTER_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"{host_ip}:{dataimporter_external_port}"

        # harmonized-api
        if 'harmonizer-external-port' in conf['expose-services']:
            harmonizer_external_port = conf['expose-services']['harmonizer-external-port']
            env_mapping['FEDDB_HARMONIZED_API_EXPOSED_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_HARMONIZED_API_EXTERNAL_PORT'] = harmonizer_external_port
            env_mapping['FEDDB_HARMONIZED_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f'{host_ip}:{harmonizer_external_port}'
            placeholder_mapping['$$FEDDB_HARMONIZED_API_USE_ENV_PORTS$$'] = True
            placeholder_mapping["$$FEDDB_HARMONIZED_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"{host_ip}:{harmonizer_external_port}"

        # meta-api
        if 'meta-api-external-port' in conf['expose-services']:
            meta_api_external_port = conf['expose-services']['meta-api-external-port']
            env_mapping['FEDDB_META_API_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_META_API_EXTERNAL_PORT'] = meta_api_external_port
            env_mapping['FEDDB_META_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES'] = f'{host_ip}:{meta_api_external_port}'
            placeholder_mapping['$$FEDDB_META_API_USE_ENV_PORTS$$'] = True
            placeholder_mapping["$$FEDDB_META_API_EXPOSED_ADDRESS_FOR_OTHER_SERVICES$$"] = \
                f"{host_ip}:{meta_api_external_port}"

        # meta-api-db
        # this doesn't need to be able to be provided from the outside
        # therefor there is no need for other services to know the address
        # this is why there is no placeholder EXPORSED_ADDRESS_FOR_OTHER_SERVICES
        if 'meta-api-db-external-port' in conf['expose-services']:
            meta_api_db_external_port = conf['expose-services']['meta-api-db-external-port']
            env_mapping['FEDDB_META_API_DB_ADDRESS'] = host_ip_to_listen_on
            env_mapping['FEDDB_META_API_DB_EXTERNAL_PORT'] = meta_api_db_external_port
            placeholder_mapping['$$FEDDB_META_API_DB_USE_ENV_PORTS$$'] = True


    if 'use-internal-nginx' in conf:
        nginx_internal_port = 80
        nginx_external_port = conf['use-internal-nginx']['nginx-external-port']
        env_mapping['COMPOSE_PROFILES'] = 'use-internal-nginx'
        env_mapping['FEDDB_MAIN_ACCESS_ADDRESS'] = host_ip_to_listen_on
        env_mapping['FEDDB_MAIN_ACCESS_PORT'] = nginx_external_port
        env_mapping['FEDDB_NGINX_INTERNAL_PORT'] = nginx_internal_port
        placeholder_mapping['$$FEDDB_MAIN_ACCESS_PORT$$'] = nginx_external_port
        placeholder_mapping["$$FEDDB_NGINX_INTERNAL_PORT$$"] = nginx_internal_port

    # set the other vars
    env_mapping['FEDDB_FRONTEND_IMAGE'] = conf['frontend-image']
    env_mapping['FEDDB_LOCAL_KEYCLOAK_URL'] = conf['keycloak-address']
    env_mapping['FEDDB_NETWORK_NAME'] = f'{domain}-local-net'
    env_mapping['FEDDB_IMAGE_TAG'] = conf['image-tag']
    env_mapping['FEDDB_WATCHTOWER_LABEL'] = "com.centurylinklabs.watchtower.enable=true"
    env_mapping['FEDDB_GLOBAL_ADDRESS'] = conf['global-address']

    return env_mapping, placeholder_mapping

def _copy_file_with_replacements(source_path: str, destination_path: str, placeholders: Dict[Any, Any]) -> None:
    """
    Copy the file from source_path to destination_path and replace the placeholders in the file.
    """
    if 'example_deployment_env' in source_path:
        # we ignore the example file
        return
    content = ''
    with open(source_path, 'r') as f:
        content = f.read()
    for placeholder, value in placeholders.items():
        content = content.replace(placeholder, str(value))
        # now we also need to catch the $$<placeholder:+<replacement_value>$$ case
        placeholder_without_dollar = placeholder[2:-2]
        # regex: \$\$<placeholder>:\+<replacement_value>\$\$
        regex = re.compile(rf'\$\${placeholder_without_dollar}:\+.+\$\$')
        for match in regex.finditer(content):
            full = match.group()
            replacement = full[len(placeholder_without_dollar)+4:-2]
                # +4 because of the $$ at the beginning and the :+ after the placeholder
                # -2 because of the $$ at the end
            if value:
                # replace
                content = content.replace(full, replacement)
            else:
                # remove
                content = content.replace(full, '')

    with open(destination_path, 'w') as f:
        f.write(content)

def create_deployment_folder(env_vars: Dict[Any, Any], placeholders: Dict[Any, Any],
                             mode: str, destination_folder:str) -> str:
    """
    Create the deployment folder for the fedDB project.

    Returns the name of the folder that was created.
    """
    foldername = destination_folder
    if os.path.exists(foldername):
        remove_folder = input(f'The folder {foldername} exists. Do you want to overwrite it? (y/n): ')
        if remove_folder.lower() == 'y':
            shutil.rmtree(foldername)
        else:
            print('Exiting.')
            exit()
    template_folder = f'template-{mode}'
    if not os.path.exists(template_folder):
        raise FileNotFoundError(f'The template folder {template_folder} does not exist. Implementation error.')

    # create the folder
    os.mkdir(foldername)
    # copy the files from the template folder to the new folder (replace placeholders)
    for file in os.listdir(template_folder):
        source_path = os.path.join(template_folder, file)
        destination_path = os.path.join(foldername, file)
        if os.path.isfile(source_path):
            _copy_file_with_replacements(source_path, destination_path, placeholders)
        elif os.path.isdir(source_path):
            os.mkdir(destination_path)
            for subfile in os.listdir(source_path):
                subsource_path = os.path.join(source_path, subfile)
                subdestination_path = os.path.join(destination_path, subfile)
                _copy_file_with_replacements(subsource_path, subdestination_path, placeholders)



    # write the env file
    with open(f'{foldername}/deployment.env', 'w') as f:
        for key, value in env_vars.items():
            f.write(f'{key}={value}\n')
    return foldername


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create a deployment folder for the fedDB project.')
    parser.add_argument('mode', type=str, help='Whether to help with local db instance or global platform deployment.', choices=['local', 'platform'])
    args = parser.parse_args()
    mode = args.mode

    ### Prerequisites
    # is docker installed and running
    try:
        os.system('docker info')
    except Exception as e:
        print("Docker is not installed or not running. Please install and run docker.")
        exit()

    # is docker-compose installed
    try:
        os.system('docker compose version')
    except Exception as e:
        print("Docker compose is not installed. Please install docker-compose.")
        exit()

    # can I get an example image (global-learning-ui)
    try:
        os.system('docker pull gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/global-learning-ui/learning-api:latest')
    except Exception as e:
        print("The example image could not be pulled. Please check the connection to the gitlab registry.")
        exit()


    ### Get the configuration parameters
    conf = get_conf(mode)

    ### map from the input conf of this script to placeholders and env vars
    if mode == 'local':
        env_vars, placeholders, destination_folder = map_conf_to_env_placeholders(conf, mode=mode)
    else:
        raise ValueError(f'The mode {mode} is not known.')

    ### create the deployment folder
    foldername = create_deployment_folder(env_vars, placeholders, mode, destination_folder)
    print(f'The deployment folder {foldername} was created successfully.')
    print(f"Simply run the following commands to deploy the fedDB project:\n")
    print(f"cd {foldername}")
    print("docker compose --env-file=deployment.env up -d")
