import socket
import upnpy
from Peer import terminal
from Peer import connection


if __name__=="__main__":
    terminal.start()
    connection.start()

    
    try:
        if terminal.terminal_thread.is_alive():
            terminal.terminal_thread.join()
        if connection.connection_thread.is_alive():
            connection.connection_thread.join()
    except KeyboardInterrupt:
        pass    