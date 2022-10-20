
import json
import socket
import threading
import sys
import queue
import time
from xml.dom import NotFoundErr

from parso import parse
from . import printing
from . import terminal
from . import tools
from . import parse_command

TIMEOUT = 0.1

ALIVE_TIMER = 3
MAX_OFFLINE_TIME = 10 
RETRY_CONNECT_TIMER = 5

INTERNET_PROTOCOL = socket.AF_INET


MTU = 1024

try:
    with open("config.json") as config_file:
        config = json.load(config_file)
except NotFoundErr:
    printing.rcprint("No config file found","red",end="\n")
    exit()

if INTERNET_PROTOCOL == socket.AF_INET:
    local_address = ("0.0.0.0",config["port"])
    server_address = (config["server"],25566)
    addr = tuple[str,int]
elif INTERNET_PROTOCOL == socket.AF_INET6:
    local_address = ("::",config["port"],0,0)
    server_address = (config["server"],25566,0,0)
    addr = tuple[str,int,int,int]

server:socket.socket = None   

class peer:
    def __init__(self,nickname:str,address:addr):
        self.last_seen = 0
        self.nickname = nickname
        self.address = address
    def see(self):
        self.last_seen = time.time()


open_connections:dict[str,peer] = {}
pending_connections:queue.Queue[tuple[str,addr,int]] = queue.Queue()
waiting_handshake_connections:dict[str,tuple[addr,float]] = {}
waiting_connected_connections:dict[str,tuple[addr,float]] = {}


server_connected = False
def new_server_socket():
    global server_connected
    server = socket.socket(family=INTERNET_PROTOCOL,type=socket.SOCK_STREAM)    
    server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    server.settimeout(TIMEOUT)
    server.connect(server_address)
    server.send(config["nickname"].encode("ASCII"))
    return server



