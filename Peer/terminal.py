import threading
import time
from typing import Callable

command_buffer = ""
def terminal(input_ready:threading.Event):
    global command_buffer
    try:
        while command_buffer!="exit":
            if not input_ready.is_set():
                command = input("\r> ")
                command_buffer = command
                input_ready.set()
    except (KeyboardInterrupt,EOFError,ValueError):
        print("\r",end="")

input_ready = threading.Event()
input_lock = threading.Lock()
terminal_thread = threading.Thread(target=terminal,args=(input_ready,))

def start():
    global terminal_thread
    terminal_thread.start()

def get_input_from_terminal():
    global command_buffer
    global input_lock
    global input_ready
    with input_lock:
        input_ready.wait()
        ret = command_buffer
        input_ready.clear()
    return ret

def get_input_from_terminal_if_ready():
    global command_buffer
    global input_lock
    global input_ready
    with input_lock:
        if input_ready.is_set():
            command_buffer
            input_ready.clear()
            return command_buffer
        else:
            return None

def get_input_from_terminal_with_timeout(timeout):
    global command_buffer
    global input_lock
    global input_ready
    begin = time.time()
    with input_lock:
        while time.time()-begin < timeout:
            if input_ready.is_set():
                ret = command_buffer
                input_ready.clear()
                return ret
            else:
                time.sleep(0.1)
    return None

class InputTask(threading.Thread):
    input_task_lock = threading.Lock()
    def __init__(self,pre_task:Callable,task:Callable[[str],None]):
        threading.Thread.__init__(self)
        self.pre_task = pre_task
        self.task = task
    def run(self):
        global command_buffer
        global input_lock
        global input_ready
        with InputTask.input_task_lock:
            self.pre_task()
            self.task(get_input_from_terminal(input_ready))