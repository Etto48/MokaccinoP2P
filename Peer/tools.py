import socket
import time

INTERNET_PROTOCOL = socket.AF_INET

if INTERNET_PROTOCOL == socket.AF_INET:
    addr = tuple[str,int]
elif INTERNET_PROTOCOL == socket.AF_INET6:
    addr = tuple[str,int,int,int]


def string_to_address(address:str) -> addr:
    address = address.strip("()")
    ip = address.split(",")[0].strip("\'")
    port = int(address.split(",")[1].strip())
    if INTERNET_PROTOCOL == socket.AF_INET:
        return (ip,port)
    elif INTERNET_PROTOCOL == socket.AF_INET6:
        flowinfo = int(address.split(",")[2].strip())
        scope_id = 0
        return (ip,port,flowinfo,scope_id)

class peer:
    def __init__(self,nickname:str,address:addr):
        self.last_seen = 0
        self.nickname = nickname
        self.address = address
    def see(self):
        self.last_seen = time.time()


def get_msg_command(msg:bytearray) -> str:
    command = ""
    for b in msg:
        if b != 58: #58 = ':'
            command += chr(b)
        else:
            break
    return command