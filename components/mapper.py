import random
import logging
import json

from lib.task import Task
from lib.fps import FPSCounter
from lib.pubsub import publish, subscribe


logger = logging.getLogger(__name__)


class MapperTask(Task):
    def setup(self):
        self.fps = FPSCounter('Mapper')
        self._parse_mapping(self.config)

        self.lights = None
        self.state = None

    def setup_inthread(self):
        self.lights = publish('light.get.lights', returning=True)
        self.state = publish('light.get.state', returning=True)
        if not (self.lights or self.state):
            raise RuntimeError("Failed to get light/state info")
        self.events = subscribe('light.state.*', 'audio')

    def _loop(self):
        with self.fps:
            for ev in self.events:
                ev.returning()
                if ev.event == 'audio':
                    self._run_mapping(ev.data)
                else:
                    cmd, args = ev.unpack_name(ignore=0)
                    if cmd == 'light':
                        what, light = args(2)
                        if what == 'state':
                            self.state[light].update(ev.data)

    def _parse_mapping(self, config):
        self.mapping = config.get('Mapping', {})
        for light, data in self.mapping.items():
            program = data.get('Program')
            while isinstance(program, str):
                program = self.mapping.get(program, {}).get('Program')
            data['Program'] = program or []

            def make_bins(bins):
                for b in bins:
                    try:
                        iter(b)
                        yield from range(b[0], b[1] + 1)
                    except:
                        yield b
            for directive in data['Program']:
                if directive.get('bins'):
                    directive['bins'] = list(make_bins(directive['bins']))

    def _run_mapping(self, data):
        with self.fps:
            for light_name, mapping in self.mapping.items():
                state = {}
                program = mapping.get('Program')
                if not program:
                    continue

                for directive in program:
                    trigger_value = None
                    trigger = directive.get('trigger', 'frequency')
                    scale_src = directive.get('scale_src')
                    threshold = directive.get('threshold', 0.25)
                    if threshold < 0:
                        thresh_cmp = lambda v: v < abs(threshold)
                    else:
                        thresh_cmp = lambda v: v >= threshold

                    freq_agg = None
                    freq_peak = None
                    if trigger == 'frequency' or scale_src == 'frequency':
                        if not data.get('audio'):
                            continue
                        try:
                            bins = [data['audio'][i] for i in directive['bins']] if directive.get('bins') else data['audio']
                        except IndexError as e:
                            logger.error("Invalid bin %s in directive %s for light %s", e, directive, light_name)
                            continue
                        agg = directive.get('aggregate', 'max')
                        if agg == 'max':
                            freq_agg = max(bins)
                        elif agg == 'avg' or agg == 'average':
                            freq_agg = sum(bins) / len(bins)
                        else:
                            logger.error("Invalid aggregate function %s in directive %s for light %s", agg, directive, light_name)
                            continue
                        freq_peak = 1 - (bins.index(max(bins)) / len(bins))


                    if trigger == 'onset':
                        if not data.get('is_onset'):
                            continue
                        trigger_value = 1
                    elif trigger == 'beat':
                        if not data.get('is_beat'):
                            continue
                        trigger_value = 1
                    elif trigger == 'frequency':
                        if freq_agg is None or not thresh_cmp(freq_agg):
                            continue
                        trigger_value = freq_agg
                    else:
                        logger.error("Invalid trigger in program for %s: %s", light_name, trigger)
                        continue

                    value = None
                    value_type = directive.get('value')
                    if not value_type:
                        value = trigger_value * 255
                    elif value_type == 'random':
                        # TODO: if the light has an enum, pick a random choice
                        value = random.randint(0, 255)
                    else:
                        try:
                            value = int(value_type)
                        except (TypeError, ValueError):
                            logger.error("Invalid value %s in directive %s for light %s", value_type, directive, light_name)
                            continue

                    if directive.get('range') == 'scaled':
                        if not scale_src:
                            scale_value = trigger_value
                        elif scale_src == 'frequency':
                            scale_value = freq_peak
                        else:
                            logger.error("Invalid scale source %s in directive %s for light %s", scale_src, directive, light_name)
                            continue

                        value *= scale_value
                    elif directive.get('range'):
                        # Must be a (min, max)
                        value = max(directive['range'][0], min(directive['range'][1], value))

                    value = int(min(255, max(0, value)))

                    # print(light_name, directive['function'], value)
                    state[directive['function']] = value
                if state:
                    publish('light.set_state.' + light_name, state, sender='mapper')
                    for linked_name, link_config in (mapping.get('Links') or {}).items():
                        linked_state = state.copy()
                        if link_config is not True:
                            for prop in link_config.get('Invert'):
                                if prop in linked_state:
                                    linked_state[prop] = 255 - linked_state[prop]
                        publish('light.set_state.' + linked_name, linked_state, sender='mapper')


# back_1:
#   Program:
#     - {trigger: onset, function: pan, value: random, range: scaled, scale_src: frequency}
#     - {trigger: onset, function: tilt, value: random, range: scaled, scale_src: frequency}
#     - {trigger: frequency, bins: [[13, 20]], function: gobo, value: random, threshold: 0.5}
#     - {trigger: frequency, bins: [[19, 23]], function: strobe, value: scaled, scale_src: tempo, threshold: 0.7, reset: beat}
#     - {trigger: frequency, bins: [[0, 23]], function: color, value: random, threshold: 0.9}
#   Links:
#     mid_1:
#       Invert: [pan]
#     mid_4: true

# back_2:
#   Program: back_1
#   Links:
#     mid_2: true
#     mid_3:
#       Invert: [pan]

# front_1:
#   Program:
#     - {trigger: onset, function: pan, value: random, range: scaled, scale_src: frequency}
#     - {trigger: onset, function: tilt, value: random, range: scaled, scale_src: frequency}
#     - {trigger: frequency, bins: [[19, 23]], function: strobe, value: scaled, scale_src: tempo, threshold: 0.7, reset: beat}
#     - {trigger: frequency, bins: [[19, 23]], function: white, value: 255, threshold: 0.7}
#     - {trigger: frequency, bins: [[19, 23]], function: white, value: 0, threshold: 0.7, duration: 0.32}
#     - {trigger: frequency, bins: [[0, 23]], function: dim, value: scaled, threshold: 0.15}
#     - {trigger: frequency, bins: [[0, 3]], function: red, value: scaled, threshold: 0.1, duration: 0.25}
#     - {trigger: frequency, bins: [[4, 12]], function: green, value: scaled, threshold: 0.1, duration: 0.25}
#     - {trigger: frequency, bins: [[13, 23]], function: blue, value: scaled, threshold: 0.1, duration: 0.25}
#     - {trigger: frequency, bins: [[0, 23]], function: uv, value: 255, threshold: -0.1, duration: 0.125}
#     - {trigger: frequency, bins: [[0, 23]], function: uv, value: 0, threshold: 0.1}
#   Links:
#     front_2: true

# laser:
#   Program:
#     - {trigger: beat, function: pattern}
#     - {trigger: onset, function: x}
#     - {trigger: onset, function: 'y'}
#     - {trigger: beat, function: pattern_size}