def string_to_address(address:str) -> tuple[str,int]:
    address = address.strip("()")
    ip = address.split(",")[0].strip("\'")
    port = int(address.split(",")[1].strip())
    return (ip,port)
