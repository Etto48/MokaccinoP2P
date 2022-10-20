import pyaudio
import wave
import queue
import threading
from . import tools

CHUNK = 1024-8
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 3

send_audio_buffer:queue.Queue = queue.Queue()
recv_audio_buffer:queue.Queue = queue.Queue()

requested_peer:str = None


stop_call:threading.Event = threading.Event()

voice_call_peer:tools.peer = None 

def voice_call(target:tools.peer,stop_call_event:threading.Event):
    def callback_send(in_data, frame_count, time_info, status):
        send_audio_buffer.put(in_data)
        return (in_data,pyaudio.paContinue)

    def callback_recv(in_data, frame_count, time_info, status):
        in_data = recv_audio_buffer.get()
        return (in_data,pyaudio.paContinue)

    p = pyaudio.PyAudio()
    stream_out = p.open(format=FORMAT,channels=1,rate=RATE,input=True,output=False,stream_callback=callback_send)
    stream_in = p.open(format=FORMAT,channels=1,rate=RATE,input=False,output=True,stream_callback=callback_recv)
    stream_out.start_stream()
    stream_in.start_stream()
    
    stop_call_event.wait()
    stream_out.stop_stream()
    stream_in.stop_stream()

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
    voice_call_peer = None
    stop_call.set()