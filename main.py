import socket

TIMEOUT = 0.1

'''
after connection server waits for Nickname

you can request a connection to a user sending an UDP packet with
"REQUEST:<your nickname>:<target nickname>"
the server will respond with
"FOUND:<target nickname>:(<addr>,<port>)"
or
"NOT FOUND"

the server may inform you about a new user wanting to connect with
"PENDING:<nickname>:(<addr>,<port>)"
you may respond with
"HERE:<nickname>" in an UDP packet, then try to connect to (<addr>,<port>) with UDP for a while
or
"REFUSE:<nickname>" in an UDP packet to reject the request
'''

waiting_list:dict[str,str] = {}

server_tcp_addr = ("0.0.0.0",25566)
server_udp_addr = ("0.0.0.0",25566)
server_udp_socket = socket.socket(family=socket.AF_INET,type=socket.SOCK_DGRAM)
server_socket = socket.socket(family=socket.AF_INET,type=socket.SOCK_STREAM)
server_udp_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
server_udp_socket.bind(server_udp_addr)
server_socket.bind(server_tcp_addr)
server_socket.listen()
clients:dict[str,tuple[socket.socket,tuple[str,int]]] = {}


server_socket.settimeout(TIMEOUT)
server_udp_socket.settimeout(TIMEOUT)
dots = ["   ",".  ",".. ","..."]
dot_iter = 0
try:
    while True:
        try:
            #new connection
            client_socket, client_addr = server_socket.accept()
            client_socket.settimeout(TIMEOUT)
            raw_nickname = client_socket.recv(1024)
            nickname = raw_nickname.decode("ASCII").split('\n')[0]
            if nickname not in clients:
                clients[nickname] = (client_socket,client_addr)
                print(f"{nickname} connected! {client_addr}")
        except TimeoutError:
            pass
        to_remove:list[str] = []
        for name,client_info in clients.items():
            #check old connections
            try:
                data = client_info[0].recv(1024)
                if not data: #client disconnected
                    print(f"{name} disconnected! {client_info[1]}")
                    to_remove.append(name)
            except TimeoutError:
                pass
        for dead in to_remove:
            clients.pop(dead)
        
        #udp requests
        try:
            data, client_address = server_udp_socket.recvfrom(1024)
            print(f"received udp command: {data.decode('ASCII')}")
            command = data.decode("ASCII").split(":")[0]
            if command == "REQUEST":
                client_nickname = data.decode("ASCII").split(":")[1]
                target_nickname = data.decode("ASCII").split(":")[2]
                if clients[client_nickname][1][0]==client_addr[0]:
                    print(f"REQUEST from {client_nickname} to {target_nickname}")
                    if target_nickname not in clients:
                        clients[client_nickname][0].send(f"NOT FOUND".encode("ASCII"))
                    clients[target_nickname][0].send(f"PENDING:{client_nickname}:{client_address}".encode("ASCII"))
                    waiting_list[target_nickname]=client_nickname

            elif command == "HERE":
                if clients[client_nickname][1][0]==client_addr[0]:
                    print(f"HERE from {client_nickname}")
                    clients[waiting_list[client_nickname]][0].send(f"FOUND:{client_nickname}:{client_address}".encode("ASCII"))
            elif command == "REFUSE":
                if clients[client_nickname][1][0]==client_addr[0]:
                    print(f"REFUSE from {client_nickname}")
                    clients[waiting_list[client_nickname]][0].send(f"NOT FOUND")

        except TimeoutError:
            pass


        print(f"Working{dots[dot_iter]}",end='\r')
        dot_iter+=1
        dot_iter%=len(dots)
except KeyboardInterrupt:
    print("Server closed!")
    

