import json
import socket
import threading
import queue
import time

from . import printing
from . import terminal
from . import tools
from . import parse_command
from . import voice

TIMEOUT = 0.05

NOT_BUSY_TIME = 0.1

ALIVE_TIMER = 3
MAX_OFFLINE_TIME = 10 
RETRY_CONNECT_TIMER = 5

INTERNET_PROTOCOL = socket.AF_INET


MTU = 2048*8
DATA_COMMANDS = ['AUDIO']


try:
    with open("config.json") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
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

connection_shutdown = threading.Event()

server:socket.socket = None   

open_connections_lock = threading.Lock()
open_connections:dict[str,tools.peer] = {}
pending_connections:queue.Queue[tuple[str,addr,int]] = queue.Queue()
waiting_handshake_connections:dict[str,tuple[addr,float]] = {}
waiting_connected_connections:dict[str,tuple[addr,float]] = {}

server_connected = False


def voice_call_send_task():
    while not connection_shutdown.is_set():
        if not voice.send_audio_buffer.empty() and voice.voice_call_peer is not None:
            out_data = voice.send_audio_buffer.get(block=False)
            udp_socket.sendto("AUDIO:".encode("ASCII")+out_data,voice.voice_call_peer.address)
        else:
            time.sleep(NOT_BUSY_TIME)

def udp_recv_task():
    global open_connections
    global waiting_handshake_connections
    global waiting_connected_connections
    global pending_connections
    while not connection_shutdown.is_set():
        try:#receive messages from peers
            msg,src = udp_socket.recvfrom(MTU)
            command = tools.get_msg_command(msg)
            with open_connections_lock:
                if command in DATA_COMMANDS:
                    #printing.rprint(f"{addr}: {command}:<BINARY DATA>")
                    decoded_msg = [command]
                else:
                    #printing.rprint(f"{addr}: {msg.decode('ASCII')}")
                    decoded_msg = msg.decode("ASCII").split(":")
                if decoded_msg[0] == "CONNECT":
                    if decoded_msg[1] not in open_connections:
                        pending_connections.put((decoded_msg[1],src,1),block=False)
                elif decoded_msg[0] == "HANDSHAKE":
                    if decoded_msg[1] in waiting_handshake_connections and waiting_handshake_connections[decoded_msg[1]][0]==src:
                        waiting_handshake_connections.pop(decoded_msg[1])
                        pending_connections.put((decoded_msg[1],src,2),block=False)
                elif decoded_msg[0] == "CONNECTED":
                    if decoded_msg[1] in waiting_connected_connections and waiting_connected_connections[decoded_msg[1]][0]==src:
                        waiting_connected_connections.pop(decoded_msg[1])
                        open_connections[decoded_msg[1]] = tools.peer(decoded_msg[1],src)
                        open_connections[decoded_msg[1]].see()
                        printing.rprint(f"Connected with {decoded_msg[1]}")
                elif decoded_msg[0] == "ALIVE":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == src:
                        open_connections[decoded_msg[1]].see()
                elif decoded_msg[0] == "DISCONNECT":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == src:
                        open_connections.pop(decoded_msg[1])
                        printing.rprint(f"{decoded_msg[1]} disconnected")
                elif decoded_msg[0] == "MSG":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == src:
                        open_connections[decoded_msg[1]].see()
                        printing.rcprint(printing.format_messge(True,decoded_msg[1],decoded_msg[2]),"cyan")
                elif decoded_msg[0] == "AUDIOSTART":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == src:
                        if config["autoconnect"]:
                            udp_socket.sendto(f"AUDIOACCEPT:{config['nickname']}".encode("ASCII"),open_connections[decoded_msg[1]].address)
                            voice.start_voice_call(open_connections[decoded_msg[1]])
                            printing.rprint(f"Voice call accepted from {decoded_msg[1]}")
                elif decoded_msg[0] == "AUDIOACCEPT":
                    if decoded_msg[1] in open_connections and open_connections[decoded_msg[1]].address == src and voice.requested_peer==decoded_msg[1]:
                        open_connections[decoded_msg[1]].see()
                        voice.requested_peer = None
                        voice.start_voice_call(open_connections[decoded_msg[1]])
                        printing.rprint(f"Voice call started with {decoded_msg[1]}")
                elif decoded_msg[0] == "AUDIOSTOP":
                    if voice.voice_call_peer is not None and voice.voice_call_peer.nickname==decoded_msg[1] and voice.voice_call_peer.address == src:
                        voice.stop_voice_call()
                        printing.rprint(f"Voice call terminated by {decoded_msg[1]}")
                elif decoded_msg[0] == "AUDIO":
                    if voice.voice_call_peer is not None and voice.voice_call_peer.address == src:
                        in_data = msg[6:]
                        try:
                            voice.recv_audio_buffer.put(in_data,block=False)
                        except queue.Full:
                            pass
                    else:
                        udp_socket.sendto(f"AUDIOSTOP:{config['nickname']}".encode("ASCII"),src)
        except socket.timeout:
            pass

