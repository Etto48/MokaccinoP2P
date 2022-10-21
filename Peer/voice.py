import pyaudio
import wave
import queue
import threading
from . import tools

WIDTH=2
CHUNK = 512
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 3

send_audio_buffer:queue.Queue = queue.Queue()
recv_audio_buffer:queue.Queue = queue.Queue()

requested_peer:str = None


stop_call:threading.Event = threading.Event()

voice_call_peer:tools.peer = None 

def voice_call(target:tools.peer,stop_call_event:threading.Event):
    def callback(in_data, frame_count, time_info, status):
        send_audio_buffer.put(in_data)
        out_data = recv_audio_buffer.get()
        return (out_data,pyaudio.paContinue)

    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(WIDTH),channels=CHANNELS,rate=RATE,input=True,output=True,frames_per_buffer=CHUNK,stream_callback=callback)
    stream.start_stream()
    stop_call_event.wait()

    stream.stop_stream()

voice_call_thread:threading.Thread = None
def start_voice_call(target:tools.peer):
    global voice_call_peer
    global voice_call_thread
    global stop_call
    stop_call.clear()
    voice_call_peer = target
    voice_call_thread = threading.Thread(target=voice_call,args=(target,stop_call))
    voice_call_thread.start()

def stop_voice_call():
    global stop_call
    global voice_call_peer
    voice_call_peer = None
    stop_call.set()