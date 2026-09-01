#!/usr/bin/env python3
"""
Initializes the FLNET_CLIENT_DIR as a FL-Net Client on the current machine.
Checks first for requirements, requests relevant parameters from the user and
initializes secrets.
Leaves the user with instructions on how to then start and setup their FL-Net Client.
"""
import re
from typing import Optional
import secrets
import string
import sys
from pathlib import Path

BASE_DIR_INSTALLER_SCRIPT = Path(__file__).resolve().parent
FLNET_CLIENT_DIR = BASE_DIR_INSTALLER_SCRIPT / 'FLNet_client'
FLNET_CLIENT_ENV_DIR = FLNET_CLIENT_DIR / 'env'

DEFAULT_PLATFORM_ADDRESS = "federated-learning.net"
DEFAULT_PLATFORM_PROTOCOL = "https"
DEFAULT_FULL_GLOBAL_ADDRESS = f"{DEFAULT_PLATFORM_PROTOCOL}://{DEFAULT_PLATFORM_ADDRESS}"
DEFAULT_PLATFORM_TCP_PORT = "9152"
DEFAULT_COMPOSE_PROJECT_NAME = "flnet"
IMAGE_TAG = "latest"
GLOBAL_DOMAIN_TO_IMAGE = {
    "https://federated-learning.net": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-fl-net:{IMAGE_TAG}",
    "https://daibetes-net.cosy.bio": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-daibetes:{IMAGE_TAG}",
    "https://daibetes-net.federated-learning.net": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-daibetes:{IMAGE_TAG}",
    "https://microb-ai-net.cosy.bio": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-microbaiome:{IMAGE_TAG}",
    "https://microb-ai-net.federated-learning.net": f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-microbaiome:{IMAGE_TAG}",
}
GLOBAL_DOMAIN_TO_AUTH_ENABLED_INFO = {
    "https://federated-learning.net": True,
    "https://daibetes-net.cosy.bio": False,
    "https://daibetes-net.federated-learning.net": False,
    "https://microb-ai-net.cosy.bio": False,
    "https://microb-ai-net.federated-learning.net": False,
}
DEFAULT_FRONTEND_IMAGE = f"gitlab.cosy.bio:5050/cosybio/federated-learning/federated_db/frontend-shared/local-fl-net:{IMAGE_TAG}"
DEFAULT_KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME = "keycloak-admin"
overwrite_existing_secrets = False

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
        self.auth_enabled = GLOBAL_DOMAIN_TO_AUTH_ENABLED_INFO.get(global_domain, True)
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

PREDEFINED_NETWORKS = {
    "1": FLNET_CONFIG,
    "2": MICROBAIOME_CONFIG,
    "3": DAIBETES_CONFIG,
}

def gen_secret(length: int = 64) -> str:
    """
    Generate a URL-safe random string of given length.
    Uses secrets module for cryptographic randomness.
    """
    # To make sure this works on all systems, we limit to alphanumeric characters
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def write_env_file(filepath: Path, comments: Optional[dict] = None, skip_when_exists: bool = False, **variables) -> bool:
    """
    Write environment variables to a file with overwrite protection.

    Args:
        filepath: Path to the .env file
        comments: Optional dict mapping variable names to comment lines prepended before that variable
        skip_when_exists: If True, skip writing if the file already exists
        **variables: Key-value pairs to write (VAR=value format)

    Returns:
        True if successful, False if user aborted
    """
    global overwrite_existing_secrets
    if filepath.exists():
        if skip_when_exists:
            print(f"Info: The file '{filepath}' already exists. Skipping.")
            return True
        if overwrite_existing_secrets == False:
            while True:
                print(f"WARNING: Trying to write to '{filepath}' but it already exists.")
                print("This means you already created a deployment before. Overwriting would break an EXISTING deployment, as as soon as the deployment has been started once")
                print("The databases are initialized with the respective secrets")
                overwrite_input = input(f"Do you want to overwrite files with new settings, potentially breaking an existing deployment? (y/n): ").strip().lower()
                if overwrite_input in ('y', 'yes'):
                    print(f"Overwriting the file '{filepath}' with new settings.")
                    overwrite_existing_secrets = True
                    break
                elif overwrite_input in ('n', 'no'):
                    print(f"Skipping writing to '{filepath}' as per user request.")
                    return True
                else:
                    print("Please answer with 'y' or 'n'.")

        print(f"Warning: The file '{filepath}' already exists. Overwriting with new settings.")

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