def server_comms_task():
    global server
    global server_connected
    global pending_connections
    while not connection_shutdown.is_set():
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
            except (socket.timeout,OSError):
                pass   
        else:#reconnect to server
            try:
                server = new_server_socket()
                server_connected = True
                printing.rcprint("Server reconnected!","green")
            except (socket.timeout, ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
                pass
            time.sleep(NOT_BUSY_TIME)

def finalize_new_connections_task():
    global open_connections
    global waiting_handshake_connections
    global waiting_connected_connections
    global pending_connections
    while not connection_shutdown.is_set():
        if not pending_connections.empty():#finish connecting with peers
            target_nickname,address,stage = pending_connections.get(block=False)
            if stage==0: #->[CONNECT] HANDSHAKE CONNECTED
                udp_socket.sendto(f"CONNECT:{config['nickname']}".encode("ASCII"),address)
                waiting_handshake_connections[target_nickname] = (address,time.time())
            elif stage==1: #CONNECT ->[HANDSHAKE] CONNECTED
                udp_socket.sendto(f"HANDSHAKE:{config['nickname']}".encode("ASCII"),address)
                waiting_connected_connections[target_nickname] = (address,time.time())
            elif stage==2: #CONNECT HANDSHAKE ->[CONNECTED]
                udp_socket.sendto(f"CONNECTED:{config['nickname']}".encode("ASCII"),address)
                with open_connections_lock:
                    open_connections[target_nickname] = tools.peer(target_nickname,address)
                printing.rprint(f"Connected with {target_nickname}")
        else:
            time.sleep(NOT_BUSY_TIME)

def retry_to_connect_task():
    global waiting_handshake_connections
    global waiting_connected_connections
    global pending_connections
    while not connection_shutdown.is_set():
        #retry connections
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

        time.sleep(RETRY_CONNECT_TIMER)

def check_offline_peer_task():
    global open_connections
    while not connection_shutdown.is_set():
        #check peer gone offline
        with open_connections_lock:
            offline_peers:list[str] = []
            for nickname, conn in open_connections.items():
                if time.time() - conn.last_seen > MAX_OFFLINE_TIME:
                    offline_peers.append(nickname)
            for nickname in offline_peers:
                open_connections.pop(nickname)
                printing.rcprint(f"{nickname} is now offline","red")

        time.sleep(MAX_OFFLINE_TIME)

def keep_alive_task():
    global open_connections
    while not connection_shutdown.is_set():
        #keep alive
        with open_connections_lock:
            for nickname, conn in open_connections.items():
                udp_socket.sendto(f"ALIVE:{config['nickname']}".encode("ASCII"),conn.address)
        time.sleep(ALIVE_TIMER)

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
        while not connection_shutdown.is_set():
            if not terminal.terminal_thread.is_alive():
                break
            else:
                command = terminal.get_input_from_terminal_if_ready()
                if command is not None:#handle input
                    parse_command.parse_command(command)

            
    except KeyboardInterrupt:
        pass
    connection_shutdown.set()
    voice.stop_voice_call()
    server.close()
    printing.rprint("Closing...",end="")

connection_thread = threading.Thread(target=connection,args=())
voice_call_send_thread = threading.Thread(target=voice_call_send_task,args=())
udp_recv_thread = threading.Thread(target=udp_recv_task,args=())
server_comms_thread = threading.Thread(target=server_comms_task,args=())
finalize_new_connections_thread = threading.Thread(target=finalize_new_connections_task,args=())
retry_to_connect_thread = threading.Thread(target=retry_to_connect_task,args=())
check_offline_peer_thread = threading.Thread(target=check_offline_peer_task,args=())
keep_alive_thread = threading.Thread(target=keep_alive_task,args=())

connection_thread_list = [
    voice_call_send_thread,
    udp_recv_thread,
    server_comms_thread,
    finalize_new_connections_thread,
    retry_to_connect_thread,
    check_offline_peer_thread,
    keep_alive_thread
]

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
        for t in connection_thread_list:
            t.start()
        connection_thread.start()
    except KeyboardInterrupt:
        printing.rprint("Goodbye!",end="\n")
        pass




