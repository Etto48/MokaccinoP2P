from numpy import ndarray
import pyaudio
import audioop
import queue
import threading
import pyflac
import numpy as np
from . import tools

QUALITY_DIV = 4

WIDTH=2
CHUNK = 128
CHANNELS = 1
RATE = 44100
VOLUME_THRESHOLD = 50
ENABLE_COMPRESSION = False
COMPRESSION_LEVEL = 5

p:pyaudio.PyAudio = None
stream:pyaudio.Stream = None

send_audio_buffer:queue.Queue = queue.Queue(16)
recv_audio_buffer:queue.Queue = queue.Queue(16)

requested_peer:str = None


stop_call:threading.Event = threading.Event()

voice_call_peer:tools.peer = None 

class AudioEncoder(threading.Thread):
    def __init__(self):
        super().__init__()
        self.queue:queue.SimpleQueue = queue.SimpleQueue()
        self.encoder = pyflac.StreamEncoder(
            sample_rate=RATE,
            write_callback=self.callback,
            compression_level=COMPRESSION_LEVEL,
            blocksize=0
        )

    def start(self):
        self.running = True
        super().start()
    def stop(self):
        self.running = False

    def callback(self,buffer,num_bytes,num_samples,current_frame):
        global send_audio_buffer
        try:
            send_audio_buffer.put(buffer,block=False)
        except queue.Full:
            pass
    
    def run(self):
        while self.running:
            while not self.queue.empty():
                data = np.frombuffer(self.queue.get(), dtype=np.int16)
                samples = data.reshape((len(data) // CHANNELS, CHANNELS))
                self.encoder.process(samples)
        self.encoder.finish()
    
class AudioDecoder(threading.Thread):
    def __init__(self):
        super().__init__()
        self.queue:queue.SimpleQueue = queue.SimpleQueue()
        self.decoder = pyflac.StreamDecoder(
            write_callback=self.callback
        )
        
    def start(self):
        self.running = True
        super().start()
    def stop(self):
        self.running = False

    def callback(self,samples:ndarray,num_bytes,num_samples,current_frame):
        try:
            buffer = samples.tobytes()
            self.queue.put(buffer,block=False)
        except queue.Full:
            pass
    
    def run(self):
        global recv_audio_buffer
        while self.running:
            while not recv_audio_buffer.empty():
                data = recv_audio_buffer.get()
                self.decoder.process(data)
        self.decoder.finish()


def voice_call_out(target:tools.peer,stop_call_event:threading.Event):
    global p
    while not stop_call_event.is_set():
        data = stream.read(CHUNK,exception_on_overflow=False)
        volume = audioop.rms(data,WIDTH)
        if volume > VOLUME_THRESHOLD:
            if ENABLE_COMPRESSION:
                encoder_thread.queue.put(data,block=False)
            else:
                try:
                    send_audio_buffer.put(data,block=False)
                except queue.Full:
                    pass


def voice_call_in(target:tools.peer,stop_call_event:threading.Event):
    while not stop_call_event.is_set():
        try:
            if ENABLE_COMPRESSION:
                data = decoder_thread.queue.get(block=False)
            else:
                data = recv_audio_buffer.get(block=False)
            stream.write(data)
        except queue.Empty:
            pass

encoder_thread:AudioEncoder = None
decoder_thread:AudioDecoder = None        

voice_call_thread:threading.Thread = None
def start_voice_call(target:tools.peer):
    global voice_call_peer
    global voice_call_thread
    global encoder_thread
    global decoder_thread
    global stop_call
    global p
    global stream
    if voice_call_peer is not None:
        return

    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(WIDTH),channels=CHANNELS,rate=RATE,input=True,output=True,frames_per_buffer=CHUNK)

    stop_call.clear()
    voice_call_peer = target
    if ENABLE_COMPRESSION:
        encoder_thread = AudioEncoder()
        decoder_thread = AudioDecoder()
        encoder_thread.start()
        decoder_thread.start()
    voice_call_input_thread = threading.Thread(target=voice_call_in,args=(target,stop_call))
    voice_call_output_thread = threading.Thread(target=voice_call_out,args=(target,stop_call))
    voice_call_input_thread.start()
    voice_call_output_thread.start()

def stop_voice_call():
    global stop_call
    global voice_call_peer
    global encoder_thread
    global decoder_thread
    voice_call_peer = None

    if encoder_thread is not None:
        encoder_thread.stop()
    if decoder_thread is not None:
        decoder_thread.stop()
    stop_call.set()