def connection():
    global server
    global server_connected
    global open_connections
    global waiting_handshake_connections
    global waiting_connected_connections
    global pending_connections
    last_keep_alive = 0
    last_checked_keep_alive = 0
    last_check_connection = 0
    need_to_check_alive = False
    try:
        while True:
            #check commands from server
            if server_connected:
                try:
                    data = server.recv(MTU)
                    if not data:
                        server.close()
                        server_connected = False
                        printing.rcprint("Server disconnected!","red")
                    else:
                        command = data.decode("ASCII").split(":")[0]
                        
                        if command == "PENDING":
                            if "autoconnect" in config and config["autoconnect"]:
                                udp_socket.sendto(f"HERE:{config['nickname']}".encode("ASCII"),server_address)
                            else:
                                def pre_input_task():
                                    printing.rprint(f"Accept connection from {data.decode('ASCII').split(':')[1]}? (y/N): ", end="")
                                def input_task_function(res):
                                    if res == 'Y' or res == 'y':
                                        udp_socket.sendto(f"HERE:{config['nickname']}".encode("ASCII"),server_address)
                                    else:
                                        udp_socket.sendto(f"REFUSE:{config['nickname']}".encode("ASCII"),server_address)
                                input_task = terminal.InputTask(pre_input_task,input_task_function)
                                input_task.start()
                        elif command == "FOUND":
                            target_nickname = data.decode("ASCII").split(":")[1]
                            address_string = ":".join(data.decode("ASCII").split(":")[2:])
                            address = tools.string_to_address(address_string)
                            printing.rprint(f"{target_nickname} found at {address}")

                            pending_connections.put((target_nickname,address,0),block=False)                                    
                                

                        elif command == "NOT FOUND":
                            target_nickname = data.decode("ASCII").split(":")[1]
                            printing.rprint(f"{target_nickname} not found")
                except socket.timeout:
                    pass   
            else:#reconnect to server
                try:
                    server = new_server_socket()
                    server_connected = True
                    printing.rcprint("Server reconnected!","green")
                except (socket.timeout, ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
                    pass
            
            try:#receive messages from peers
                msg,addr = udp_socket.recvfrom(MTU)
                #printing.rprint(f"{addr}: {msg.decode('ASCII')}")
                decoded_msg = msg.decode("ASCII").split(":")
                if decoded_msg[0] == "CONNECT":
                    if decoded_msg[1] not in open_connections:
                        pending_connections.put((decoded_msg[1],addr,1),block=False)
                elif decoded_msg[0] == "HANDSHAKE":
                    if decoded_msg[1] in waiting_handshake_connections and waiting_handshake_connections[decoded_msg[1]][0]==addr:
                        waiting_handshake_connections.pop(decoded_msg[1])
                        pending_connections.put((decoded_msg[1],addr,2),block=False)
                elif decoded_msg[0] == "CONNECTED":
                    if decoded_msg[1] in waiting_connected_connections and waiting_connected_connections[decoded_msg[1]][0]==addr:
                        waiting_connected_connections.pop(decoded_msg[1])
                        open_connections[decoded_msg[1]] = peer(decoded_msg[1],address)
                        open_connections[decoded_msg[1]].see()
                        printing.rprint(f"Connected with {decoded_msg[1]}")
                elif decoded_msg[0] == "ALIVE":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == addr:
                        open_connections[decoded_msg[1]].see()
                elif decoded_msg[0] == "DISCONNECT":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == addr:
                        open_connections.pop(decoded_msg[1])
                        printing.rprint(f"{decoded_msg[1]} disconnected")
                elif decoded_msg[0] == "MSG":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == addr:
                        open_connections[decoded_msg[1]].see()
                        printing.rcprint(printing.format_messge(True,decoded_msg[1],decoded_msg[2]),"cyan")
            except socket.timeout:
                pass

            while not pending_connections.empty():#finish connecting with peers
                target_nickname,address,stage = pending_connections.get(block=False)
                if stage==0: #->[CONNECT] HANDSHAKE CONNECTED
                    udp_socket.sendto(f"CONNECT:{config['nickname']}".encode("ASCII"),address)
                    waiting_handshake_connections[target_nickname] = (address,time.time())
                elif stage==1: #CONNECT ->[HANDSHAKE] CONNECTED
                    udp_socket.sendto(f"HANDSHAKE:{config['nickname']}".encode("ASCII"),address)
                    waiting_connected_connections[target_nickname] = (address,time.time())
                elif stage==2: #CONNECT HANDSHAKE ->[CONNECTED]
                    udp_socket.sendto(f"CONNECTED:{config['nickname']}".encode("ASCII"),address)
                    open_connections[target_nickname] = peer(target_nickname,address)
                    printing.rprint(f"Connected with {decoded_msg[1]}")

            #check peer gone offline
            if need_to_check_alive and time.time() - last_checked_keep_alive > MAX_OFFLINE_TIME:
                offline_peers:list[str] = []
                for nickname, conn in open_connections.items():
                    if time.time() - conn.last_seen > MAX_OFFLINE_TIME:
                        offline_peers.append(nickname)
                for nickname in offline_peers:
                    open_connections.pop(nickname)
                    printing.rcprint(f"{nickname} is now offline","red")
                last_checked_keep_alive = time.time()

            #keep alive
            if time.time() - last_keep_alive > ALIVE_TIMER:
                for nickname, conn in open_connections.items():
                    udp_socket.sendto(f"ALIVE:{config['nickname']}".encode("ASCII"),conn.address)
                last_keep_alive = time.time()
                if not need_to_check_alive:
                    last_checked_keep_alive = time.time()
                    need_to_check_alive = True

            if time.time() - last_check_connection > RETRY_CONNECT_TIMER:
                to_remove:list[str] = []
                for nickname,(address,last_seen) in waiting_connected_connections.items():
                    if time.time() - last_seen > RETRY_CONNECT_TIMER:
                        to_remove.append(nickname)
                for nickname in to_remove:
                    pending_connections.put((nickname,waiting_connected_connections[nickname][0],1),block=False)
                    waiting_connected_connections.pop(nickname)
                to_remove = []
                for nickname,(address,last_seen) in waiting_handshake_connections.items():
                    if time.time() - last_seen > RETRY_CONNECT_TIMER:
                        to_remove.append(nickname)
                for nickname in to_remove:
                    pending_connections.put((nickname,waiting_handshake_connections[nickname][0],0),block=False)
                    waiting_handshake_connections.pop(nickname)
                    


            if not terminal.terminal_thread.is_alive():
                break
            else:
                command = terminal.get_input_from_terminal_if_ready()
                if command is not None:#handle input
                    parse_command.parse_command(command)

            
    except KeyboardInterrupt:
        pass
    server.close()
    printing.rprint("Disconnected!",end="")

connection_thread = threading.Thread(target=connection,args=())

def start():
    global connection_thread
    global udp_socket
    global local_address
    global server
    global server_connected

    try:
        udp_socket = socket.socket(family=INTERNET_PROTOCOL,type=socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        udp_socket.bind(local_address)


        udp_socket.settimeout(TIMEOUT)

        while server_connected == False:
            try:
                server = new_server_socket()
                server_connected = True
                printing.rprint("Connected!")
            except socket.timeout:
                pass
        connection_thread.start()
    except KeyboardInterrupt:
        printing.rprint("Goodbye!",end="\n")
        pass




