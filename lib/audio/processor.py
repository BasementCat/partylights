import time

import numpy as np
from scipy.ndimage.filters import gaussian_filter1d
import aubio

from .dsp import create_mel_bank, ExpFilter


class Processor:
    def __init__(self, config):
        self.capconfig = config['Capture']
        self.config = config.get('Processors', {})

    def process(self, raw_audio, data):
        pass


class SmoothingProcessor(Processor):
    def __init__(self, config):
        super().__init__(config)
        self.config = self.config.get('Smoothing', {})
        self.rolling_history = self.config.get('RollingHistory', 2)
        self.fft_bins = self.config.get('FFTBins', 24)
        self.samples_per_frame = int(self.capconfig['SampleRate'] / self.capconfig['FPS'])
        self.y_roll = np.random.rand(self.rolling_history, self.samples_per_frame) / 1e16
        self.fft_window = np.hamming(int(self.capconfig['SampleRate'] / self.capconfig['FPS']) * self.rolling_history)
        self.mel_y, self.mel_x = create_mel_bank(
            self.capconfig['SampleRate'],
            self.rolling_history,
            self.capconfig['FPS'],
            self.fft_bins,
            self.config.get('MinFrequency', 200),
            self.config.get('MaxFrequency', 12000)
        )
        self.mel_gain = ExpFilter(np.tile(1e-1, self.fft_bins),
                         alpha_decay=0.01, alpha_rise=0.99)
        self.mel_smoothing = ExpFilter(np.tile(1e-1, self.fft_bins),
                         alpha_decay=0.5, alpha_rise=0.99)

    def process(self, raw_audio, data):
        data['audio'] = None
        if raw_audio is None:
            return
        # Normalize samples between 0 and 1
        y = raw_audio / 2.0**15
        # Construct a rolling window of audio samples
        self.y_roll[:-1] = self.y_roll[1:]
        self.y_roll[-1, :] = np.copy(y)
        y_data = np.concatenate(self.y_roll, axis=0).astype(np.float32)

        output = None

        vol = np.max(np.abs(y_data))
        if vol < self.config.get('MinVolumeThreshold', 1e-7):
            # print('No audio input. Volume below threshold. Volume:', vol)
            output = np.tile(0, self.fft_bins).astype(float)
        else:
            # Transform audio input into the frequency domain
            N = len(y_data)
            N_zeros = 2**int(np.ceil(np.log2(N))) - N
            # Pad with zeros until the next power of two
            y_data *= self.fft_window
            y_padded = np.pad(y_data, (0, N_zeros), mode='constant')
            YS = np.abs(np.fft.rfft(y_padded)[:N // 2])
            # Construct a Mel filterbank from the FFT data
            mel = np.atleast_2d(YS).T * self.mel_y.T
            # Scale data to values more suitable for visualization
            # mel = np.sum(mel, axis=0)
            mel = np.sum(mel, axis=0)
            mel = mel**2.0
            # Gain normalization
            self.mel_gain.update(np.max(gaussian_filter1d(mel, sigma=1.0)))
            mel /= self.mel_gain.value
            mel = self.mel_smoothing.update(mel)
            output = mel

        if output is not None:
            data['audio'] = output


class BeatProcessor(Processor):
    def __init__(self, config):
        super().__init__(config)
        self.config = self.config.get('Beat', {})
        self.win_s = 1024
        self.hop_s = self.frames_per_buffer = int(self.capconfig['SampleRate'] / self.capconfig['FPS'])
        self.onset_detect = aubio.onset('energy', self.win_s, self.hop_s, self.capconfig['SampleRate'])
        self.beat_detect = aubio.tempo('hfc', self.win_s, self.hop_s, self.capconfig['SampleRate'])

    def process(self, raw_audio, data):
        data.update({'is_onset': None, 'is_beat': None})
        if raw_audio is None:
            return
        data.update({
            'is_onset': True if self.onset_detect(raw_audio) else False,
            'is_beat': True if self.beat_detect(raw_audio) else False,
            })


class PitchProcessor(Processor):
    def __init__(self, config):
        super().__init__(config)
        self.config = self.config.get('Pitch', {})
        self.win_s = 1024
        self.hop_s = self.frames_per_buffer = int(self.capconfig['SampleRate'] / self.capconfig['FPS'])
        self.pitch_detect = aubio.pitch('yin', self.win_s, self.hop_s, self.capconfig['SampleRate'])
        self.pitch_detect.set_unit('midi')
        # self.pitch_detect.set_tolerance(1)
        self.buffer = []
        self.buffer_len = 3

    def process(self, raw_audio, data):
        data['pitch'] = None
        if raw_audio is None:
            return
        pitch = self.pitch_detect(raw_audio)[0]
        confidence = self.pitch_detect.get_confidence()
        # print('{:1.5f} {:s}'.format(confidence, '*' * int(pitch)))
        if confidence > 0:
            self.buffer.append(pitch)
            self.buffer = self.buffer[-self.buffer_len:]

        if len(self.buffer) == self.buffer_len:
            avg = sum(self.buffer) / len(self.buffer)
            data['pitch'] = avg


class IdleProcessor(Processor):
    def __init__(self, config):
        super().__init__(config)
        self.config = self.config.get('Idle', {})
        self.idle_since = None
        self.dead_since = None

    def process(self, raw_audio, data):
        data.update({'idle_for': None, 'dead_for': None})
        audio = data.get('audio')
        if audio is None:
            return
        threshold = self.config.get('Threshold', 0.1)
        v_sum = np.sum(audio)
        v_avg = v_sum / len(audio)
        data.update({'audio_v_sum': v_sum, 'audio_v_avg': v_avg})
        if v_avg < threshold:
            self.idle_since = self.idle_since or time.time()
            data['idle_for'] = time.time() - self.idle_since
        else:
            self.idle_since = None
            data['idle_for'] = None

        if v_sum == 0:
            self.dead_since = self.dead_since or time.time()
            data['dead_for'] = time.time() - self.dead_since
        else:
            self.dead_since = None
            data['dead_for'] = None
