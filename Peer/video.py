import cv2
import threading
import queue
import time
import numpy as np
from . import tools



WAIT_FOR_QUEUE = 0.05

SIZE = (640,480)

video_call_peer:tools.peer = None

video_stream = None

send_video_buffer:queue.Queue = queue.Queue(16)
recv_video_buffer:queue.Queue = queue.Queue(16)

stop_call:threading.Event = threading.Event()


def video_call_out(target:tools.peer,stop_call_event:threading.Event):
    while not stop_call_event.is_set():
        try:
            ret,data = video_stream.read()
            data = cv2.resize(data,SIZE)
            ret, data = cv2.imencode('.jpg', data)
            send_video_buffer.put(data,block=False)
        except queue.Full:
            time.sleep(WAIT_FOR_QUEUE)

def video_call_in(target:tools.peer,stop_call_event:threading.Event):
    while not stop_call_event.is_set():
        try:
            data = recv_video_buffer.get(block=False)
            data = cv2.imdecode(data, 1)
            cv2.imshow(f"{video_call_peer.nickname}",data)
            cv2.waitKey(1)
        except queue.Empty:
            time.sleep(WAIT_FOR_QUEUE)
    cv2.destroyAllWindows()

def start_video_call(target:tools.peer):
    global video_call_peer
    global video_stream

    if video_call_peer is not None:
        return
    
    video_stream = cv2.VideoCapture(0)

    voice_call_input_thread = threading.Thread(target=video_call_in,args=(target,stop_call))
    voice_call_output_thread = threading.Thread(target=video_call_out,args=(target,stop_call))
    voice_call_input_thread.start()
    voice_call_output_thread.start()
            
def stop_video_call():
    global video_call_peer
    global stop_call
    video_call_peer = None
    stop_call.set()
