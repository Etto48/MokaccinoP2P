import pyaudio
import audioop
import queue
import threading
from . import tools

QUALITY_DIV = 2

WIDTH=2
CHUNK = 1024*8//QUALITY_DIV
CHANNELS = 1
RATE = 44100//QUALITY_DIV
VOLUME_THRESHOLD = 45

p:pyaudio.PyAudio = None
stream:pyaudio.Stream = None

send_audio_buffer:queue.Queue = queue.Queue(16)
recv_audio_buffer:queue.Queue = queue.Queue(16)

requested_peer:str = None


stop_call:threading.Event = threading.Event()

voice_call_peer:tools.peer = None 

def voice_call_out(target:tools.peer,stop_call_event:threading.Event):
    global p
    while not stop_call_event.is_set():
        try:
            data = stream.read(CHUNK)
            volume = audioop.rms(data,WIDTH)
            if volume > VOLUME_THRESHOLD:
                send_audio_buffer.put(data,block=False)
        except queue.Full:
            pass


def voice_call_in(target:tools.peer,stop_call_event:threading.Event):
    global p
    while not stop_call_event.is_set():
        try:
            data = recv_audio_buffer.get(block=False)
            stream.write(data)
        except queue.Empty:
            pass
        

voice_call_thread:threading.Thread = None
def start_voice_call(target:tools.peer):
    global voice_call_peer
    global voice_call_thread
    global stop_call
    global p
    global stream
    if voice_call_peer is not None:
        return

    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(WIDTH),channels=CHANNELS,rate=RATE,input=True,output=True,frames_per_buffer=CHUNK)

    stop_call.clear()
    voice_call_peer = target
    voice_call_input_thread = threading.Thread(target=voice_call_in,args=(target,stop_call))
    voice_call_output_thread = threading.Thread(target=voice_call_out,args=(target,stop_call))
    voice_call_input_thread.start()
    voice_call_output_thread.start()

def stop_voice_call():
    global stop_call
    global voice_call_peer
    voice_call_peer = None
    stop_call.set()