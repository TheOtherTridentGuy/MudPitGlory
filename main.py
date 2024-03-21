import paramiko
import socket
import threading
import redis
import json

from paramiko import Ed25519Key, PKey, Channel
from paramiko.common import AUTH_FAILED, AUTH_SUCCESSFUL, OPEN_SUCCEEDED
from typing import override

db = redis.Redis(host='redis', port=6379, db=0)

# Create a custom server interface class with overrides for methods in
# paramiko.ServerInterface that handle authentication and channel requests
class CustomServerInterface(paramiko.ServerInterface):
    @override
    def get_allowed_auths(self, username: str) -> str:
        return "publickey,none"

    @override
    def check_auth_publickey(self, username: str, key: PKey) -> int:
        return AUTH_SUCCESSFUL
    @override
    def check_auth_none(self, username: str) -> int:
        return AUTH_FAILED if db.get(username) == None else AUTH_SUCCESSFUL

    @override
    def check_channel_request(self, kind: str, chanid: int) -> int:
       return OPEN_SUCCEEDED

    @override
    def check_channel_pty_request(self, channel: Channel, term: bytes, width: int, height: int, pixelwidth: int, pixelheight: int, modes: bytes) -> bool:
        return True

    @override
    def check_channel_shell_request(self, channel: Channel) -> bool:
        return True

    @override
    def check_channel_exec_request(self, channel: Channel, command)-> bool:
        return True

def handle_client(client_socket):
    # Use Paramiko to handle SSH client connections
    transport = paramiko.Transport(client_socket)
    transport.add_server_key(Ed25519Key(filename="./id_ed25519"))

    server = CustomServerInterface()
    transport.start_server(server=server)
    channel = transport.accept()
    # Additional code to handle SSH sessions
    if channel is not None:
        if transport.get_username() is not None:
            user = str(transport.get_username())
        else:
            channel.send(b"Username not found, bye!")
            transport.close()
        channel.send(b'Welcome to MudPitGlory! Press any key to continue...\n\r')
        first_msg = channel.recv(1000)

        print(first_msg)
        print(first_msg.decode('utf-8'))

        if "ssh-ed25519" in str(first_msg):
            print("user sent ED25519 key, saving it...")
            if db.get(user) is None:
                db.set(user, json.dumps({"key": first_msg.decode('utf-8').rstrip()}))
        else:
            channel.send(bytes(f"Hello, {user}! You are authenticated, your key is {json.loads(db.get(user))["key"]}\n\r", "utf-8")) # type: ignore
        channel.close()


# Set up the server socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('0.0.0.0', 22))  # Bind to port 22 for SSH
server_socket.listen(100)

print("Paramiko SSH Server running.")

while True:
    client, addr = server_socket.accept()
    print(f"Accepted connection from {addr}")
    client_handler = threading.Thread(target=handle_client, args=(client,))
    client_handler.start()
