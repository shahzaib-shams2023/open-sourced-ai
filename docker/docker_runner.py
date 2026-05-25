import docker

client = docker.from_env()

def run_container(command):

    container = client.containers.run(
        image="python:3.11",

        command=command,

        remove=True,

        network_disabled=True,

        mem_limit="1g",

        detach=False
    )

    return container
