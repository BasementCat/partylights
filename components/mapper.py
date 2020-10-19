import random
import logging
import json
import time

from lib.task import Task
from lib.fps import FPSCounter
from lib.pubsub import publish, subscribe


logger = logging.getLogger(__name__)


class StateEffect:
    def __init__(self, mapper, index, name, light_name, when, effects, keep_state=False, reset=None, priority=None):
        self.mapper = mapper
        self.name = name
        self.light_name = light_name
        self.when = when
        self.effects = effects
        self.keep_state = keep_state
        self.reset = reset or list(self.effects.keys())
        self.priority = index if priority is None else priority

        # TODO: parse effects, when start/end value is random, pick a random value, should scale as well

        self.orig_state = None
        self.sub = None
        self.sub_effects = {}

    def get_is_applicable(self, audio, prop_last_update):
        return eval(self.when)

    @property
    def is_applied(self):
        return bool(self.sub)

    def apply(self):
        if self.orig_state is None:
            self.orig_state = dict(filter(lambda v: v[1] is not None, ((k, self.mapper.state.get(self.light_name, {}).get(k)) for k in self.reset)))

        def mk_effect(e):
            args = dict(e[1])
            for k in ('start_value', 'end_value'):
                if args.get(k) == 'random':
                    args[k] = random.randint(0, 255)
            return dict(
                light_name=self.light_name,
                function=e[0],
                **args
            )
        sub, effects = publish('light.effect.start', {'effects': list(map(mk_effect, self.effects.items()))}, returning=True)
        self.sub = sub
        self.sub_effects = {e.id: e for e in effects}

    def check(self):
        if self.sub:
            ev = self.sub.get(0)
            if ev:
                cmd, args = ev.unpack_name(ignore=2)
                action, id = args(2)
                if action in ('cancelled', 'done'):
                    del self.sub_effects[id]
            if not self.sub_effects:
                self.sub = None
        return self.is_applied

    def unapply(self):
        if self.sub:
            self.sub.unsubscribe()
            self.sub = None
        for k in self.sub_effects.keys():
            # TODO: not sure if keep state applies here?
            publish('light.effect.cancel', {'effect': k, 'keep_state': self.keep_state})
        self.sub_effects = {}
        if self.orig_state:
            publish('light.set_state.' + self.light_name, self.orig_state)
        self.orig_state = None


class MapperTask(Task):
    def setup(self):
        self.fps = FPSCounter('Mapper')
        self.state_effects = []
        self._parse_mapping(self.config)

        self.lights = None
        self.state = None
        self.prop_last_update = {}

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
                    self._run_effects(ev.data)
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

            cooldown = data.get('Cooldown')
            while isinstance(cooldown, str):
                cooldown = self.mapping.get(cooldown, {}).get('Cooldown')
            data['Cooldown'] = cooldown or {}

            state_effects = data.get('StateEffects')
            while isinstance(state_effects, str):
                state_effects = self.mapping.get(state_effects, {}).get('StateEffects')
            data['StateEffects'] = state_effects or {}

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

            for i, (k, v) in enumerate(data['StateEffects'].items()):
                self.state_effects.append(StateEffect(
                    self,
                    i,
                    k,
                    light,
                    **v
                ))
            self.state_effects = list(sorted(self.state_effects, key=lambda v: v.priority, reverse=True))

    def _run_effects(self, data):
        # Determine what effect is currently applied
        applied_effect = (list(filter(lambda e: e.is_applied, self.state_effects)) or [None])[0]
        # Determine what effects are applicable, they are already ordered by priority
        applicable_effects = list(filter(lambda e: e.get_is_applicable(data, self.prop_last_update), self.state_effects))

        if applied_effect and (applied_effect not in applicable_effects or applicable_effects.index(applied_effect) > 0):
            # Either the applied effect is no longer applicable, or another higher priority effect is now applicable
            applied_effect.unapply()
            applied_effect = None

        if applied_effect:
            # Run & check status
            if not applied_effect.check():
                # No longer applied, but if it's still applicable, re-apply
                if applied_effect in applicable_effects:
                    applied_effect.apply()
                else:
                    applied_effect.unapply()
                    applied_effect = None

        if not applied_effect and applicable_effects:
            applicable_effects[0].apply()

        # If the currently applied effect's index in app
        for e in self.state_effects:
            # First - if 
            if e.get_is_applicable(data, self.prop_last_update):
                if e.is_applied:
                    # Currently running state effect - check & unapply if necessary
                    if not e.check():
                        # Time to unapply
                        e.unapply()

    def _run_mapping(self, data):
        with self.fps:
            for light_name, mapping in self.mapping.items():
                state = {}
                program = mapping.get('Program')
                if not program:
                    continue

                for directive in program:
                    self.prop_last_update \
                        .setdefault(light_name, {}) \
                        .setdefault(directive['function'], -10000)
                    # print(light_name, directive['function'], "last @", self.prop_last_update[light_name][directive['function']], ", now", time.perf_counter(), ", cooldown", mapping.get('Cooldown', {}).get(directive['function'], 0))
                    if time.perf_counter() - self.prop_last_update[light_name][directive['function']] < mapping.get('Cooldown', {}).get(directive['function'], 0):
                        continue

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
                    self.prop_last_update[light_name][directive['function']] = time.perf_counter()
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