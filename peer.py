import socket
import json
import sys
import threading
import time
from typing import Callable

'''
A peer must send "CONNECT:<nickname>" to try to connect to another peer with UDP
each peer must respond with "CONNECT:<nickname>" after the first CONNECT message received
'''

TIMEOUT = 0.1
CONNECTION_ATTEMPTS = 5

with open("config.json") as config_file:
    config = json.load(config_file)

def rprint(string,end="\n> "):
    print("\r"+string,end=end)

local_address = ("0.0.0.0",25567)
if len(sys.argv)>1:
    server_address = (sys.argv[1],25566)
else:
    server_address = ("127.0.0.1",25566)

server_connected = False

open_connections:dict[str,tuple[str,int]] = {}


def string_to_address(address:str):
    address = address.strip("()")
    ip = address.split(",")[0].strip("\'")
    port = int(address.split(",")[1].strip())
    return (ip,port)

def new_server_socket():
    global server_connected
    server = socket.socket(family=socket.AF_INET,type=socket.SOCK_STREAM)    
    server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    server.settimeout(TIMEOUT)
    server.connect(server_address)
    server.send(config["nickname"].encode("ASCII"))
    return server

udp_socket = socket.socket(family=socket.AF_INET,type=socket.SOCK_DGRAM)
udp_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
udp_socket.bind(local_address)


udp_socket.settimeout(TIMEOUT)

while server_connected == False:
    try:
        server = new_server_socket()
        server_connected = True
        print("Connected!")
    except socket.timeout:
        pass

command_buffer = ""
def terminal(input_ready:threading.Event):
    global command_buffer
    try:
        while True:
            if not input_ready.is_set():
                command = input("> ")
                command_buffer = command
                input_ready.set()
    except (KeyboardInterrupt,EOFError):
        pass

input_ready = threading.Event()
input_mutex = threading.Semaphore(1)
terminal_thread = threading.Thread(target=terminal,args=(input_ready,))
terminal_thread.start()

def get_input_from_terminal(input_ready:threading.Event):
    global command_buffer
    global input_mutex
    input_mutex.acquire()
    input_ready.wait()
    ret = command_buffer
    input_ready.clear()
    input_mutex.release()
    return ret

def get_input_from_terminal_if_ready(input_ready:threading.Event):
    global command_buffer
    global input_mutex
    input_mutex.acquire()
    if input_ready.is_set():
        ret = command_buffer
        input_ready.clear()
        input_mutex.release()
        return ret
    else:
        input_mutex.release()
        return None

def get_input_from_terminal_with_timeout(input_ready:threading.Event,timeout):
    global command_buffer
    global input_mutex
    begin = time.time()
    input_mutex.acquire()
    while time.time()-begin < timeout:
        if input_ready.is_set():
            ret = command_buffer
            input_ready.clear()
            input_mutex.release()
            return ret
    input_mutex.release()
    return None

class InputTask(threading.Thread):
    input_task_mutex = threading.Semaphore(1)
    def __init__(self,pre_task:Callable,task:Callable[[str],None]):
        threading.Thread.__init__(self)
        self.pre_task = pre_task
        self.task = task
    def run(self):
        global command_buffer
        global input_mutex
        global input_ready
        InputTask.input_task_mutex.acquire()
        self.pre_task()
        self.task(get_input_from_terminal(input_ready))
        InputTask.input_task_mutex.release()

def connection(input_ready:threading.Event):
    global terminal_thread
    global server
    global server_connected
    global open_connections
    try:
        while True:
            #check commands from server
            if server_connected:
                try:
                    data = server.recv(1024)
                    if not data:
                        server.close()
                        server_connected = False
                        rprint("\033[31mServer disconnected!\033[0m")
                    else:
                        command = data.decode("ASCII").split(":")[0]
                        
                        if command == "PENDING":
                            def pre_input_task():
                                rprint(f"Accept connection from {data.decode('ASCII').split(':')[1]}? (y/N): ", end="")
                            def input_task_function(res):
                                if res == 'Y' or res == 'y':
                                    udp_socket.sendto(f"HERE:{config['nickname']}".encode("ASCII"),server_address)
                                else:
                                    udp_socket.sendto(f"REFUSE:{config['nickname']}".encode("ASCII"),server_address)
                            input_task = InputTask(pre_input_task,input_task_function)
                            input_task.start()
                        elif command == "FOUND":
                            target_nickname = data.decode("ASCII").split(":")[1]
                            address = string_to_address(data.decode("ASCII").split(":")[2])
                            rprint(f"{target_nickname} found at {address}")

                            for i in range(CONNECTION_ATTEMPTS):
                                udp_socket.sendto(f"CONNECT:{config['nickname']}".encode("ASCII"),address)
                                data,ck_address = udp_socket.recvfrom(1024)
                                if data.decode("ASCII")==f"CONNECT:{target_nickname}" and ck_address==address:
                                    udp_socket.sendto(f"CONNECT:{config['nickname']}".encode("ASCII"),address)
                                    rprint(f"Connected to {target_nickname}!")
                                    open_connections[target_nickname]=address
                                    break
                                    

                        elif command == "NOT FOUND":
                            target_nickname = data.decode("ASCII").split(":")[1]
                            rprint(f"{target_nickname} not found")
                except socket.timeout:
                    pass   
            else:
                try:
                    server = new_server_socket()
                    server_connected = True
                    rprint("\033[32mServer reconnected!\033[0m")
                except (socket.timeout, ConnectionRefusedError):
                    pass

            if not terminal_thread.is_alive():
                break
            else:
                input = get_input_from_terminal_if_ready(input_ready)
                if input is not None:#handle input
                    udp_socket.sendto(input.encode("ASCII"),server_address)
    except KeyboardInterrupt:
        pass
    server.close()
    rprint("Disconnected!",end="")

connection_thread = threading.Thread(target=connection,args=(input_ready,))
connection_thread.start()

try:
    connection_thread.join()
    terminal_thread.join()
except KeyboardInterrupt:
    pass
