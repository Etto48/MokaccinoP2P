from asyncio import open_connection
from . import connection
from . import printing


def parse_command(command:str):
    command_args = command.split()
    if command_args[0] == "connect" and len(command_args) == 2:
        connection.udp_socket.sendto(f"REQUEST:{connection.config['nickname']}:{command_args[1]}".encode("ASCII"),connection.server_address)
    elif command_args[0] == "disconnect" and len(command_args) == 2:
        if command_args[1] not in connection.open_connections:
            printing.rcprint(f"You are not connected with {command_args[1]}","red")
        else:
            connection.udp_socket.sendto(f"DISCONNECT:{connection.config['nickname']}".encode("ASCII"),connection.open_connections[command_args[1]].address)
            connection.open_connections.pop(command_args[1])
    elif command_args[0] == "msg" and len(command_args) == 3:
        if command_args[1] not in connection.open_connections:
            printing.rcprint(f"You are not connected with {command_args[1]}","red")
        else:
            connection.udp_socket.sendto(f"MSG:{connection.config['nickname']}:{command_args[2]}".encode("ASCII"),connection.open_connections[command_args[1]].address)
            printing.rcprint(printing.format_messge(False,command_args[1],command_args[2]),"yellow")
    elif command_args[0] == "help":
        pass
    else:
        printing.rcprint("Command not found","red")