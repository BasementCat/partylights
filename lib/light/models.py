import logging


logger = logging.getLogger(__name__)


class Light:
    RAW_TYPE = None

    def __init__(self, config, name, type_config, light_config):
        self.config = config
        self.name = name
        self.type_name = light_config['Type']

    def __str__(self):
        return f'{self.type_name} {self.name}'

    def dump(self):
        return {
            'Name': self.name,
            'Type': self.type_name,
        }

    @classmethod
    def get_bases(cls):
        return {c.RAW_TYPE: c for c in cls.__subclasses__()}

    @classmethod
    def create_from(cls, config, name, light_config):
        type_config = config['LightTypes'][light_config['Type']]
        l_cls = cls.get_bases()[type_config['RawType']]
        return l_cls(config, name, type_config, light_config)


class DMXLight(Light):
    RAW_TYPE = 'dmx'

    def __init__(self, config, name, type_config, light_config):
        super().__init__(config, name, type_config, light_config)
        self.device_name = light_config.get('Device', 'default')
        self.num_channels = type_config['Channels']
        self.functions = type_config['Functions']
        self.initialize = light_config.get('Initialize', {})
        self.address = light_config['Address']
        # TODO: light config RestrictPosition, or in auto?

        self.init_state()

    def init_state(self):
        self.state = {k: self.initialize.get(k, 0) for k in self.functions}
        self.last_state = self.state.copy()
        # On init, pretend everything has changed
        self.diff_state = self.state.copy()

    def dump(self):
        out = super().dump()
        out.update({
            'Device': self.device_name,
            'Channels': self.num_channels,
            'Functions': self.functions,
            'Initialize': self.initialize,
            'Address': self.address,
        })
        return out

    def get_dmx(self):
        out = {}
        for fn, data in self.functions.items():
            v = self.state.get(fn, 0)
            if data.get('invert'):
                v = 255 - v
            out[(self.address - 1) + data['channel']] = v
        return out

    def _get_map(self, prop, multi=True):
        fn = self.functions.get(prop, {})
        if 'map' in fn:
            return fn['map']
        if multi and 'maps' in fn:
            for multi_map in fn['maps']:
                when_prop, when_expected_val = multi_map['when']
                when_current_val = self.state.get(when_prop)
                when_prop_map = self._get_map(when_prop)
                if when_prop_map:
                    for k, v in when_prop_map.items():
                        if when_current_val >= v[0] and when_current_val <= v[1] and k == when_expected_val:
                            when_expected_val = v[0]
                            break
                if when_expected_val == when_current_val:
                    return multi_map['map']

    def set_state(self, **kwargs):
        choice_map_props = []
        for k, v in kwargs.items():
            fn = self.functions.get(k)
            if not fn:
                continue
            if fn.get('type') == 'static':
                if isinstance(v, str):
                    # If there's a single map, use it
                    map_ = self._get_map(k, multi=False)
                    if map_:
                        if v not in map_:
                            logger.error("%s: value '%s' not in prop map for %s", self, v, k)
                        else:
                            self.state[k] = map_[v][0]
                    elif fn.get('maps'):
                        # Set other props before figuring out what map to use
                        choice_map_props.append(k)
                    else:
                        logger.error("%s: can't set value '%s' for %s", self, v, k)
                else:
                    self.state[k] = v
            elif fn.get('type') == 'boolean':
                self.state[k] = int(bool(v))
            else:
                # Probably range
                self.state[k] = v

        for k in choice_map_props:
            # Can assume that k is both in functions and kwargs, and that v is a string
            v = kwargs[k]
            map_ = self._get_map(k)
            if map_:
                if v not in map_:
                    logger.error("%s: value '%s' not in prop map for %s", self, v, k)
                else:
                    self.state[k] = map_[v][0]

        for k, v in self.state.items():
            if v != self.last_state.get(k):
                self.diff_state[k] = v

    def mark_sent(self):
        for k, v in self.diff_state.items():
            fn = self.functions.get(k)
            if not fn:
                continue
            if fn.get('resets') is True:
                if v:
                    return self.init_state()
            elif fn.get('resets'):
                if v >= fn['resets'][0] and v <= fn['resets'][1]:
                    return self.init_state()
        self.last_state = self.state.copy()
        self.diff_state = {}

    @classmethod
    def send_batch(cls, devices, lights):
        dev_data = {}
        for l in lights:
            if l.diff_state:
                dev_data.setdefault(l.device_name, {}).update(l.get_dmx())
                l.mark_sent()
        for dname, data in dev_data.items():
            for chan, val in data.items():
                devices[dname].setChannel(chan, val)
            devices[dname].render()