def env_file_to_dict(filepath: Path) -> dict:
    """Read a .env file and return a dictionary of key-value pairs."""
    env_dict = {}
    if not filepath.exists():
        print(f"Warning: The file '{filepath}' does not exist. Returning empty dictionary.")
        return env_dict

    with filepath.open('r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                env_dict[key.strip()] = value.strip()
    return env_dict

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

    def is_ip_address(self) -> bool:
        """Check if the domain name is an IP address rather than a hostname."""
        if not self._domain_is_valid or self._domain_name is None:
            return False
        return validate_ip_address(self._domain_name)

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

def get_validated_user_input(prompt: str, validation_func, error_message: str, apply_lower: bool) -> str:
    """
    Prompt the user for input and validate it using the provided validation_func.
    Apply apply_lower to convert input to lowercase before validation if specified.
    Keeps prompting until valid input is received.
    """
    while True:
        user_input = input(prompt).strip()
        if apply_lower:
            user_input = user_input.lower()
        if validation_func(user_input):
            return user_input
        else:
            print(error_message)

def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question, returning default (False -> 'n') if the user just hits enter."""
    default_label = "y" if default else "n"
    while True:
        answer = get_validated_user_input(
            prompt=f"{prompt} (y/n), default: {default_label}: ",
            validation_func=lambda x: x in ("y", "yes", "n", "no", ""),
            error_message="Invalid input. Please enter 'y' or 'n'.",
            apply_lower=True,
        )
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no", ""):
            return default
        print("Please answer with 'y' or 'n'.")

def ask_choice(prompt: str, options: dict, default: str) -> str:
    """Ask the user to pick one of several named options.
    `options` maps what the user types -> the value that gets stored.
    `default` is the stored value used when the user just presses enter."""
    default_key = next(key for key, value in options.items() if value == default)
    valid_inputs = list(options.keys()) + [""]
    while True:
        answer = get_validated_user_input(
            prompt=f"{prompt} ({'/'.join(options.keys())}), default: {default_key}: ",
            validation_func=lambda x: x in valid_inputs,
            error_message=f"Invalid input. Please enter one of: {', '.join(options.keys())}.",
            apply_lower=True,
        )
        return options[answer] if answer != "" else default


def ask_int(prompt: str, default: int) -> int:
    """Ask for a whole number, returning default if the user just presses enter."""
    answer = get_validated_user_input(
        prompt=f"{prompt} default: {default}: ",
        validation_func=lambda x: x == "" or x.isdigit(),
        error_message="Invalid input. Please enter a whole number.",
        apply_lower=False
        )
    return int(answer) if answer != "" else default

# ============================================================================
# Main Installation Logic
# ============================================================================

def main():
    """Main installation/initialization workflow."""
    print("Starting the initialization of a FL-Net Client...\n")
    # All variables that will be set
    exposed_address = None
    exposed_ip_address = None
    client_port = None
    domain_obj = None
    enable_ssl_termination_in_client = False
    ssl_files_given = False
    use_self_signed_certs = False
    ssl_path = None
    fullchain_file = None
    privkey_file = None
    global_domain_obj = None
    global_tcp_port = None
    federated_learning_enabled = True
    auth_enabled = True
    frontend_image = DEFAULT_FRONTEND_IMAGE
    # ========================================================================
    # 0. Preconfiguration: Network and federation setup
    # vars: global_domain_obj, global_tcp_port, federated_learning_enabled,
    #   permission system settings, auth settings
    # ========================================================================
    network_defined = False
    while not network_defined:
        print("An FL-Net Client connects to a global network to access data schemas (standards) and")
        print("the app registry (ETL helpers, federated learning apps).")
        print("When subscriping to a schema, the client informs the network that this schema is used and the network increments the subscription counter")
        print("Otherwise, this is a read only connection and no data from the client is sent")
        print("Optionally, the same network can also be used for federated queries and learning (asked next).")
        print()
        print("Do you want to:")
        print("1. join a preexisting network")
        print("2. join a self-deployed network")
        print("You can later chose to not participate in federation and only use the network to read-only access the app registry and data schemas.")
        input_preconfiguration = get_validated_user_input(
            prompt="Enter '1' or '2': ",
            validation_func=lambda x: x in ("1", "2"),
            error_message="Invalid input. Please enter '1' or '2'.",
            apply_lower=True
        )

        if input_preconfiguration == "1":
            print("Enter the number of the network you want to join:")
            print("1. flnet")
            print("2. microbaiome")
            print("3. daibetes")
            input_predefined_config = get_validated_user_input(
                prompt="Enter '1', '2' or '3': ",
                validation_func=lambda x: x in ("1", "2", "3"),
                error_message="Invalid input. Please enter '1', '2' or '3'.",
                apply_lower=True
            )

            config = PREDEFINED_NETWORKS[input_predefined_config]
            global_domain_obj = Domain(config.global_domain)
            global_tcp_port = config.global_tcp_port
            auth_enabled = config.auth_enabled
            frontend_image = config.frontend_image
            print(f"Joining the '{config.name}' network at '{config.global_domain}' (TCP port {config.global_tcp_port}).")

        elif input_preconfiguration == "2":
            print("You chose to join your own self-deployed network.")
            print("Make sure the global platform is up and running before continuing.")
            while True:
                global_domain_input = input(f"Enter the platform address with protocol (e.g., 'https://platform.example.com'). Press Enter for default ({DEFAULT_FULL_GLOBAL_ADDRESS}): ").strip()
                if not global_domain_input:
                    global_domain_input = DEFAULT_FULL_GLOBAL_ADDRESS
                temp_global_domain_obj = Domain(global_domain_input)
                if not temp_global_domain_obj.is_valid():
                    if not temp_global_domain_obj.protocol_is_valid():
                        print("ERROR: You must specify a protocol (http:// or https://).")
                    elif not temp_global_domain_obj.domain_is_valid():
                        print("ERROR: The domain name is not valid.")
                    elif not temp_global_domain_obj.port_is_valid():
                        print("ERROR: The port is not valid.")
                    continue
                global_domain_obj = temp_global_domain_obj
                print(f"Connecting to platform at '{global_domain_obj}'.")
                break
            while True:
                global_tcp_port = input(f"Enter the TCP relay port of the global platform (default {DEFAULT_PLATFORM_TCP_PORT}): ").strip()
                if not global_tcp_port:
                    global_tcp_port = DEFAULT_PLATFORM_TCP_PORT
                    break
                if validate_port(global_tcp_port):
                    break
                else:
                    print(f"The port '{global_tcp_port}' is not valid. Please enter a number between 1 and 65535.")

            auth_enabled = ask_yes_no(
                "Is authentication of your Client to the  Platform enabled on your self-deployed platform?",
                default=True
            )
            frontend_image = GLOBAL_DOMAIN_TO_IMAGE.get(str(global_domain_obj), DEFAULT_FRONTEND_IMAGE)

        # Step B: Federation participation (join and own only)
        print()
        print("The TCP relay and WebSocket connection enable federated queries and learning across organizations.")
        print("This allows privacy-preserving computation on data distributed across multiple sites.")
        while True:
            federation_input = input("Do you want to enable federated queries and learning? (y/n): ").strip().lower()
            if federation_input in ("y", "yes"):
                federated_learning_enabled = True
                print("Federated queries and learning will be enabled.")
                break
            elif federation_input in ("n", "no"):
                federated_learning_enabled = False
                print("Federated queries and learning will be disabled. Relevant addresses will be set to non-resolving addresses.")
                break
            else:
                print("Please answer with 'y' or 'n'.")
        network_defined = True

        # Step C: Privacy settings - Should automatic-access permissions be allowed to exist at all?
        print("\nThe FL-Net Client uses a permission system that controls which global network users can access certain resources on this client:")
        print("  - Resources: federated queries, statistics, learning results, and metrics from executed federated learning runs.")
        print("  - Users: these are users on the FL-Net network you're joining, NOT local accounts on this machine. When a permission is created, it can be scoped to one specific user or opened up to any user.")
        print("\nStatistics, learning results, and metrics require manual approval by default for every access request.")
        print("Here, you decide whether 'automatic' access is even allowed to exist for these three resources. If you say no here, no permission created later at any point will ever be able to skip manual approval for that resource.")

        automatic_statistics_permission_enabled = ask_yes_no(
            "Should automatic-access permissions be allowed to exist at all for STATISTICS?"
        )
        automatic_learning_permission_enabled = ask_yes_no(
            "Should automatic-access permissions be allowed to exist at all for LEARNING results?"
        )
        automatic_metrics_permission_enabled = ask_yes_no(
            "Should automatic-access permissions be allowed to exist at all for METRICS?"
        )

        # Step D: Privacy settings - default permission for new cohorts
        print("\nRegarding this permission system, we support setting up a default permission that's created automatically for every new cohort on this client.")
        print("This also configures the default handling of federated queries. ")

        cohort_permission_enabled = ask_yes_no(
            "Do you want to set up this default permission for every new cohort?", default=False
        )

        if cohort_permission_enabled:
            global_user_id = get_validated_user_input(
                prompt="Who is this default permission for? Give a specific FL-Net user ID, or leave blank for any user: ",
                validation_func=lambda x: True,
                error_message="",
                apply_lower=False
            )

            if automatic_statistics_permission_enabled:
                auto_statistics_access = ask_choice(
                    "Should the default permission grant automatic access to STATISTICS? 'all' automatically approves every request; 'none' leaves every request requiring manual approval.",
                    options={"all": "ALL", "none": "NONE"},
                    default="NONE",
                )
            else:
                auto_statistics_access = "NONE"

            if automatic_metrics_permission_enabled:
                auto_metrics_access = ask_choice(
                    "Should the default permission grant automatic access to METRICS? 'all' automatically approves every request; 'none' leaves every request requiring manual approval.",
                    options={"all": "ALL", "none": "NONE"},
                    default="NONE",
                )
            else:
                auto_metrics_access = "NONE"

            if automatic_learning_permission_enabled:
                print("(Note: learning access is never automatic for tools that require internet or host access — those always require manual approval, regardless of this setting or any other permissions)")
                auto_learning_access = ask_choice(
                    "Should the default permission grant automatic access to LEARNING results? 'all' automatically approves every request; 'certified' automatically approves only requests using certified tools; 'none' leaves every request requiring manual approval.",
                    options={"all": "ALL", "none": "NONE", "certified": "CERTIFIED_APPS"},
                    default="NONE",
                )
            else:
                auto_learning_access = "NONE"

            print("\nFederated queries work differently: once a permission allows queries, access is granted automatically — there is no manual-approval step.")
            print("Instead, the permission configures privacy protections applied to the results: thresholding, rounding, and rate-limiting.")

            is_allowed_to_query = ask_yes_no(
                "Allow federated queries against this client's data?", default=True
            )

            if is_allowed_to_query:
                query_retry_time = ask_int(
                    "Minimum seconds between answering repeated queries (rate-limiting)?", default=3
                )
                query_sample_threshold = ask_int(
                    "Minimum sample size required before a query is answered (thresholding)?", default=100
                )
            else:
                query_retry_time = 3
                query_sample_threshold = 100

        else:
            auto_learning_access = "NONE"
            auto_statistics_access = "NONE"
            auto_metrics_access = "NONE"
            is_allowed_to_query = True
            query_retry_time = 3
            query_sample_threshold = 100
            global_user_id = ""

        # Step E: Authentication settings
        username = "dummy"
        password = "dummy"
        if auth_enabled:
            print("\nThe FL-Net Client authorizes towards the FL-Net Platform. You should have created or received a user account on the platform before continuing.")
            print("If this is not the case, please create an account on the platform first and then come back to this installer.")
            username = input("Please enter your FL-Net Platform username: ").strip()
            password = input("Please enter your FL-Net Platform password: ").strip()

    # ========================================================================
    # 1. Which interface to listen on?
    # vars: exposed_address
    # ========================================================================
    print("A FL-Net Client is accessed via the browser.")
    print("You can either only expose the client to this machine (localhost), or expose it to the internet/intranet.")
    print("If you expose to the internet, consider limiting access to your server to only your internal network or via a VPN for security reasons.")
    print("You can also set up SSL encryption for encrypted communication later in the setup.\n")
    while True:
        exposed_address_input = input("\nPlease specify the address without port the FL-Net Client should run on. We suggest to use 0.0.0.0 to open to the internet/intranet or localhost to only listen on this machine (default 127.0.0.1 if you just press Enter): ").strip().lower()
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

    # ========================================================================
    # 2. Domain configuration including SSL
    # vars: domain_name, host_port, ssl_files_given, fullchain_file, privkey_file
    # ========================================================================
    # Domain Name and host port retrieval loop
    print("You can optionally set the domain you are using for your FL-Net Client.")
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
        print("How do you want to provide SSL certificates?")
        print("  1) Provide existing certificate files (e.g. from Let's Encrypt / certbot)")
        print("  2) Use self-signed certificates (generated separately via create_self_signed_certs_config.py + create_self_signed_certs.sh)")
        ssl_source_input = input("Enter '1' or '2': ").strip()

        if ssl_source_input == '2':
            # Self-signed path: cert files don't exist yet, set paths to the predefined location
            self_signed_dir = BASE_DIR_INSTALLER_SCRIPT / 'FLNet_client' / 'self_signed_certs'
            fullchain_file = self_signed_dir / 'fullchain.pem'
            privkey_file   = self_signed_dir / 'privkey.pem'
            use_self_signed_certs = True
            ssl_files_given = True
            print(f"Self-signed certificate paths set:")
            print(f"  Certificate : {fullchain_file}")
            print(f"  Private key : {privkey_file}")
            print("IMPORTANT: If you didn't specifically create any certificates already, the certificate files do not exist yet.")
            print("  Before running 'docker compose up', you MUST:")
            print("  Either generate the certs yourself or use the helper:")
            print("  python3 create_self_signed_certs.py")
            print("  This installer will remind you at the end.")
            input("  Press Enter to continue...")
            break

        elif ssl_source_input == '1':
            print("Please provide the paths to your SSL certificate files.")
            cert_input = input("Enter the path to your public certificate file (e.g. fullchain.pem): ").strip()
            fullchain_file = Path(cert_input).resolve()
            if not fullchain_file.exists():
                print(f"ERROR: The file '{cert_input}' does not exist.")
                continue

            key_input = input("Enter the path to your private key file (e.g. privkey.pem): ").strip()
            privkey_file = Path(key_input).resolve()
            if not privkey_file.exists():
                print(f"ERROR: The file '{key_input}' does not exist.")
                continue

            ssl_files_given = True
            print(f"SSL certificate files found: '{fullchain_file}' and '{privkey_file}'.")
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

        else:
            print("Please enter '1' or '2'.")
            continue

    # which port?
    # If we terminate SSL we take the given port from the domain, in the other case
    # the user does SSL termination and therefore will listen on the domain_obj port with something
    # else just use 8250, some whatever default port
    default_client_port = domain_obj.port() if domain_obj is not None and ssl_files_given else "8250"
    assert default_client_port is not None, "Default client port should be set at this point. Script error."
    while True:
        client_port_input = input(f"Please specify the port that the FL-Net Client should listen on (default is {default_client_port}): ").strip()
        client_port = client_port_input or default_client_port
        if validate_port(client_port):
            break
        else:
            print(f"The port '{client_port}' is not valid. Please enter a number between 1 and 65535.")
    print(f"Exposing the FL-Net Client to {exposed_address}:{client_port}.\n")
    print()

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
    if exposed_address != "localhost" and not ssl_files_given:
        print("WARNING: The FL-Net Client is exposed to a non localhost IP without SSL encryption.")
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
    if domain_obj is not None and domain_obj.protocol() == 'https' and not ssl_files_given:
        print("WARNING: You specified HTTPS protocol but did not provide SSL certificates.")
        print("  Without SSL certificates, the client cannot serve HTTPS traffic directly.")
        print("  You MUST use an external reverse proxy (e.g., nginx, Caddy) to handle SSL termination.")
        print("  Make sure to forward traffic from port 443 to the FL-Net Client and handle SSL termination in the reverse proxy.")
        print("  Furthermore make sure to preserve the Host header ($host) in the reverse proxy or the FL-Net Client will not work properly!")
        input("Press Enter to continue...")
        print()

    # Warning 3: Domain with localhost exposure
    if domain_obj is not None and exposed_address == "localhost":
        print("WARNING: You specified a domain name, but the FL-Net Client is only listening on localhost.")
        print(f"  Make sure you have a reverse proxy forwarding traffic from {str(domain_obj)} to localhost:{client_port} or use a reverse tunnel.")
        if ssl_files_given:
            print(f"  Additionally, you configured SSL certificates ('{fullchain_file}', '{privkey_file}') for localhost-only access.")
            print("  This is unusual - SSL is typically not needed for localhost. Consider having your")
            print("  reverse proxy handle SSL termination instead. You can abort via Ctrl+C and re-run the installer without SSL.")
        input("Press Enter to continue...")
        print()

    # Warning 4: Port mismatch between domain and client
    if domain_obj is not None:
        if domain_obj.port() != client_port:
            print(f"WARNING: Port mismatch detected!")
            print(f"  Domain '{str(domain_obj)}' will receive traffic on port {domain_obj.port()}")
            print(f"  But the FL-Net Client is configured to listen on port {client_port}")
            print(f"  Make sure you relay traffic from port {domain_obj.port()} to port {client_port} on the server.")
            print(f"  This is typically done via a reverse proxy (nginx, apache, etc.).")
            input("Press Enter to continue...")
            print()

    print()
    assert global_domain_obj is not None, "Global domain object should be set at this point. Script error."
    # ========================================================================
    # 3. Generate Secrets
    # ========================================================================
    print("Securely generating database secrets...\n")

    # --- orch-secrets ---
    orch_db_password = gen_secret()

    orch_api_secrets_file = FLNET_CLIENT_ENV_DIR / 'orch-secrets.env'
    if not write_env_file(
        orch_api_secrets_file,
        skip_when_exists=False,
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
        skip_when_exists=False,
        POSTGRES_PASSWORD=learning_db_password,
        QUARKUS_DATASOURCE_PASSWORD=learning_db_password,
        QUARKUS_OIDC_CREDENTIALS_SECRET=learning_api_client_secret,
        QUARKUS_KEYCLOAK_ADMIN_CLIENT_CLIENT_SECRET=learning_api_client_secret,
        QUARKUS_OIDC_CLIENT_GRANT_OPTIONS_PASSWORD_USERNAME=username,
        QUARKUS_OIDC_CLIENT_GRANT_OPTIONS_PASSWORD_PASSWORD=password,
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
        skip_when_exists=False,
        KC_BOOTSTRAP_ADMIN_USERNAME=DEFAULT_KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME,
        POSTGRES_PASSWORD=keycloak_db_password,
        KC_DB_PASSWORD=keycloak_db_password,
        KC_BOOTSTRAP_ADMIN_PASSWORD=keycloak_bootstrap_admin_password,
        LOCAL_LEARNING_SECRET=learning_api_client_secret,
    ):
        sys.exit(1)

    print("All secrets generated and stored securely.\n")
    print()

    # ========================================================================
    # 5. Patch nginx.conf and save the final .env file
    # ========================================================================
    # Build global URLs based on global_domain_obj
    global_protocol = global_domain_obj.protocol()
    global_ws_protocol = "wss" if global_protocol == "https" else "ws"
    global_domain_name = global_domain_obj.domain_name()
    global_port = global_domain_obj.port()
    assert global_protocol in ("http", "https"), "Global protocol must be either 'http' or 'https'."

    # Include port in URLs only if it's non-standard for the protocol
    global_port_suffix = ""
    if (global_protocol == "https" and global_port != "443") or (global_protocol == "http" and global_port != "80"):
        global_port_suffix = f":{global_port}"

    global_base_with_port = f"{global_domain_name}{global_port_suffix}"

    # Federation host: real domain for WebSocket/relay when enabled, non-resolving otherwise
    if federated_learning_enabled:
        global_federation_host = global_domain_name
        global_keycloak_url = global_protocol + "://" + global_base_with_port + "/auth/realms/FLNet-Platform"
    else:
        global_federation_host = "federated-learning.invalid"
        global_keycloak_url = ""

    # Set the complete domain with protocol and port as well as the bare domain
    # bare domain is required as ALLOWED_HOSTS in Django
    # as well as server_name in nginx
    # we set this in nginx via patching the nginx.conf
    if domain_obj is not None:
        deployed_on_address = str(domain_obj)
        deployed_on_domain = domain_obj.domain_name()
    else:
        # No domain - use exposed address with http
        port_suffix = f":{client_port}" if client_port != "80" else ""
        deployed_on_address = f"http://{exposed_address}{port_suffix}"
        deployed_on_domain = exposed_address

    nginx_conf_path = FLNET_CLIENT_DIR / 'nginx.conf'
    patch_nginx_server_name(nginx_conf_path, str(deployed_on_domain))
    if not write_env_file(
        FLNET_CLIENT_DIR / '.env',
        comments={
            'DEPLOYED_ON_ADDRESS': 'WARNING: Changing DEPLOYED_ON_ADDRESS or DEPLOYED_ON_DOMAIN here will NOT update the nginx server_name. Re-run the installer to regenerate nginx.conf with the new domain.',
        },
        skip_when_exists=False,
        COMPOSE_PROJECT_NAME=DEFAULT_COMPOSE_PROJECT_NAME,
        EXPOSED_IP_ADDRESS=exposed_ip_address,
            # IP address for docker binding (docker doesn't understand 'localhost')
        EXPOSED_PORT=client_port,
        DEPLOYED_ON_ADDRESS=deployed_on_address,
        DEPLOYED_ON_DOMAIN=deployed_on_domain,
        GLOBAL_DOMAIN=global_base_with_port,
        GLOBAL_HTTP_PROTOCOL=global_protocol,
        GLOBAL_WS_PROTOCOL=global_ws_protocol,
        GLOBAL_TCP_PORT=global_tcp_port,
        FEDERATED_LEARNING_ENABLED="true" if federated_learning_enabled else "false",
        GLOBAL_FEDERATION_HOST=global_federation_host,
        COMPOSE_PROFILES="no-ssl" if not ssl_files_given else "ssl",
        SSL_CERT_PUBLIC_KEY=str(fullchain_file) if fullchain_file else "dummyfile",
        SSL_CERT_PRIVATE_KEY=str(privkey_file) if privkey_file else "dummyfile",
        FRONTEND_IMAGE=frontend_image,
        DISABLE_AUTOMATIC_COHORT_PERMISSION_METRICS="true" if not automatic_metrics_permission_enabled else "false",
        DISABLE_AUTOMATIC_COHORT_PERMISSION_STATISTICS="true" if not automatic_statistics_permission_enabled else "false",
        DISABLE_AUTOMATIC_COHORT_PERMISSION_LEARNING="true" if not automatic_learning_permission_enabled else "false",
        COHORT_PERMISSION_ENABLED="true" if cohort_permission_enabled else "false",
        COHORT_PERMISSION_QUERY_RETRY_TIME=query_retry_time,
        COHORT_PERMISSION_IS_ALLOWED_TO_QUERY="true" if is_allowed_to_query else "false",
        COHORT_PERMISSION_QUERY_SAMPLE_THRESHOLD=query_sample_threshold,
        COHORT_PERMISSION_GLOBAL_USER_ID=global_user_id,
        COHORT_PERMISSION_AUTO_TRAINING_ACCESS=auto_learning_access,
        COHORT_PERMISSION_AUTO_STATISTICS_ACCESS=auto_statistics_access,
        COHORT_PERMISSION_AUTO_METRICS_ACCESS=auto_metrics_access,
        GLOBAL_KEYCLOAK_URL=global_keycloak_url,
        GLOBAL_KEYCLOAK_ENABLED="true" if auth_enabled else "false",
    ):
        sys.exit(1)
    # ========================================================================
    # 6. Installation Summary
    # ========================================================================
    self_signed_startup_instructions = ""
    additional_instructions = ""
    if use_self_signed_certs:
        self_signed_startup_instructions = (
            "\nBefore starting, you MUST generate your self-signed certificates:\n"
            f"  python3 {BASE_DIR_INSTALLER_SCRIPT / 'create_self_signed_certs.py'}\n"
            "  You MUST also comment out the HSTS header in FLNet_client/nginx_conf_HTTPS.conf or disable HSTS in your browser for the domain to avoid issues with self-signed certs, otherwise the browser accessing the Client will refuse to let you visit the site!\n"
        )

    if domain_obj is not None and domain_obj.protocol() == 'https' and domain_obj.is_ip_address():
        additional_instructions = (
            "You are using an IP address as the domain using HTTPS.\n"
            "The NGINX config is NOT setup for this as this is somewhat unusual.\n"
            "NGINX cannot correctly find the right server block (the right configuration) for IP addresses.\n"
            "The steps below reassign 'default_server' to the SSL block so NGINX starts cleanly.\n"
            "Please perform the following manual steps:\n"
            f"1. Go to the client directory: cd {FLNET_CLIENT_DIR}\n"
            "2. Open the file nginx.conf in a text editor.\n"
            "You need to comment out/remove the default server block at the end of the file:\n"
            "You can find it via the searching for 'listen 443 ssl default_server;'"
            "3. Open the file nginx_conf_HTTPS.conf in a text editor.\n"
            "You need to add to the listen directive the default_server flag."
            "Change 'listen 443 ssl;' to 'listen 443 ssl default_server;'"
        )

    client_startup_instructions = (
        "The FL-Net Client is not started yet. To start it, please do the following:\n\n"
        f"cd {FLNET_CLIENT_DIR}\n"
        "docker compose up -d\n"
        f"{self_signed_startup_instructions}\n"
        f"{additional_instructions}\n"
        "After starting, you need to perform the following steps to finalize the setup:\n"
        f"1. Access the Keycloak admin console at {deployed_on_address}/auth/\n"
        "2. Find the temporary admin credentials in FLNet_client/env/keycloak-secrets.env\n"
        "3. Change the admin password immediately after logging in.\n"
        "  If you have problems with the manage account page, please add + to the Web Origins of the account-console client in the master realm.\n"
        "4. Change to the 'FL-Net-Client' realm in Keycloak.\n"
        "5. Create a user there. Give him the appropiate group (e.g. 'Admin'). Users without a Group cannot access the FL-Net Client!\n"
        "6. If you want to have automatic updates: All containers are set with a watchtower label. You can simply add a watchtower contaner to the docker compose file.\n"
        "  More information: https://github.com/containrrr/watchtower\n"
        "For more information, please refer to the deployment documentation:\n"
        "https://federated-learning.net/documentation/docs/client-deployment-usage/deploy-client\n"
    )

    client_startup_instructions_file = BASE_DIR_INSTALLER_SCRIPT / 'client_startup_instructions.txt'
    client_startup_instructions_file.write_text(client_startup_instructions)

    print("⚠️")
    print(client_startup_instructions)
    print(f"A copy of these startup instructions was written to {client_startup_instructions_file}.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during installation: {e}", file=sys.stderr)
        sys.exit(1)
