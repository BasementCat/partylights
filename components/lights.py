import logging
import json
import uuid
import time

from lib.task import Task
from lib.fps import FPSCounter
from lib.pubsub import publish, subscribe
from lib.light.models import Light, DMXLight
from lib.light.dmx import DMXDevice


logger = logging.getLogger(__name__)


class Effect:
    def __init__(self, sender, light_name, function, start_value, end_value, duration, speed_config=None):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.light_name = light_name
        self.function = function
        self.start_value = start_value
        self.end_value = end_value
        self.duration = duration
        self.speed_config = speed_config

        self.start_time = time.perf_counter()

    @property
    def speed(self):
        if self.speed_config is None:
            return None
        # speed: [25, 1]
        slowest, fastest = self.speed_config
        full_move_speed = 255 - min(255, max(0, 255 * (self.duration / fastest)))
        return int(full_move_speed * (abs(self.end_value - self.start_value) / 255))

    @property
    def value(self):
        return int(min(self.end_value, ((self.end_value - self.start_value) * ((time.perf_counter() - self.start_time) / self.duration)) + self.start_value))

    @property
    def done(self):
        return (time.perf_counter() - self.start_time) >= self.duration

    @property
    def serialized(self):
        return {
            'sender': self.sender,
            'light_name': self.light_name,
            'function': self.function,
            'start_value': self.start_value,
            'end_value': self.end_value,
            'duration': self.duration,
            'speed': self.speed,
            'value': self.value,
            'done': self.done,
        }

# Effect: transition a property from a starting (or current) value to ending (or current) over a period of time
# Not exclusive but does prevent setting that property while the effect is active
# Effect has an ID, can be used to cancel
# If the property has a speed (pan/tilt), calculate the speed property value needed to achieve, send that first
# Otherwise just update per loop
# When using speed, update our knowledge of the state based on time (without sending directly) and emit as state event
# When an effect using speed is cancelled, set and send our current estimated state to the light to ensure consistency
# EffectSet: A group of effects w/ one ID for cancelling the whole set
# When a sender goes exclusive, all effects NOT from that sender are immediately cancelled
# When creating either effect/effectset, also return a subscription to an event fired when the effect is done or cancelled
# The sender would check this first in their event loop so in the case of idle/dead effects a new one can be immediately started
# Maybe use returning and allow the sender to say whether or not to reset props (like dim) so that lights don't flash in between effects


