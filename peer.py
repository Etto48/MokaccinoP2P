import socket
import upnpy
import cProfile
from Peer import terminal
from Peer import connection

def main():
    terminal.start()
    connection.start()    
    try:
        if terminal.terminal_thread.is_alive():
            terminal.terminal_thread.join()
        if connection.connection_thread.is_alive():
            connection.connection_thread.join()
    except KeyboardInterrupt:
        pass   


if __name__=="__main__":
    cProfile.run("main()")
    #main()