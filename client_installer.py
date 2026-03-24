#!/usr/bin/env python3
"""
Initializes the FLNET_CLIENT_DIR as a FLNet Client on the current machine.
Checks first for requirements, requests relevant parameters from the user and
initializes secrets.
Leaves the user with instructions on how to then start and setup their FLNet Client.
"""
import re
import secrets
import string
import sys
from pathlib import Path

BASE_DIR_INSTALLER_SCRIPT = Path(__file__).resolve().parent
FLNET_CLIENT_DIR = BASE_DIR_INSTALLER_SCRIPT / 'FLNet_client'
FLNET_CLIENT_ENV_DIR = FLNET_CLIENT_DIR / 'env'
OVERWRITE_SECRETS = False

DEFAULT_PLATFORM_ADDRESS = "federated-learning.net"
DEFAULT_PLATFORM_PROTOCOL = "https"
DEFAULT_FULL_GLOBAL_ADDRESS = f"{DEFAULT_PLATFORM_PROTOCOL}://{DEFAULT_PLATFORM_ADDRESS}"
DEFAULT_PLATFORM_TCP_PORT = "9152"
IMAGE_TAG = "latest"
GLOBAL_DOMAIN_TO_IMAGE = {
    "https://federated-learning.net": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-fl-net:{IMAGE_TAG}",
    "https://daibetes-net.cosy.bio": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-daibetes:{IMAGE_TAG}",
    "https://daibetes-net.federated-learning.net": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-daibetes:{IMAGE_TAG}",
    "https://microb-ai-net.cosy.bio": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-microbaiome:{IMAGE_TAG}",
    "https://microb-ai-net.federated-learning.net": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-microbaiome:{IMAGE_TAG}",
}
DEFAULT_FRONTEND_IMAGE = f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-fl-net:{IMAGE_TAG}"
#TODO: as soon as the docs are deployed we can also link to them in this script!

# ============================================================================
# Helper Functions
# ============================================================================
class PredefinedConfiguration:
    """
    Contains some of the variables collected in this installer.
    Each Instance of this class represents a predefined configuration
    that the user can choose at the beginning of the installer.
    Example is the predefined config for the daibetes/microbaiome projects
    """
    def __init__(self, name: str, global_domain: str, global_tcp_port: str):
        self.name = name
        self.global_domain = global_domain
        self.global_tcp_port = global_tcp_port
        self.frontend_image = GLOBAL_DOMAIN_TO_IMAGE.get(global_domain, DEFAULT_FRONTEND_IMAGE)
        if global_domain not in GLOBAL_DOMAIN_TO_IMAGE:
            print(f"Warning: No predefined frontend image for global domain '{global_domain}'. Using default image '{DEFAULT_FRONTEND_IMAGE}'.")
            print("This will most likely only concern styling")

FLNET_CONFIG = PredefinedConfiguration(
    name="FLNet",
    global_domain="https://federated-learning.net",
    global_tcp_port="9152"
)

DAIBETES_CONFIG = PredefinedConfiguration(
    name="Daibetes",
    global_domain="https://daibetes-net.federated-learning.net",
    global_tcp_port="9153"
)

MICROBAIOME_CONFIG = PredefinedConfiguration(
    name="MicrobAIome",
    global_domain="https://microb-ai-net.federated-learning.net",
    global_tcp_port="9154"
)