class LightOutputTask(Task):
    def setup(self):
        self.lights = {}
        self.exclusive = {}
        self.effects = {}
        for name, lconfig in self.config.get('Lights', {}).items():
            if name in self.lights:
                raise RuntimeError(f"The light {name} is defined more than once, somehow")
            self.lights[name] = Light.create_from(self.config, name, lconfig)

        self.dmx_devices = {k: DMXDevice(v) for k, v in self.config.get('DMXDevices', {}).items()}
        if not self.dmx_devices:
            raise RuntimeError("No DMX devices are configured")
        if not self.dmx_devices.get('default'):
            raise RuntimeError("The default DMX device is not configured")

        self.fps = FPSCounter('Light Server')
        self.events = subscribe('light.*')

    def _set_state(self, sender, light, state):
        light = light if hasattr(light, 'set_state') else self.lights[light]
        state = {k: v for k, v in state.items() if self.exclusive.get((light.name, k)) in (None, sender)}
        if state:
            light.set_state(**state)

    def _create_effect(self, sender, data):
        light_name = data.get('light_name')
        if not light_name or light_name not in self.lights:
            raise ValueError(f"Invalid light name: {light_name}")
        light = self.lights[light_name]
        function = data.get('function')
        if not function or function not in light.functions:
            raise ValueError(f"Invalid function: {function}")

        if self.exclusive.get((light_name, function)) not in (sender, None):
            # Someone else is exclusive for this light and/or function, so bail
            return None, None

        to_cancel = None
        for eff in self.effects.values():
            if eff.light_name == light_name and eff.function == function:
                if eff.sender != sender:
                    # Someone else already has an effect for this light/function
                    return None, None
                else:
                    # This sender has an effect - cancel it
                    to_cancel = eff
                    break

        start_value = data.get('start_value', light.state[function])
        end_value = data.get('end_value', light.state[function])
        if 'duration' not in data:
            raise ValueError("A duration is required")
        speed_config = light.functions[function].get('speed')
        # def __init__(self, sender, light_name, function, start_value, end_value, duration, speed_config=None):
        return to_cancel, Effect(
            sender,
            light_name,
            function,
            start_value,
            end_value,
            data['duration'],
            speed_config=speed_config,
        )

    def _cancel_effect(self, effect=None, light=None, function=None, explicit=False, keep_state=False):
        if not (effect or light):
            raise ValueError("Provide effect, or light and optional function")
        if isinstance(light, Light):
            light = light.name

        if effect:
            effects = [effect]
        else:
            effects = []
            for eff in self.effects.values():
                if eff.light_name == light:
                    if function and eff.function != function:
                        continue
                    effects.append(eff)

        new_state = {}
        for eff in effects:
            if explicit:
                # If the effect was explicitly cancelled, we do not need a return value
                publish('light.effect.done.' + eff.id, {'effect': eff})
                if not keep_state:
                    new_state.setdefault(eff.sender, {}).setdefault(eff.light_name, {})[eff.function] = eff.start_value
            else:
                if not publish('light.effect.done.' + eff.id, {'effect': eff}, returning=True):
                    new_state.setdefault(eff.sender, {}).setdefault(eff.light_name, {})[eff.function] = eff.start_value
            del self.effects[eff.id]
        for sender, lights in new_state.items():
            for l, s in lights.items():
                self._set_state(sender, l, s)

    def _loop(self):
        with self.fps:
            # Run effects first
            eff_state = {}
            for eff_id, eff in list(self.effects.items()):
                if eff.speed is None:
                    eff_state.setdefault(eff.sender, {}).setdefault(eff.light_name, {})[eff.function] = eff.value
                if eff.done:
                    self._cancel_effect(effect=eff)
            for sender, lights in eff_state.items():
                for l, s in lights.items():
                    self._set_state(sender, l, s)

            for ev in self.events:
                with ev:
                    cmd, args = ev.unpack_name()
                    if cmd == 'set_state':
                        light_name = args(1)
                        lights = list(filter(None, [self.lights.get(light_name)])) if light_name else list(self.lights.values())
                        for l in lights:
                            self._set_state(ev.sender, l, ev.data)
                    elif cmd == 'get':
                        what = args(1)
                        if what == 'lights':
                            ev.returning(self.lights)
                        elif what == 'state':
                            ev.returning({l.name: l.state for l in self.lights.values()})
                    elif cmd == 'exclusive':
                        if not ev.sender:
                            logger.warning("Can't go exclusive with no sender")
                        else:
                            exclusive_set = []
                            try:
                                for light_name in ev.data.get('lights') or self.lights.keys():
                                    light = self.lights.get(light_name)
                                    if not light:
                                        raise ValueError(f"No such light: {light_name}")
                                    if getattr(light, 'functions', None):
                                        for prop in ev.data.get('functions') or light.functions.keys():
                                            exclusive_set.append((light_name, prop))
                                    else:
                                        exclusive_set.append((light_name, None))

                                if ev.data.get('state'):
                                    for k in exclusive_set:
                                        if self.exclusive.get(k) and self.exclusive[k] != ev.sender:
                                            raise ValueError(f"Another client is exclusive for {k}")
                                    self.exclusive.update({k: ev.sender for k in exclusive_set})
                                else:
                                    self.exclusive.update({k: None for k in exclusive_set if self.exclusive.get(k) == ev.sender})
                            except ValueError as e:
                                logger.warning("Sender %s cannot be exclusive: %s", str(e))
                                ev.returning(False)
                            else:
                                ev.returning(True)
                                for l, f in exclusive_set:
                                    self._cancel_effect(light=l, function=f)
                    elif cmd == 'effect':
                        action = args(1)
                        if action == 'start':
                            try:
                                effects_to_cancel = []
                                new_effects = []
                                out = []
                                for effect_config in ev.data.get('effects') or []:
                                    to_cancel, new_effect = self._create_effect(ev.sender, effect_config)
                                    if to_cancel:
                                        effects_to_cancel.append(to_cancel)
                                    if new_effect:
                                        new_effects.append(new_effect)
                                    out.append(new_effect)

                                new_state = {}
                                for e in effects_to_cancel:
                                    self._cancel_effect(effect=e)

                                for e in new_effects:
                                    publish('light.effect.started.' + e.id, {'effect': e})
                                    self.effects[e.id] = e
                                    speed = e.speed
                                    if speed is not None:
                                        new_state.setdefault(e.light_name, {})['speed'] = speed
                                        new_state.setdefault(e.light_name, {})[e.function] = e.end_value
                                    else:
                                        new_state.setdefault(e.light_name, {})[e.function] = e.start_value

                                for l, s in new_state.items():
                                    self._set_state(ev.sender, l, s)

                                ev.returning((
                                    subscribe(*(f'light.effect.*.{e.id}' for e in new_effects)),
                                    out
                                ))
                            except ValueError as e:
                                logger.warning("Failed to create effects: %s", str(e))
                                ev.returning((None, False))
                            finally:
                                ev.returning((None, None))
                        elif action == 'cancel':
                            effect = self.effects.get(ev.data.get('effect'))
                            if not effect:
                                logger.error("Tried to cancel an effect that doesn't exist")
                            elif effect.sender != ev.sender:
                                logger.error("Tried to cancel an effect w/ wrong sender")
                            else:
                                self._cancel_effect(effect=effect, explicit=True, keep_state=ev.data.get('keep_state'))

            for l in self.lights.values():
                if l.diff_state:
                    # TODO: try to not receive this, somehow
                    publish('light.state.' + l.name, l.diff_state)
            DMXLight.send_batch(self.dmx_devices, self.lights.values())
