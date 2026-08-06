import platform
import socket


def get_system_info() -> str:
    return (
        f"Platform: {platform.platform()}\n"
        f"System: {platform.system()}\n"
        f"Release: {platform.release()}\n"
        f"Hostname: {socket.gethostname()}"
    )
