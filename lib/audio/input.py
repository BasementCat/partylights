import sys
import time

import numpy as np

try:
    import pyaudio
except ImportError:
    pass

try:
    import alsaaudio
except ImportError:
    pass


class Input:
    NAME = None

    @classmethod
    def get_input(cls, config):
        name = config['Capture']['Method']
        for tcls in cls.__subclasses__():
            if tcls.NAME == name:
                return tcls(config)
        raise RuntimeError(f"No such capture method {name}")

    def __init__(self, config):
        self.config = config['Capture']
        self.frames_per_buffer = int(self.config['SampleRate'] / self.config['FPS'])

    def _get_device_index(self, valid_input_devices):
        in_device = self.config['Device']
        device_num = None
        try:
            device = int(in_device)
            device_num = device if device in valid_input_devices else None
        except (TypeError, ValueError):
            device = in_device
            for k, v in valid_input_devices.items():
                if device == v:
                    device_num = k
                    break
            if device_num is None:
                for k, v in valid_input_devices.items():
                    if device in v:
                        device_num = k
                        break

        if device_num is None:
            print(f"Invalid device {in_device} - valid devices are:")
            for k in sorted(valid_input_devices.keys()):
                print(f"{k}: {valid_input_devices[k]}")
            sys.exit(1)

        return device_num

    def get_device_index(self):
        return self._get_device_index({})

    def start(self):
        pass

    def read(self):
        pass

    def stop(self):
        pass

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


class PyAudioInput(Input):
    NAME = 'pyaudio'

    def __init__(self, config):
        try:
            pyaudio
        except NameError:
            raise RuntimeError("PyAudio is not installed")
        super().__init__(config)
        self.pa = pyaudio.PyAudio()

    def get_device_index(self):
        valid_input_devices = {}

        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info.get('maxInputChannels') > 0:
                valid_input_devices[i] = info.get('name')

        return self._get_device_index(valid_input_devices)

    def start(self):
        device_num = self.get_device_index()
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.config['SampleRate'],
            input=True,
            frames_per_buffer=self.frames_per_buffer,
            input_device_index=device_num
        )
        self.overflows = 0
        self.prev_ovf_time = time.time()

    def read(self):
        out = None
        try:
            out = self.stream.read(self.frames_per_buffer, exception_on_overflow=False)
            out = np.fromstring(out, dtype=np.int16)
            out = out.astype(np.float32)
            self.stream.read(self.stream.get_read_available(), exception_on_overflow=False)
        except KeyboardInterrupt:
            raise
        except IOError:
            self.overflows += 1
            if time.time() > self.prev_ovf_time + 1:
                self.prev_ovf_time = time.time()
                print('Audio buffer has overflowed {} times'.format(self.overflows))
        finally:
            return out

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()


class AlsaDeviceInput(Input):
    NAME = 'alsa'

    def __init__(self, config):
        try:
            alsaaudio
        except NameError:
            raise RuntimeError("AlsaAudio is not installed")
        super().__init__(config)
        self.devices = dict(enumerate(alsaaudio.pcms(alsaaudio.PCM_CAPTURE)))

    def get_device_index(self):
        return self._get_device_index(self.devices)

    def start(self):
        self.buffer = b''
        self.device = alsaaudio.PCM(
            alsaaudio.PCM_CAPTURE,
            alsaaudio.PCM_NONBLOCK,
            device=self.devices[self.get_device_index()],
        )
        # Set attributes: Mono, 44100 Hz, 16 bit little endian samples
        self.device.setchannels(1)
        self.device.setrate(self.config['SampleRate'])
        self.device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        self.device.setperiodsize(self.frames_per_buffer)

    def read(self):
        num_frames, frame_data = self.device.read()
        if num_frames:
            self.buffer += frame_data

        offset = self.frames_per_buffer * 2
        if len(self.buffer) < offset:
            return

        raw_data = self.buffer[:offset]
        self.buffer = self.buffer[offset:]
        raw_data = np.frombuffer(raw_data, dtype=np.int16)
        raw_data = raw_data.astype(np.float32)
        return raw_data
