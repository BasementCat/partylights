import random
import logging
import json
import time

from lib.task import Task


logger = logging.getLogger(__name__)


class StateEffect:
    def __init__(self, mapper, index, name, light_name, when, effects, keep_state=False, reset=None, priority=None):
        self.mapper = mapper
        self.name = name
        self.light_name = light_name
        self.when = when
        self.effects = effects
        self.keep_state = keep_state
        self.reset = list(self.effects.keys()) if reset is None else reset
        self.priority = index if priority is None else priority

        # TODO: parse effects, when start/end value is random, pick a random value, should scale as well

        self.orig_state = None
        self.is_applied = False
        self.sub_effects = {}

    def __str__(self):
        return f"StateEffect {self.name}#{self.priority} on {self.light_name}" + (' [applied]' if self.is_applied else '')

    def get_is_applicable(self, audio, prop_last_update):
        return eval(self.when)

    def apply(self, orig_state=None):
        self.is_applied = True

        if self.orig_state is None:
            self.orig_state = orig_state or self.mapper.tasks['lights'].get_state(self.light_name)

        def mk_effect(e):
            args = dict(e[1])
            for k in ('start_value', 'end_value'):
                if args.get(k) == 'random':
                    args[k] = random.randint(0, 255)

            eff = self.mapper.tasks['lights'].create_effect(
                'mapper',
                self.light_name,
                dict(args, function=e[0], keep_state=True),
                suppress_errors=True
            )
            if eff:
                self.sub_effects[eff.id] = eff

        for item in self.effects.items():
            mk_effect(item)

    def check(self):
        for id, eff in list(self.sub_effects.items()):
            if eff.done:
                del self.sub_effects[id]
        return bool(self.sub_effects)

    def unapply(self, reset_state=True):
        self.is_applied = False
        out = None
        for eff in self.sub_effects.values():
            self.mapper.tasks['lights'].cancel_effect(eff)
        self.sub_effects = {}
        if reset_state:
            if self.orig_state:
                out = self.orig_state
                new_state = dict(filter(lambda v: v[1] is not None, ((k, self.orig_state.get(k)) for k in self.reset)))
                if new_state:
                    self.mapper.tasks['lights'].set_state('mapper', self.light_name, new_state, suppress_errors=True)
        self.orig_state = None
        return out


class MapperTask(Task):
    def setup(self):
        self.state_effects = {}
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
                self.state_effects[light].append(StateEffect(
                    self,
                    i,
                    k,
                    light,
                    **v
                ))
            self.state_effects[light] = list(sorted(self.state_effects[light], key=lambda v: v.priority, reverse=True))

    def _run_effects(self, data):
        # TODO: somehow state effects need to update prop_last_update
        # TODO: dim isn't being reset?
        # TODO: copy effects to linked
        for s_eff_set in self.state_effects.values():
            first_applicable = None
            applied_effect = None
            for eff in s_eff_set:
                if first_applicable is None and eff.get_is_applicable(data, self.prop_last_update):
                    first_applicable = eff
                if applied_effect is None and eff.is_applied:
                    applied_effect = eff
                if first_applicable and applied_effect:
                    break

            orig_state = None
            if applied_effect:
                # An effect is already applied
                if applied_effect.check() and applied_effect.get_is_applicable(data, self.prop_last_update):
                    if not first_applicable or first_applicable is applied_effect:
                        continue
                else:
                    # The effect is done, so it likely should be ended
                    if applied_effect is first_applicable:
                        # Still applicable - reapply
                        logger.debug("Reapplying still applicable %s", applied_effect)
                        applied_effect.apply()
                        continue
                    # Not applicable, so end
                    logger.debug("Unapplying non-applicable %s", applied_effect)
                    orig_state = applied_effect.unapply(reset_state=not bool(first_applicable))
                    applied_effect = None

            if first_applicable:
                if applied_effect:
                    logger.debug("Cancelling %s", applied_effect)
                    orig_state = applied_effect.unapply(reset_state=False)
                logger.debug("Applying new %s", first_applicable)
                first_applicable.apply(orig_state)

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