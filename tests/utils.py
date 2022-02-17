import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests
from thehive4py.client import TheHiveApi


@dataclass
class Container:
    url: str
    name: str


def is_hive_container_responsive(container_url: str) -> bool:
    COOLDOWN = 1.0
    TIMEOUT = 30.0

    now = time.time()
    end = now + TIMEOUT

    while now < end:
        try:
            response = requests.get(f"{container_url}/api/status")
            if response.ok:
                return True
        except Exception:
            pass

        time.sleep(COOLDOWN)
        now = time.time()
    return False


def is_hive_container_exist(container_name: str) -> bool:
    exist_cmd = subprocess.run(
        shlex.split(f"docker ps -aq --filter name={container_name}"),
        capture_output=True,
        text=True,
    )
    return bool(exist_cmd.stdout.strip())


def generate_container_name() -> str:
    CONTAINER_PREFIX = "thehive4py-integration-tests"
    return CONTAINER_PREFIX


def get_container_port(container_name: str) -> str:
    port_cmd = subprocess.run(
        shlex.split(f"docker port {container_name}"), capture_output=True, text=True
    )
    port = port_cmd.stdout.strip().split(":")[-1]
    return port


def build_container_url(container_name: str) -> str:
    port = get_container_port(container_name)
    return f"http://localhost:{port}"


def run_hive_container(
    container_name: str, container_image: str = "thehive4py-thehive"
):
    subprocess.run(
        shlex.split(
            f"docker run -d --rm -p 9000 --name {container_name} {container_image}"
        ),
        capture_output=True,
        text=True,
    )


def cleanup_hive_container(container_name: str):
    subprocess.run(
        shlex.split(f"docker rm -f {container_name}"),
        capture_output=True,
        text=True,
    )


def spawn_hive_container() -> Container:
    name = generate_container_name()

    if not is_hive_container_exist(container_name=name):
        run_hive_container(container_name=name)
    url = build_container_url(container_name=name)

    if not is_hive_container_responsive(container_url=url):
        cleanup_hive_container(container_name=name)
        raise RuntimeError("Unable to startup test container for TheHive")

    return Container(url=url, name=name)


def reinit_hive_container(client: TheHiveApi) -> None:

    alerts = client.alert.find()
    cases = client.case.find()

    with ThreadPoolExecutor() as executor:
        executor.map(client.alert.delete, [alert["_id"] for alert in alerts])
        executor.map(client.case.delete, [case["_id"] for case in cases])