def gen_secret(length: int = 64) -> str:
    """
    Generate a URL-safe random string of given length.
    Uses secrets module for cryptographic randomness.
    """
    # To make sure this works on all systems, we limit to alphanumeric characters
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def write_env_file(filepath: Path, comments: dict = None, **variables) -> bool:
    """
    Write environment variables to a file with overwrite protection.

    Args:
        filepath: Path to the .env file
        comments: Optional dict mapping variable names to comment lines prepended before that variable
        **variables: Key-value pairs to write (VAR=value format)

    Returns:
        True if successful, False if user aborted
    """
    global OVERWRITE_SECRETS
    if filepath.exists() and not OVERWRITE_SECRETS:
        print(f"Warning: The secrets file '{filepath}' already exists. Overwriting most likely breaks existing deployments. If you've already started a FLNet Client once, please be cautious.")
        confirm = input("Do you want to continue and overwrite the secrets? (y/n): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("Initialization aborted by user.")
            return False
        OVERWRITE_SECRETS = True  # Avoid multiple prompts in one run

    # Ensure parent directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write variables
    with filepath.open('w') as f:
        for key, value in variables.items():
            if comments and key in comments:
                f.write(f"# {comments[key]}\n")
            f.write(f"{key}={value}\n")

    # Set permissions to 600 (owner read/write only)
    filepath.chmod(0o600)
    return True

class Domain:
    """
    Helper class to parse and validate domain inputs.
    Requires protocol (http:// or https://) to be specified.
    Parses protocol, domain name and optional port.
    Expects input in the format: protocol://domain[:port], e.g. 'https://example.com:8080'
    """
    def __init__(self, domain_input: str):
        self._raw_input = domain_input.strip()
        self._protocol = None
        self._domain_name = None
        self._port = None
        self._protocol_is_valid = False
        self._domain_is_valid = False
        self._port_is_valid = True  # default to true if no port specified
        self._parse()

    def _parse(self):
        """Parse the domain input into protocol, domain, and port."""
        domain_input = self._raw_input

        # Protocol is required
        if "://" not in domain_input:
            self._protocol_is_valid = False
            return

        # Extract protocol
        protocol_part, domain_port = domain_input.split("://", 1)
        self._protocol = protocol_part.lower()

        # Validate protocol
        if self._protocol not in ('http', 'https'):
            self._protocol_is_valid = False
            return
        self._protocol_is_valid = True

        # Clean trailing slash
        if domain_port.endswith('/'):
            domain_port = domain_port[:-1]

        # Extract domain and port (if present)
        if ':' in domain_port:
            domain_name, port = domain_port.split(':', 1)
            self._domain_name = domain_name.strip()
            self._port = port.strip()
            if not validate_port(self._port):
                self._port_is_valid = False
                return
        else:
            self._domain_name = domain_port.strip()
            self._port = "80" if self._protocol == 'http' else "443"
            self._port_is_valid = True

        # Validate domain
        if len(self._domain_name) > 253:  # Full domain max length
            self._domain_is_valid = False
            return
        if not re.match(r'^[a-zA-Z0-9.-]+$', self._domain_name):
            self._domain_is_valid = False
            return
        if re.match(r'^[-.]|[-.]$', self._domain_name):
            self._domain_is_valid = False
            return
        if '--' in self._domain_name or '..' in self._domain_name:
            self._domain_is_valid = False
            return

        self._domain_is_valid = True

    def protocol(self) -> str | None:
        """Return the protocol (http or https)."""
        return self._protocol

    def domain_name(self) -> str | None:
        """Return the domain name without protocol or port."""
        return self._domain_name

    def port(self) -> str | None:
        """Return the port as string, or None if not specified."""
        return self._port

    def protocol_is_valid(self) -> bool:
        """Check if protocol is valid (http: or https:)."""
        return self._protocol_is_valid

    def domain_is_valid(self) -> bool:
        """Check if domain name is valid."""
        return self._domain_is_valid

    def port_is_valid(self) -> bool:
        """Check if port is valid (1-65535)."""
        return self._port_is_valid

    def is_valid(self) -> bool:
        """Check if the entire domain input is valid."""
        return self._protocol_is_valid and self._domain_is_valid and self._port_is_valid

    def is_default_port(self) -> bool:
        """Check if the port is the default for the protocol."""
        if not self.is_valid():
            return False
        if self._protocol == 'http' and self._port == "80":
            return True
        if self._protocol == 'https' and self._port == "443":
            return True
        return False

    def __str__(self) -> str:
        """Return the full domain string with protocol and port."""
        if not self.is_valid():
            return self._raw_input

        if self._port is None:
            self._port = "80" if self._protocol == 'http' else "443"

        # Only show port if it's non-standard
        default_port = "443" if self._protocol == 'https' else "80"
        result = f"{self._protocol}://{self._domain_name}"
        if self._port != default_port:
            result += f":{self._port}"

        return result

def patch_nginx_server_name(nginx_conf_path: Path, server_name: str) -> None:
    """
    Replace the server_name directive in the main server block of nginx.conf.
    Uses the first server_name occurrence (the main block precedes the catch-all).
    Works both for the initial placeholder (${NGINX_HOST}) and on re-runs where
    a real domain is already present.
    """
    content = nginx_conf_path.read_text()
    # Check if the pattern exists before attempting substitution
    pattern = r'^(\s*server_name\s+).*?;\s*$'
    if not re.search(pattern, content, flags=re.MULTILINE):
        print(f"Warning: Could not find server_name directive in '{nginx_conf_path}'. nginx may not use the correct hostname.")
        return
    
    new_content = re.sub(
        pattern,
        rf'\g<1>{server_name};',
        content,
        count=1,
        flags=re.MULTILINE
    )
    nginx_conf_path.write_text(new_content)


def validate_port(port_str: str) -> bool:
    """Validate that port is a number between 1 and 65535."""
    try:
        port = int(port_str)
        return 1 <= port <= 65535
    except ValueError:
        return False

def validate_ip_address(ip: str) -> bool:
    """Validate IPv4 address format."""
    pattern = re.compile(r'^(((?!25?[6-9])[12]\d|[1-9])?\d\.?\b){4}$')
        # https://stackoverflow.com/questions/5284147/validating-ipv4-addresses-with-regexp
        # smelly nerds and their smelly regexes
    if not pattern.match(ip):
        return False
    parts = ip.split('.')
    for part in parts:
        if not 0 <= int(part) <= 255:
            return False
    return True

# ============================================================================
# Main Installation Logic
# ============================================================================

def main():
    """Main installation/initialization workflow."""
    print("Starting the initialization of a FLNet Client...\n")
    # All variables that will be set
    exposed_address = None
    exposed_ip_address = None
    client_port = None
    domain_obj = None
    enable_ssl_termination_in_client = False
    ssl_folder = None
    ssl_path = None
    fullchain_file = None
    privkey_file = None
    global_domain_obj = None
    global_tcp_port = None
    # ========================================================================
    # 0. Preconfiguration: Ask if user wants to use an already defined
    # configuration or do a fresh setup.
    # vars: global_domain_obj, global_tcp_port (indirectly frontend image)
    # ========================================================================
    print("An FLNet Client is part of a network allowing privacy preserving federated learning across multiple organizations.")
    print("Do you want to join a preexisting network?")
    while True:
        input_predefined_config = input("Enter the name of the network you want to join (flnet, daibetes, microbaiome) or enter own to join your own deployed network: ").strip()
        normalized_input = input_predefined_config.lower()
        if normalized_input not in ("flnet", "daibetes", "microbaiome", "own"):
            print("Invalid input. Please enter 'flnet', 'daibetes', 'microbaiome' or 'own'.")
            continue # continue getting input until valid
        if normalized_input == "own":
            print("Proceeding with custom configuration. You will be asked to provide the relevant parameters in the next steps.")
            break # own config
        else:
            for config in (FLNET_CONFIG, DAIBETES_CONFIG, MICROBAIOME_CONFIG):
                if normalized_input == config.name.lower():
                    global_domain_obj = Domain(config.global_domain)
                    global_tcp_port = config.global_tcp_port
                    print(f"Joining the '{config.name}' network with global domain '{config.global_domain}' and TCP port '{config.global_tcp_port}'.")
                    print(f"The installer will use the predefined frontend image '{config.frontend_image}' for this configuration.")
                    break
            break # predefined config selected
    # ========================================================================
    # 1. Which interface to listen on?
    # vars: exposed_address, client_port
    # ========================================================================
    print("A FLNet Client is accessed via the browser.")
    print("You can either only expose the client to this machine (localhost), or expose it to the internet/intranet.")
    print("If you expose to the internet, consider limiting access to your server to only your internal network or via a VPN for security reasons.")
    print("You can also set up SSL encryption for encrypted communication later in the setup.\n")
    while True:
        exposed_address_input = input("\nPlease specify the address without port the FLNet Client should run on. We suggest to use 0.0.0.0 to open to the internet/intranet or localhost to only listen on this machine (default 127.0.0.1 if you just press Enter): ").strip().lower()
        if not exposed_address_input or exposed_address_input == "127.0.0.1":
            # translate 127.0.0.1 to localhost
            exposed_address_input = "localhost"
        if not (validate_ip_address(exposed_address_input) or exposed_address_input == "localhost"):
            print(f"The address '{exposed_address_input}' is not a valid IPv4 address.")
            continue
        exposed_address = exposed_address_input
        # Keep IP address for docker binding (docker doesn't understand 'localhost')
        exposed_ip_address = "127.0.0.1" if exposed_address == "localhost" else exposed_address
        break

    # which port?
    while True:
        if exposed_address == "localhost" or exposed_address == "127.0.0.1":
            client_port_input = input(f"Please specify the port that the FLNet Client should listen on (default is 80): ").strip()
            client_port = client_port_input or "80"
        else:
            client_port_input = input(f"Please specify the port that the FLNet Client should listen on (default is 443): ").strip()
            client_port = client_port_input or "443"
        if validate_port(client_port):
            break
        else:
            print(f"The port '{client_port}' is not valid. Please enter a number between 1 and 65535.")
    print(f"Exposing the FLNet Client to {exposed_address}:{client_port}.\n")
    print()

    # ========================================================================
    # 2. Domain configuration including SSL
    # vars: domain_name, host_port, ssl_folder, fullchain_file, privkey_file
    # ========================================================================
    # Domain Name and host port retrieval loop
    print("You can optionally set the domain you are using for your FLNet Client.")
    print("This enables us to enforce CORS policies and improve security.")
    print("We also offer to do SSL termination if you provide the relevant SSL files.")
    while True:
        domain_input = input("If you setup a domain please specify the domain here with protocol (e.g., 'https://example.com:4200', 'http://example2.com', ...), or press Enter to skip: ").strip()
        if domain_input:
            # domain given
            domain_obj = Domain(domain_input)

            if not domain_obj.protocol_is_valid():
                print("ERROR: You must specify a protocol (http:// or https://).")
                print("Examples: 'https://example.com', 'http://example.com:8080'")
                continue

            if not domain_obj.domain_is_valid():
                print(f"ERROR: The domain name is not valid.")
                continue

            if not domain_obj.port_is_valid():
                print(f"ERROR: The port '{domain_obj.port()}' is not valid. Please enter a number between 1 and 65535 or leave it empty for default ports (80 for HTTP, 443 for HTTPS).")
                continue

            # All valid
            print(f"\nUsing the following domain: {domain_obj}")
            break
        else:
            # No domain provided
            break

    # Should the Client do the SSL termination?
    while domain_input:
        enable_ssl_termination_in_client_input = \
            input("Do you want to enable SSL termination in the FLNet Client by providing SSL certificate files? (y/n): ").strip().lower()
        if enable_ssl_termination_in_client_input in ('y', 'yes'):
            enable_ssl_termination_in_client = True
            break
        elif enable_ssl_termination_in_client_input in ('n', 'no'):
            enable_ssl_termination_in_client = False
            break
        else:
            print("Please answer with 'y' or 'n'.")
            continue

    # SSL certificate files retrieval loop
    while enable_ssl_termination_in_client:
        print("Please provide the folder containing your SSL certificate files (fullchain.pem and privkey.pem).")
        ssl_folder = input("Enter the path to the folder containing fullchain.pem and privkey.pem: ").strip()
        ssl_path = Path(ssl_folder)
        if not ssl_path.is_dir():
            print(f"ERROR: The folder '{ssl_folder}' does not exist.")
            continue
        # ensure we get the absolute path
        ssl_path = ssl_path.resolve()

        fullchain_file = ssl_path / 'fullchain.pem'
        privkey_file = ssl_path / 'privkey.pem'
        if not fullchain_file.exists() or not privkey_file.exists():
            print(f"ERROR: Required files fullchain.pem and privkey.pem not found in '{ssl_folder}'.")
            continue
        # success
        print(f"SSL certificate files found in '{ssl_folder}'.")
        print("✓ SSL configuration completed.")
        print("WARNING:")
        print("  The deployment does NOT take care of certification renewal and does NOT automatically reload the certificates on renewal.")
        print("  You need to renew the certs yourself e.g. via certbot.")
        print("  To reload the renewed certificates, you need to reload the deployed nginx reverse proxy via the following command:")
        print("  docker exec <container_name_or_id> nginx -s reload")
        print("  The relevant container should be called 'FLNet-client-reverse-proxy-encrypted-1'")
        print("  If you're using certbot, you can add this command to the relevant deploy/reload hooks to automate the process!")
        input("  Press Enter to continue...")
        break

    # Final warnings for potential misconfigurations
    # Warning 0: Using a domain without SSL encryption
    if domain_obj is not None and domain_obj.protocol() != 'https':
        # HTTP protocol - warn about no encryption
        print("\nWARNING: You specified HTTP protocol. Communication will be unencrypted!")
        print("We STRONGLY advise against this!")
        confirm = input("Do you want to continue without SSL encryption? (y/n): ").strip().lower()
        if confirm in ('y', 'yes'):
            confirm2 = input("Are you sure you want to continue without SSL encryption? (y/n): ").strip().lower()
            if confirm2 in ('y', 'yes'):
                print("Continuing without SSL encryption as per user request.")
            else:
                sys.exit("Aborting setup as per user request.")
        else:
            sys.exit("Aborting setup as per user request.")

    # Warning 1: Exposed to network without SSL encryption
    if exposed_address != "localhost" and not ssl_folder:
        print("WARNING: The FLNet Client is exposed to a non localhost IP without SSL encryption.")
        print("  This means all communication (including passwords) is unencrypted and potentially insecure!")
        # with HTTPS -> User just needs to ensure SSL termination is done externally
        if domain_obj and domain_obj.protocol() == 'https':
            print(f"WARNING: You specified HTTPS for domain '{domain_obj.domain_name()}' but without SSL certificates.")
            print("We STRONGLY advise against this!")
            print("Make sure you have a reverse proxy handling SSL termination!")
            print(input("Press Enter to continue..."))
        # without HTTPS -> strongly advise to use SSL
        elif domain_obj and domain_obj.protocol() == 'http':
            print("\nWARNING: You specified HTTP protocol. Communication will be unencrypted!")
            print("We STRONGLY advise against this!")
            confirm = input("Do you want to continue without SSL encryption? (y/n): ").strip().lower()
            if confirm in ('y', 'yes'):
                confirm2 = input("Are you sure you want to continue without SSL encryption? (y/n): ").strip().lower()
                if confirm2 in ('y', 'yes'):
                    print("Continuing without SSL encryption as per user request.")
                else:
                    sys.exit("Aborting setup as per user request.")
            else:
                sys.exit("Aborting setup as per user request.")
        print()

    # Warning 2: Domain provided without SSL certificates
    if domain_obj is not None and domain_obj.protocol() == 'https' and not ssl_folder:
        print("WARNING: You specified HTTPS protocol but did not provide SSL certificates.")
        print("  Without SSL certificates, the client cannot serve HTTPS traffic directly.")
        print("  You MUST use an external reverse proxy (e.g., nginx, Caddy) to handle SSL termination.")
        print("  Make sure to forward traffic from port 443 to the FLNet Client and handle SSL termination in the reverse proxy.")
        print("  Furthermore make sure to preserve the Host header ($host) in the reverse proxy or the FLNet Client will not work properly!")
        input("Press Enter to continue...")
        print()

    # Warning 3: Domain with localhost exposure
    if domain_obj is not None and exposed_address == "localhost":
        print("WARNING: You specified a domain name, but the FLNet Client is only listening on localhost.")
        print(f"  Make sure you have a reverse proxy forwarding traffic from {str(domain_obj)} to localhost:{client_port} or use a reverse tunnel.")
        if ssl_folder:
            print("  Additionally, you configured SSL certificates for localhost-only access.")
            print("  This is unusual - SSL is typically not needed for localhost. Consider having your")
            print("  reverse proxy handle SSL termination instead. You can abort via Ctrl+C and re-run the installer without SSL.")
        input("Press Enter to continue...")
        print()



    # Warning 4: Port mismatch between domain and client
    if domain_obj is not None:
        if domain_obj.port() != client_port:
            print(f"WARNING: Port mismatch detected!")
            print(f"  Domain '{str(domain_obj)}' will receive traffic on port {domain_obj.port()}")
            print(f"  But the FLNet Client is configured to listen on port {client_port}")
            print(f"  Make sure you relay traffic from port {domain_obj.port()} to port {client_port} on the server.")
            print(f"  This is typically done via a reverse proxy (nginx, apache, etc.).")
            input("Press Enter to continue...")
            print()

    print()
    # ========================================================================
    # 3. Which FLNet platform to connect to?
    # ========================================================================

    # Create default global domain object (443 is default for HTTPS, so not specified)
    if not global_domain_obj: # wasnt set by predefined config
        while True:
            global_domain_input = input(f"Enter the FLNet platform address with protocol (e.g., 'https://platform.example.com'). Press Enter for default ({DEFAULT_FULL_GLOBAL_ADDRESS}): ").strip()
            if not global_domain_input:
                global_domain_input = DEFAULT_FULL_GLOBAL_ADDRESS
                break

            temp_global_domain_obj = Domain(global_domain_input)
            if not temp_global_domain_obj.is_valid():
                if not temp_global_domain_obj.protocol_is_valid():
                    print("ERROR: You must specify a protocol (http:// or https://).")
                elif not temp_global_domain_obj.domain_is_valid():
                    print("ERROR: The domain name is not valid.")
                elif not temp_global_domain_obj.port_is_valid():
                    print("ERROR: The port is not valid.")
                continue

            # overwrite default with valid input
            global_domain_obj = temp_global_domain_obj
            print(f"Connecting to FLNet platform at '{global_domain_obj}'.")
            break

    # get the tcp port
    if not global_tcp_port: # wasnt set by predefined config
        while True:
            global_tcp_port = input(f"Enter the TCP port of the global platform for relay connections (default {DEFAULT_PLATFORM_TCP_PORT}): ").strip()
            if not global_tcp_port:
                global_tcp_port = DEFAULT_PLATFORM_TCP_PORT
                break
            if validate_port(global_tcp_port):
                break
            else:
                print(f"The port '{global_tcp_port}' is not valid. Please enter a number between 1 and 65535.")
    print()
    assert global_domain_obj is not None, "Global domain object should be set at this point. Script error."
    # ========================================================================
    # 4. Generate Secrets
    # ========================================================================
    print("Securely generating database secrets...\n")
    # --- dataimport-secrets ---
    importer_db_password = gen_secret()
    importer_db_root_password = gen_secret()
    importer_secret_key = gen_secret()
    importer_api_client_secret = gen_secret()

    dataimport_secrets_file = FLNET_CLIENT_ENV_DIR / 'dataimport-secrets.env'
    if not write_env_file(
        dataimport_secrets_file,
        MYSQL_PASSWORD=importer_db_password,
        MYSQL_ROOT_PASSWORD=importer_db_root_password,
        SQL_PASSWORD=importer_db_password,
        KEYCLOAK_CLIENT_SECRET_KEY=importer_api_client_secret,
        SECRET_KEY=importer_secret_key,
    ):
        sys.exit(1)

    # --- orch-secrets ---
    orch_db_password = gen_secret()

    orch_api_secrets_file = FLNET_CLIENT_ENV_DIR / 'orch-secrets.env'
    if not write_env_file(
        orch_api_secrets_file,
        POSTGRES_PASSWORD=orch_db_password,
        QUARKUS_DATASOURCE_PASSWORD=orch_db_password
    ):
        sys.exit(1)

    # --- learning-secrets ---
    learning_db_password = gen_secret()
    learning_api_client_secret = gen_secret()

    learning_api_secrets_file = FLNET_CLIENT_ENV_DIR / 'local-learning-secrets.env'
    if not write_env_file(
        learning_api_secrets_file,
        POSTGRES_PASSWORD=learning_db_password,
        QUARKUS_DATASOURCE_PASSWORD=learning_db_password,
        QUARKUS_OIDC_CREDENTIALS_SECRET=learning_api_client_secret,
        QUARKUS_KEYCLOAK_ADMIN_CLIENT_CLIENT_SECRET=learning_api_client_secret,
      # see env/local-learning-secrets.env
    ):
        sys.exit(1)

    # --- keycloak-secrets ---
    keycloak_db_password = gen_secret()
    keycloak_bootstrap_admin_password = gen_secret(16)
        # Needs to be used by the admin, so we make it a bit shorter and easier to handle
        # We advise the user to change it after first login anyways!

    keycloak_secrets_file = FLNET_CLIENT_ENV_DIR / 'keycloak-secrets.env'
    if not write_env_file(
        keycloak_secrets_file,
        POSTGRES_PASSWORD=keycloak_db_password,
        KC_DB_PASSWORD=keycloak_db_password,
        KC_BOOTSTRAP_ADMIN_PASSWORD=keycloak_bootstrap_admin_password,
        LOCAL_LEARNING_SECRET=learning_api_client_secret,
        DATA_IMPORTER_SECRET=importer_api_client_secret,
    ):
        sys.exit(1)

    print("All secrets generated and stored securely.\n")
    print()

    # ========================================================================
    # 5. Patch nginx.conf and save the final .env file
    # ========================================================================
    if domain_obj is not None:
        deployed_on_address = str(domain_obj)
        # DEPLOYED_ON_DOMAIN: bare hostname[:port] without protocol, for Django ALLOWED_HOSTS.
        # nginx forwards the original Host header ($host) to backends, which contains no protocol.
        deployed_on_domain = domain_obj.domain_name()
        if not domain_obj.is_default_port():
            assert domain_obj is not None, "Domain object should not be None here. Script error."
            deployed_on_domain += f":{str(domain_obj.port())}"
    else:
        # No domain - use exposed address with http
        port_suffix = f":{client_port}" if client_port != "80" else ""
        deployed_on_address = f"http://{exposed_address}{port_suffix}"
        # For ALLOWED_HOSTS: include port only if non-standard
        deployed_on_domain = exposed_address
        if client_port not in ("80", "443"):
            deployed_on_domain += f":{client_port}"

    # Build global URLs based on global_domain_obj
    global_protocol = global_domain_obj.protocol()
    global_ws_protocol = "wss" if global_protocol == "https" else "ws"
    global_domain_name = global_domain_obj.domain_name()
    global_port = global_domain_obj.port()

    # Include port in URLs only if it's non-standard for the protocol
    global_port_suffix = ""
    if (global_protocol == "https" and global_port != "443") or (global_protocol == "http" and global_port != "80"):
        global_port_suffix = f":{global_port}"

    global_base_with_port = f"{global_domain_name}{global_port_suffix}"

    # Bake the domain into nginx.conf directly — no envsubst or shell needed at runtime.
    # On re-runs the regex replaces whatever value is already there.
    # server_name uses bare hostname only: nginx strips the port from the Host header before
    # matching, so including the port here would prevent any request from matching.
    nginx_server_name = domain_obj.domain_name() if domain_obj is not None else exposed_address
    nginx_conf_path = FLNET_CLIENT_DIR / 'nginx.conf'
    patch_nginx_server_name(nginx_conf_path, str(nginx_server_name))
    if not write_env_file(
        FLNET_CLIENT_DIR / '.env',
        comments={
            'DEPLOYED_ON_ADDRESS': 'WARNING: Changing DEPLOYED_ON_ADDRESS or DEPLOYED_ON_DOMAIN here will NOT update the nginx server_name. Re-run the installer to regenerate nginx.conf with the new domain.',
        },
        EXPOSED_IP_ADDRESS=exposed_ip_address,
            # IP address for docker binding (docker doesn't understand 'localhost')
        EXPOSED_PORT=client_port,
        DEPLOYED_ON_ADDRESS=deployed_on_address,
        DEPLOYED_ON_DOMAIN=deployed_on_domain,
        GLOBAL_BASE_ADDRESS=global_domain_name,
        GLOBAL_LEARNING_API_URL=f"{global_protocol}://{global_base_with_port}/api",
        GLOBAL_LEARNING_API_WEBSOCKET_URL=f"{global_ws_protocol}://{global_base_with_port}/api",
        GLOBAL_SCHEMA_API_URL=f"{global_protocol}://{global_base_with_port}/data-modeler",
        GLOBAL_RELAY_HTTP_URL=f"{global_protocol}://{global_base_with_port}/relay",
        GLOBAL_RELAY_TCP_ADDRESS=f"{global_domain_name}:{global_tcp_port}",
        COMPOSE_PROFILES="no-ssl" if not ssl_folder else "ssl",
        SSL_CERT_PUBLIC_KEY=str(fullchain_file) if fullchain_file else "dummyfile",
        SSL_CERT_PRIVATE_KEY=str(privkey_file) if privkey_file else "dummyfile",
        FRONTEND_IMAGE=GLOBAL_DOMAIN_TO_IMAGE.get(str(global_domain_obj), DEFAULT_FRONTEND_IMAGE)
    ):
        sys.exit(1)

    # ========================================================================
    # 6. Installation Summary
    # ========================================================================
    print("⚠️")
    print("The FLNet Client is not started yet. To start it, please do the following:\n")
    print(f"cd {FLNET_CLIENT_DIR}")
    print("docker compose up -d\n")
    print("After starting, you need to perform the following steps to finalize the setup:")
    print(f"1. Access the Keycloak admin console at {deployed_on_address}/auth/")
    print("2. Login with the temporary admin credentials:")
    print("  Username: keycloak-admin")
    print(f"  Password: {keycloak_bootstrap_admin_password}")
    print("3. Change the admin password immediately after logging in.")
    print("  If you have problems with the manage account page, please add + to the Web Origins of the account-console client in the master realm.")
    print("4. Change to the 'FLNet-Client' realm in Keycloak.")
    print("5. Create a user there. Give him the appropiate group (e.g. 'Admin'). Users without a Group cannot access the FLNet Client!")
    print("6. If you want to have automatic updates: All containers are set with a watchtower label.")
    print("  More information: https://github.com/containrrr/watchtower")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during installation: {e}", file=sys.stderr)
        sys.exit(1)
