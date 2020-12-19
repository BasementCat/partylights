import random
import logging
import json
import time

from lib.task import Task


logger = logging.getLogger(__name__)


class StateEffect:
    @classmethod
    def define(cls, mapper, index, name, when, effects, reset=None, priority=None):
        class StateEffectImpl(cls):
            pass
        StateEffectImpl.mapper = mapper
        StateEffectImpl.name = name
        StateEffectImpl.when = when
        StateEffectImpl.effects = effects
        StateEffectImpl.reset = list(effects.keys()) if reset is None else reset
        StateEffectImpl.priority = index if priority is None else priority
        return StateEffectImpl

    @classmethod
    def get_is_applicable(cls, audio, prop_last_update):
        return eval(cls.when)

    def __str__(self):
        return f"StateEffect {self.name}#{self.priority} on {self.light_name}"

    def __init__(self, light_name, orig_state=None, addl_reset=None):
        self.id = str(uuid.uuid4())
        self.light_name = light_name
        self.orig_state = orig_state or self.mapper.tasks['lights'].get_state(self.light_name)
        self.addl_reset = addl_reset or []
        self.sub_effects = {}

        self.apply()

    def apply(self):
        for fn, props in self.effects.items():
            self._mk_effect(fn, **props)

    def _mk_effect(self, fn, **props):
        for k in ('start_value', 'end_value'):
            if props.get(k) == 'random':
                # TODO: parse effects, when start/end value is random, pick a random value from enum if present, should scale as well
                props[k] = random.randint(0, 255)

        eff = self.mapper.tasks['lights'].create_effect(
            'mapper',
            self.light_name,
            dict(props, function=fn, keep_state=True),
            suppress_errors=True
        )
        if eff:
            self.sub_effects[eff.id] = eff

    def check(self):
        for id, eff in list(self.sub_effects.items()):
            if eff.done:
                del self.sub_effects[id]
        return bool(self.sub_effects)

    def unapply(self, reset_state=True):
        for eff in self.sub_effects.values():
            self.mapper.tasks['lights'].cancel_effect(eff)
        if reset_state:
            if self.orig_state:
                to_reset = set(self.reset + self.addl_reset)
                new_state = dict(filter(lambda v: v[1] is not None, ((k, self.orig_state.get(k)) for k in to_reset)))
                if new_state:
                    self.mapper.tasks['lights'].set_state('mapper', self.light_name, new_state, suppress_errors=True)
        return self.orig_state, self.reset + self.addl_reset


class MapperTask(Task):
    def setup(self):
        self.state_effects = {}
        self.applied_state_effects = {}
        self._parse_mapping(self.config)

        self.prop_last_update = {}

    def run(self, data):
        self._run_effects(data)
        self._run_mapping(data)

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

            self.state_effects.setdefault(light, [])
            for i, (k, v) in enumerate(data['StateEffects'].items()):
                self.state_effects[light].append(StateEffect.define(
                    self,
                    i,
                    k,
                    **v
                ))
            self.state_effects[light] = list(sorted(self.state_effects[light], key=lambda v: v.priority, reverse=True))

    def _run_effects(self, data):
        # TODO: somehow state effects need to update prop_last_update
        # TODO: dim isn't being reset?
        # TODO: copy effects to linked

        for light, s_eff_set in self.state_effects.items():
            # Find the state effect that's applicable to this light right now
            applied_effect = self.applied_state_effects.get(light)
            applicable_effect = None
            for eff in s_eff_set:
                if eff.get_is_applicable(data, self.prop_last_update):
                    if applied_effect and applied_effect.priority > eff.priority:
                        # Ignore lower priority effects
                        continue
                    applicable_effect = eff
                    break

            orig_state = reset = None
            if applicable_effect and applied_effect and applicable_effect.priority > applied_effect.priority:
                # An applicable effect has a higher priority than the applied effect
                # Cancel the applied effect, but don't reset state
                orig_state, reset = applied_effect.unapply(reset_state=False)
                applied_effect = None
                del self.applied_state_effects[light]

            if applied_effect:
                if applicable_effect:
                    # Applicable effect must be the applied effect, if it was lower pri it was ignored
                    # and if it was higher, applied would have been unapplied above
                    # If the effect is done, reapply it
                    if not applied_effect.check():
                        applied_effect.apply()
                else:
                    # No effect is applicable, so unapply
                    applied_effect.unapply()
                    applied_effect = None
                    del self.applied_state_effects[light]

            if applicable_effect and not applied_effect:
                # Apply this new effect
                self.applied_state_effects[light] = applied_effect = applicable_effect(
                    light,
                    orig_state,
                    reset
                )

    def _set_state_or_create_effect(self, durations, light_name, state):
        if state:
            state = state.copy()
            for k, v in list(state.items()):
                if k in durations:
                    state.pop(k)
                    effect = {
                        'function': k,
                        'end_value': v,
                        'duration': durations[k][0],
                        'keep_state': durations[k][1],
                    }
                    self.tasks['lights'].create_effect('mapper', light_name, effect, suppress_errors=True)
            if state:
                self.tasks['lights'].set_state('mapper', light_name, state, suppress_errors=True)

    def _run_mapping(self, data):
        for light_name, mapping in self.mapping.items():
            state = {}
            durations = {}
            program = mapping.get('Program')
            if not program:
                continue

            for directive in program:
                self.prop_last_update \
                    .setdefault(light_name, {}) \
                    .setdefault(directive['function'], -10000)
                # print(light_name, directive['function'], "last @", self.prop_last_update[light_name][directive['function']], ", now", time.perf_counter(), ", cooldown", mapping.get('Cooldown', {}).get(directive['function'], 0))
                if time.perf_counter() - self.prop_last_update[light_name][directive['function']] < mapping.get('Cooldown', {}).get(directive['function'], 1):
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

                if directive.get('duration'):
                    durations[directive['function']] = (directive['duration'], directive.get('keep_state', True))
                state[directive['function']] = value
                self.prop_last_update[light_name][directive['function']] = time.perf_counter()

            if state:
                self._set_state_or_create_effect(durations, light_name, state)
                for linked_name, link_config in (mapping.get('Links') or {}).items():
                    linked_state = state.copy()
                    if link_config is not True:
                        for prop in link_config.get('Invert'):
                            if prop in linked_state:
                                linked_state[prop] = 255 - linked_state[prop]
                    self._set_state_or_create_effect(durations, linked_name, linked_state)


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