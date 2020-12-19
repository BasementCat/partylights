import logging
import json
import uuid
import time

from lib.task import Task
from lib.light.models import Light, DMXLight
from lib.light.dmx import DMXDevice


logger = logging.getLogger(__name__)


class Effect:
    def __init__(self, sender, light_name, function, start_value, end_value, duration, keep_state=False, speed_config=None, orig_speed=None):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.light_name = light_name
        self.function = function
        self.start_value = start_value
        self.end_value = end_value
        self.duration = duration
        self.speed_config = speed_config
        self.keep_state = keep_state
        self.orig_speed = orig_speed

        self.is_new = True
        self.is_cancelled = False
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
        return self.is_cancelled or (time.perf_counter() - self.start_time) >= self.duration

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

        self.state_queue = []

        for name, lconfig in self.config.get('Lights', {}).items():
            if name in self.lights:
                raise RuntimeError(f"The light {name} is defined more than once, somehow")
            self.lights[name] = Light.create_from(self.config, name, lconfig)

        self.dmx_devices = {k: DMXDevice(v) for k, v in self.config.get('DMXDevices', {}).items()}
        if not self.dmx_devices:
            raise RuntimeError("No DMX devices are configured")
        if not self.dmx_devices.get('default'):
            raise RuntimeError("The default DMX device is not configured")

    def set_state(self, sender, light_or_name, state, suppress_errors=False):
        try:
            if isinstance(light_or_name, str):
                light = self.lights.get(light_or_name)
                if not light:
                    raise ValueError(f"No such light: {light_or_name}")
            else:
                light = light_or_name

            state = {k: v for k, v in state.items() if self.exclusive.get((light.name, k)) in (None, sender)}
            if state:
                self.state_queue.append((light.name, state))
            return state
        except (ValueError, RuntimeError) as e:
            if suppress_errors:
                logger.error("Can't set state for %s:%s: %s: %s\n%s", sender, light_or_name, e.__class__.__name__, str(e), state)
            else:
                raise

    def _render_state_queue(self, light=None, clear=False):
        out = {}
        for light_, state in self.state_queue:
            out.setdefault(light_, {}).update(state)
        if clear and not light:
            self.state_queue = []
        if light:
            return out.get(light, {})
        return out

    def get_state(self, light_or_name, suppress_errors=False):
        try:
            if isinstance(light_or_name, str):
                light = self.lights.get(light_or_name)
                if not light:
                    raise ValueError(f"No such light: {light_or_name}")
            else:
                light = light_or_name

            out = light.state.copy()
            out.update(self._render_state_queue(light=light.name))
            return out
        except (ValueError, RuntimeError) as e:
            if suppress_errors:
                logger.error("Can't get state for %s: %s: %s", light_or_name, e.__class__.__name__, str(e))
            else:
                raise

    def create_effect(self, sender, light_name, data, override=False, suppress_errors=False):
        try:
            if not light_name or light_name not in self.lights:
                raise ValueError(f"Invalid light name: {light_name}")
            light = self.lights[light_name]
            function = data.get('function')
            if not function or function not in light.functions:
                raise ValueError(f"Invalid function {function} for light {light_name}")
            if 'duration' not in data:
                raise ValueError("A duration is required")

            if self.exclusive.get((light_name, function)) not in (sender, None):
                # Someone else is exclusive for this light and/or function, so bail
                raise RuntimeError(f"Another sender is exclusive for {light_name}/{function}")

            to_cancel = None
            for eff in self.effects.values():
                if eff.light_name == light_name and eff.function == function:
                    if eff.sender != sender:
                        # Someone else already has an effect for this light/function
                        raise RuntimeError(f"Another sender has an active effect for {light_name}/{function}")
                    elif override:
                        # This sender has an effect - cancel it
                        self.cancel_effect(effect=eff)
                        break
                    else:
                         # The sender is not overriding their own effect, do not apply, but do not raise an error
                         return

            start_value = data.get('start_value', light.state[function])
            end_value = data.get('end_value', light.state[function])
            speed_config = light.functions[function].get('speed')
            eff = Effect(
                sender,
                light_name,
                function,
                start_value,
                end_value,
                data['duration'],
                speed_config=speed_config,
                keep_state=data.get('keep_state', False),
                orig_speed=light.initialize.get('speed') if speed_config else None,
            )
            self.effects[eff.id] = eff
            return eff
        except (ValueError, RuntimeError) as e:
            if suppress_errors:
                logger.error("Can't set state for %s:%s: %s: %s\n%s", sender, light_or_name, e.__class__.__name__, str(e), state)
            else:
                raise

    def cancel_effect(self, effect=None, light=None, function=None):
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
            eff.is_cancelled = True
            if not eff.keep_state:
                new_state.setdefault(eff.sender, {}).setdefault(eff.light_name, {})[eff.function] = eff.start_value
            # Always reset speed
            if eff.orig_speed is not None:
                new_state.setdefault(eff.sender, {}).setdefault(eff.light_name, {})['speed'] = eff.orig_speed
            del self.effects[eff.id]
        for sender, lights in new_state.items():
            for l, s in lights.items():
                self.set_state(sender, l, s)

    def run(self, data):
        # Run effects first
        for eff_id, eff in list(self.effects.items()):
            if eff.is_new:
                # For new effects, set the initial value (unless speed is a factor then set the final value)
                eff.is_new = False
                speed = eff.speed
                if speed is None:
                    self.set_state(eff.sender, eff.light_name, {eff.function: eff.start_value}, suppress_errors=True)
                else:
                    self.set_state(eff.sender, eff.light_name, {'speed': speed, eff.function: eff.end_value}, suppress_errors=True)
            else:
                if eff.speed is None:
                    self.set_state(eff.sender, eff.light_name, {eff.function: eff.value}, suppress_errors=True)
                if eff.done:
                    self.cancel_effect(effect=eff)

        for light_name, state in self._render_state_queue(clear=True).items():
            self.lights[light_name].set_state(**state)

        #         elif cmd == 'exclusive':
        #             if not ev.sender:
        #                 logger.warning("Can't go exclusive with no sender")
        #             else:
        #                 exclusive_set = []
        #                 try:
        #                     for light_name in ev.data.get('lights') or self.lights.keys():
        #                         light = self.lights.get(light_name)
        #                         if not light:
        #                             raise ValueError(f"No such light: {light_name}")
        #                         if getattr(light, 'functions', None):
        #                             for prop in ev.data.get('functions') or light.functions.keys():
        #                                 exclusive_set.append((light_name, prop))
        #                         else:
        #                             exclusive_set.append((light_name, None))

        #                     if ev.data.get('state'):
        #                         for k in exclusive_set:
        #                             if self.exclusive.get(k) and self.exclusive[k] != ev.sender:
        #                                 raise ValueError(f"Another client is exclusive for {k}")
        #                         self.exclusive.update({k: ev.sender for k in exclusive_set})
        #                     else:
        #                         self.exclusive.update({k: None for k in exclusive_set if self.exclusive.get(k) == ev.sender})
        #                 except ValueError as e:
        #                     logger.warning("Sender %s cannot be exclusive: %s", str(e))
        #                     ev.returning(False)
        #                 else:
        #                     ev.returning(True)
        #                     for l, f in exclusive_set:
        #                         self._cancel_effect(light=l, function=f)
        #         elif cmd == 'effect':
        #             action = args(1)
        #             elif action == 'cancel':
        #                 effect = self.effects.get(ev.data.get('effect'))
        #                 if not effect:
        #                     logger.error("Tried to cancel an effect that doesn't exist")
        #                 elif effect.sender != ev.sender:
        #                     logger.error("Tried to cancel an effect w/ wrong sender")
        #                 else:
        #                     self._cancel_effect(effect=effect, explicit=True, keep_state=ev.data.get('keep_state'))

        data['rendered_state'] = DMXLight.send_batch(self.dmx_devices, self.lights.values())
