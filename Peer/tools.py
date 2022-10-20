import socket

INTERNET_PROTOCOL = socket.AF_INET6

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
        scope_id = int(address.split(",")[3].strip())
        return (ip,port,flowinfo,scope_id)
