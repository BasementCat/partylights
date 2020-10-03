from unittest import TestCase

from app.lightserver import bases


TEST_CONFIG = {
  'DMXDevices': {
    'default': 'sink',
    'test': 'sink',
  },
  'LightTypes': {
    'UnnamedGobo': {
      'RawType': 'dmx',
      'Channels': 11,
      'Functions': {
        'pan': {'channel': 1},
        'pan_fine': {'channel': 2},
        'tilt': {'channel': 3},
        'tilt_fine': {'channel': 4},
        'color': {
          'channel': 5,
          'type': 'static',
          'map': {
            'white': [0, 9],
            'yellow': [10, 19],
            'orange': [20, 29],
            'cyan': [30, 39],
            'blue': [40, 49],
            'green': [50, 59],
            'pink': [60, 69],
            'red': [70, 79],
            'pink_red': [80, 89],
            'green_pink': [90, 99],
            'blue_green': [100, 109],
            'cyan_blue': [110, 119],
            'orange_cyan': [120, 129],
            'yellow_orange': [130, 139],
          },
        },
        'gobo': {
          'channel': 6,
          'type': 'static',
          'map': {
            'none': [0, 7],
            'broken_circle': [8, 15],
            'burst': [16, 23],
            '3_spot_circle': [24, 31],
            'square_spots': [32, 39],
            'droplets': [40, 47],
            'swirl': [48, 55],
            'stripes': [56, 63],
            'dither_none': [64, 71],
            'dither_broken_circle': [72, 79],
            'dither_burst': [80, 87],
            'dither_3_spot_circle': [88, 95],
            'dither_square_spots': [96, 103],
            'dither_droplets': [104, 111],
            'dither_swirl': [112, 119],
            'dither_stripes': [120, 127],
          },
        },
        'strobe': {
          'channel': 7,
          'invert': True,
        },
        'dim': {'channel': 8},
        'speed': {
          'channel': 9,
          'invert': True,
        },
        'mode': {
          'channel': 10,
          'type': 'static',
          'map': {
            'manual': [0, 59],
            'auto0': [135, 159],
            'auto1': [110, 134],
            'auto2': [85, 109],
            'auto3': [60, 84],
            'sound0': [235, 255],
            'sound1': [210, 234],
            'sound2': [185, 209],
            'sound3': [160, 184],
          },
        },
        'reset': {
          'channel': 11,
          'type': 'boolean',
          'resets': True,
        },
      },
    },
    'UKingGobo': {
      'RawType': 'dmx',
      'Channels': 11,
      'Functions': {
        'pan': {'channel': 1},
        'pan_fine': {'channel': 2},
        'tilt': {'channel': 3},
        'tilt_fine': {'channel': 4},
        'color': {
          'channel': 5,
          'type': 'static',
          'map': {
            'white': [0, 9],
            'red': [10, 19],
            'green': [20, 29],
            'blue': [30, 39],
            'yellow': [40, 49],
            'orange': [50, 59],
            'cyan': [60, 69],
            'pink': [70, 79],
            'pink_cyan': [80, 89],
            'cyan_orange': [90, 99],
            'orange_yellow': [100, 109],
            'yellow_blue': [110, 119],
            'blue_green': [120, 127],
          },
        },
        'gobo': {
          'channel': 6,
          'type': 'static',
          'map': {
            'none': [0, 7],
            'broken_circle': [8, 15],
            'burst': [16, 23],
            '3_spot_circle': [24, 31],
            'square_spots': [32, 39],
            'droplets': [40, 47],
            'swirl': [48, 55],
            'stripes': [56, 63],
            'dither_none': [64, 71],
            'dither_broken_circle': [72, 79],
            'dither_burst': [80, 87],
            'dither_3_spot_circle': [88, 95],
            'dither_square_spots': [96, 103],
            'dither_droplets': [104, 111],
            'dither_swirl': [112, 119],
            'dither_stripes': [120, 127],
          },
        },
        'strobe': {
          'channel': 7,
          'invert': True,
        },
        'dim': {'channel': 8},
        'speed': {
          'channel': 9,
          'invert': True,
        },
        'mode': {
          'channel': 10,
          'type': 'static',
          'map': None,
        },
        'dim_mode': {
          'channel': 11,
          'type': 'static',
          'map': {
            'standard': [0, 20],
            'stage': [21, 40],
            'tv': [41, 60],
            'building': [61, 80],
            'theater': [81, 100],
            'reset': [101, 255],
          },
          'resets': [101, 255],
        },
      },
    },
    'TomshineMovingHead6in1': {
      'RawType': 'dmx',
      'Channels': 18,
      'Functions': {
        'pan': {'channel': 1},
        'pan_fine': {'channel': 2},
        'tilt': {'channel': 3},
        'tilt_fine': {'channel': 4},
        'speed': {
          'channel': 5,
          'invert': True,
        },
        'dim': {'channel': 6},
        'strobe': {'channel': 7},
        'red': {'channel': 8},
        'green': {'channel': 9},
        'blue': {'channel': 10},
        'white': {'channel': 11},
        'amber': {'channel': 12},
        'uv': {'channel': 13},
        'mode': {
          'channel': 14,
          'type': 'static',
          'map': {
            'manual': [0, 15],
            'auto0': [105, 128],
            'auto1': [75, 104],
            'auto2': [45, 74],
            'auto3': [16, 44],
            'sound0': [218, 255],
            'sound1': [188, 217],
            'sound2': [158, 187],
            'sound3': [128, 157],
          },
        },
        'motor_sens': {'channel': 15},
        'effect': {
          'channel': 16,
          'type': 'static',
          'map': {
            'manual': [0, 0],
            'gradual': [1, 7],
            'auto1': [8, 39],
            'auto2': [40, 74],
            'auto3': [75, 108],
            'auto4': [109, 140],
            'sound1': [141, 168],
            'sound2': [169, 197],
            'sound3': [198, 226],
            'sound4': [227, 255],
          },
        },
        'led_sens': {'channel': 17},
        'reset': {
          'channel': 18,
          'type': 'boolean',
          'resets': True,
        },
      },
    },
    'Generic4ColorLaser': {
      'RawType': 'dmx',
      'Channels': 7,
      'Functions': {
        'mode': {
          'channel': 1,
          'type': 'static',
          'map': {
            'off': [0, 49],
            'static': [50, 99],
            'dynamic': [100, 149],
            'sound': [150, 199],
            'auto': [200, 255],
          },
        },
        'pattern': {
          'channel': 2,
          'type': 'static',
          'maps': [
            {
              'when': ['mode', 'static'],
              'map': {
                'circle': [0, 4],
                'dot_circle_1': [5, 9],
                'dot_circle_2': [10, 14],
                'scan_circle': [15, 19],
                'horiz_line': [20, 24],
                'horiz_dot_line': [25, 29],
                'vert_line': [30, 34],
                'vert_dot_line': [35, 39],
                '45deg_diag': [40, 44],
                '45deg_dot_diag': [45, 49],
                '135deg_diag': [50, 54],
                '135deg_dot_diag': [55, 59],
                'v_line_1': [60, 64],
                'v_dot_line_1': [65, 69],
                'v_line_2': [70, 74],
                'v_dot_line_2': [75, 79],
                'triangle_1': [80, 84],
                'dot_triangle_1': [85, 89],
                'triangle_2': [90, 94],
                'dot_triangle_2': [95, 99],
                'square': [100, 104],
                'dot_square': [105, 109],
                'rectangle_1': [110, 114],
                'dot_rectangle_1': [115, 119],
                'rectangle_2': [120, 124],
                'dot_rectangle_2': [125, 129],
                'criscross': [130, 134],
                'chiasma_line': [135, 139],
                'horiz_extend_line': [140, 144],
                'horiz_shrink_line': [145, 149],
                'horiz_flex_line': [150, 154],
                'horiz_flex_dot_line': [155, 159],
                'vert_extend_line': [160, 164],
                'vert_shrink_line': [165, 169],
                'vert_flex_line': [170, 174],
                'vert_flex_dot_line': [175, 179],
                'ladder_line_1': [180, 184],
                'ladder_line_2': [185, 189],
                'ladder_line_3': [190, 194],
                'ladder_line_4': [195, 199],
                'tetragon_1': [200, 204],
                'tetragon_2': [205, 209],
                'pentagon_1': [210, 214],
                'pentagon_2': [215, 219],
                'pentagon_3': [220, 224],
                'pentagon_4': [225, 229],
                'wave_line': [230, 234],
                'wave_dot_line': [235, 239],
                'spiral_line': [240, 244],
                'many_dot_1': [245, 249],
                'many_dot_2': [250, 254],
                'square_dot': [255, 255],
              },
            },
            {
              'when': ['mode', 'dynamic'],
              'map': {
                'circle_to_big': [0, 4],
                'dot_circle_to_big': [5, 9],
                'scan_circle_to_big': [10, 14],
                'circle_flash': [15, 19],
                'dot_circle_flash': [20, 24],
                'circle_roll': [25, 29],
                'dot_circle_roll': [30, 34],
                'circle_turn': [35, 39],
                'dot_circle_turn': [40, 44],
                'dot_circle_to_add': [45, 49],
                'scan_circle_extend': [50, 54],
                'circle_jump': [55, 59],
                'dot_circle_jump': [60, 64],
                'horiz_line_jump': [65, 69],
                'horiz_dot_line_jump': [70, 74],
                'vert_line_jump': [75, 79],
                'vert_dot_line_jump': [80, 84],
                'diag_jump': [85, 89],
                'dot_diag_jump': [90, 94],
                'short_sector_round_1': [95, 99],
                'short_sector_round_2': [100, 104],
                'long_sector_round_1': [105, 109],
                'long_sector_round_2': [110, 114],
                'line_scan': [115, 119],
                'dot_line_scan': [120, 124],
                '45deg_diag_move': [125, 129],
                'dot_diag_move': [130, 134],
                'horiz_line_flex': [135, 139],
                'horiz_dot_line_flex': [140, 144],
                'horiz_line_move': [145, 149],
                'horiz_dot_line_move': [150, 154],
                'vert_line_move': [155, 159],
                'vert_dot_line_move': [160, 164],
                'rect_extend': [165, 169],
                'dot_rect_extend': [170, 174],
                'square_extend': [175, 179],
                'dot_square_extend': [180, 184],
                'rect_turn': [185, 189],
                'dot_rect_turn': [190, 194],
                'square_turn': [195, 199],
                'dot_square_turn': [200, 204],
                'pentagon_turn': [205, 209],
                'dot_pentagon_turn': [210, 214],
                'tetragon_turn': [215, 219],
                'pentagon_star_turn': [220, 224],
                'bird_fly': [225, 229],
                'dot_bird_fly': [230, 234],
                'wave_flowing': [235, 239],
                'dot_wave_flowing': [240, 244],
                'many_dot_jump_1': [245, 249],
                'square_dot_jump': [250, 254],
                'many_dot_jump_2': [255, 255],
              },
            },
          ],
        },
        'x': {'channel': 3},
        'y': {'channel': 4},
        'scan_speed': {
          'channel': 5,
          'invert': True,
        },
        'pattern_speed': {
          'channel': 6,
          'invert': True,
        },
        'pattern_size': {'channel': 7},
      },
    },
  },
  'Lights': {
    'back_1': {
      'Type': 'UnnamedGobo',
      'Address': 1,
    },
    'back_2': {
      'Type': 'UnnamedGobo',
      'Address': 12,
    },
    'mid_1': {
      'Type': 'UKingGobo',
      'Address': 23,
    },
    'mid_2': {
      'Type': 'UKingGobo',
      'Address': 34,
    },
    'mid_3': {
      'Type': 'UKingGobo',
      'Address': 45,
    },
    'mid_4': {
      'Type': 'UKingGobo',
      'Address': 56,
    },
    'front_1': {
      'Type': 'TomshineMovingHead6in1',
      'Address': 67,
      'Initialize': {'dim': 120},
    },
    'front_2': {
      'Type': 'TomshineMovingHead6in1',
      'Address': 85,
      'Initialize': {'dim': 120},
    },
    'laser': {
      'Type': 'Generic4ColorLaser',
      'Address': 103,
      'Device': 'test',
    }
  },
}



class TestLightserverBaseLight(TestCase):
    def test_get_bases(self):
        self.assertEqual({'dmx': bases.DMXLight}, bases.Light.get_bases())

    def test_init(self):
        i = bases.Light({}, 'testname', {}, {'Type': 'testtype'})
        self.assertEqual('testtype testname', str(i))


class TestLightserverDMXLight(TestCase):
    def test_create_from(self):
        i = bases.Light.create_from({'LightTypes': {'testtype': {'RawType': 'dmx', 'Channels': 1, 'Functions': {'foo': {'channel': 1}}}}}, 'testname', {'Type': 'testtype', 'Address': 1})
        self.assertIsInstance(i, bases.DMXLight)
        self.assertEqual('testtype testname', str(i))
        self.assertEqual('default', i.device_name)
        self.assertEqual(1, i.num_channels)
        self.assertEqual({'foo': {'channel': 1}}, i.functions)
        self.assertEqual({}, i.initialize)
        self.assertEqual(1, i.address)
        self.assertEqual({'foo': 0}, i.state)
        self.assertEqual({'foo': 0}, i.last_state)
        self.assertEqual({'foo': 0}, i.diff_state)

    def test_create_from_adv(self):
        for name, lconfig in TEST_CONFIG['Lights'].items():
            tconfig = TEST_CONFIG['LightTypes'][lconfig['Type']]
            try:
                i = bases.Light.create_from(TEST_CONFIG, name, lconfig)
                self.assertIsInstance(i, bases.DMXLight)
                self.assertEqual(f'{lconfig["Type"]} {name}', str(i))
                self.assertEqual(lconfig.get('Device', 'default'), i.device_name)
                self.assertEqual(tconfig['Channels'], i.num_channels)
                self.assertEqual(tconfig['Functions'], i.functions)
                self.assertEqual(lconfig.get('Initialize', {}), i.initialize)
                self.assertEqual(lconfig['Address'], i.address)
                self.assertTrue(bool(i.state))
                self.assertTrue(bool(i.last_state))
                self.assertTrue(bool(i.diff_state))
            except:
                print('TEST>', name, tconfig, lconfig)
                raise

    def test_init_state(self):
        i = bases.Light.create_from(TEST_CONFIG, 'back_1', TEST_CONFIG['Lights']['back_1'])
        self.assertEqual(
            {
                'pan': 0,
                'pan_fine': 0,
                'tilt': 0,
                'tilt_fine': 0,
                'color': 0,
                'gobo': 0,
                'strobe': 0,
                'dim': 0,
                'speed': 0,
                'mode': 0,
                'reset': 0,
            },
            i.state
        )

        i = bases.Light.create_from(TEST_CONFIG, 'front_1', TEST_CONFIG['Lights']['front_1'])
        self.assertEqual(
            {
                'pan': 0,
                'pan_fine': 0,
                'tilt': 0,
                'tilt_fine': 0,
                'speed': 0,
                'dim': 120,
                'strobe': 0,
                'red': 0,
                'green': 0,
                'blue': 0,
                'white': 0,
                'amber': 0,
                'uv': 0,
                'mode': 0,
                'motor_sens': 0,
                'effect': 0,
                'led_sens': 0,
                'reset': 0,
            },
            i.state
        )

    def test_get_dmx(self):
        i = bases.Light.create_from(TEST_CONFIG, 'front_1', TEST_CONFIG['Lights']['front_1'])
        self.assertEqual(
            {
                67: 0,
                68: 0,
                69: 0,
                70: 0,
                71: 255,
                72: 120,
                73: 0,
                74: 0,
                75: 0,
                76: 0,
                77: 0,
                78: 0,
                79: 0,
                80: 0,
                81: 0,
                82: 0,
                83: 0,
                84: 0,
            },
            i.get_dmx()
        )

    def test_set_state(self):
        i = bases.Light.create_from(TEST_CONFIG, 'front_1', TEST_CONFIG['Lights']['front_1'])
        i.set_state(
            pan=1,
            pan_fine=2,
            tilt=3,
            tilt_fine=4,
            speed=5,
            dim=6,
            strobe=7,
            red=8,
            green=9,
            blue=10,
            white=11,
            amber=12,
            uv=13,
        )
        self.assertEqual(
            {
                67: 1,
                68: 2,
                69: 3,
                70: 4,
                71: 250,
                72: 6,
                73: 7,
                74: 8,
                75: 9,
                76: 10,
                77: 11,
                78: 12,
                79: 13,
                80: 0,
                81: 0,
                82: 0,
                83: 0,
                84: 0,
            },
            i.get_dmx()
        )

    def test_set_state_map(self):
        i = bases.Light.create_from(TEST_CONFIG, 'back_1', TEST_CONFIG['Lights']['back_1'])
        i.set_state(color='pink', gobo='burst')
        res = i.get_dmx()
        self.assertEqual(60, res[5])
        self.assertEqual(16, res[6])

    def test_set_state_multi_map(self):
        i = bases.Light.create_from(TEST_CONFIG, 'laser', TEST_CONFIG['Lights']['laser'])
        i.set_state(mode='off', pattern='v_line_2')
        self.assertEqual(0, i.state['mode'])
        self.assertEqual(0, i.state['pattern'])
        i.set_state(mode='dynamic', pattern='v_line_2')
        self.assertEqual(100, i.state['mode'])
        self.assertEqual(0, i.state['pattern'])
        i.set_state(mode='static', pattern='v_line_2')
        self.assertEqual(50, i.state['mode'])
        self.assertEqual(70, i.state['pattern'])

    def test_mark_sent(self):
        i = bases.Light.create_from(TEST_CONFIG, 'front_1', TEST_CONFIG['Lights']['front_1'])
        i.mark_sent()
        i.set_state(pan=1)
        self.assertEqual({'pan': 1}, i.diff_state)
        i.mark_sent()
        self.assertEqual({}, i.diff_state)

    def test_mark_sent_reset_bool(self):
        i = bases.Light.create_from(TEST_CONFIG, 'front_1', TEST_CONFIG['Lights']['front_1'])
        i.mark_sent()
        i.set_state(reset=2)
        self.assertEqual({'reset': 1}, i.diff_state)
        i.mark_sent()
        self.assertEqual({
            'amber': 0,
            'blue': 0,
            'dim': 120,
            'effect': 0,
            'green': 0,
            'led_sens': 0,
            'mode': 0,
            'motor_sens': 0,
            'pan': 0,
            'pan_fine': 0,
            'red': 0,
            'reset': 0,
            'speed': 0,
            'strobe': 0,
            'tilt': 0,
            'tilt_fine': 0,
            'uv': 0,
            'white': 0
            }, i.diff_state)

    def test_mark_sent_reset_range(self):
        i = bases.Light.create_from(TEST_CONFIG, 'mid_1', TEST_CONFIG['Lights']['mid_1'])
        i.mark_sent()
        i.set_state(dim_mode='tv')
        self.assertEqual({'dim_mode': 41}, i.diff_state)
        i.mark_sent()
        self.assertEqual({}, i.diff_state)
        i.set_state(dim_mode='reset')
        self.assertEqual({'dim_mode': 101}, i.diff_state)
        i.mark_sent()
        self.assertEqual({
            'pan': 0,
            'pan_fine': 0,
            'tilt': 0,
            'tilt_fine': 0,
            'color': 0,
            'gobo': 0,
            'strobe': 0,
            'dim': 0,
            'speed': 0,
            'mode': 0,
            'dim_mode': 0,
            }, i.diff_state)

    def test_send_batch(self):
        self.maxDiff = None
        class MockDMXPY:
            def __init__(self):
                self.data = {}
                self.rendered = 0

            def setChannel(self, chan, val):
                self.data.setdefault(chan, []).append(val)

            def render(self):
                self.rendered += 1

        lights = [bases.Light.create_from(TEST_CONFIG, k, v) for k, v in TEST_CONFIG['Lights'].items()]

        dmx_devs = {
            'default': MockDMXPY(),
            'test': MockDMXPY(),
        }

        bases.DMXLight.send_batch(dmx_devs, lights)

        self.assertEqual(
            {1: [0],2: [0],3: [0],4: [0],5: [0],6: [0],7: [255],8: [0],9: [255],10: [0],11: [0],12: [0],13: [0],14: [0],15: [0],16: [0],17: [0],18: [255],19: [0],20: [255],21: [0],22: [0],23: [0],24: [0],25: [0],26: [0],27: [0],28: [0],29: [255],30: [0],31: [255],32: [0],33: [0],34: [0],35: [0],36: [0],37: [0],38: [0],39: [0],40: [255],41: [0],42: [255],43: [0],44: [0],45: [0],46: [0],47: [0],48: [0],49: [0],50: [0],51: [255],52: [0],53: [255],54: [0],55: [0],56: [0],57: [0],58: [0],59: [0],60: [0],61: [0],62: [255],63: [0],64: [255],65: [0],66: [0],67: [0],68: [0],69: [0],70: [0],71: [255],72: [120],73: [0],74: [0],75: [0],76: [0],77: [0],78: [0],79: [0],80: [0],81: [0],82: [0],83: [0],84: [0],85: [0],86: [0],87: [0],88: [0],89: [255],90: [120],91: [0],92: [0],93: [0],94: [0],95: [0],96: [0],97: [0],98: [0],99: [0],100: [0],101: [0],102: [0]},
            dmx_devs['default'].data
        )
        self.assertEqual(
            1,
            dmx_devs['default'].rendered
        )
        self.assertEqual(
            {103: [0], 104: [0], 105: [0], 106: [0], 107: [255], 108: [255], 109: [0]},
            dmx_devs['test'].data
        )
        self.assertEqual(
            1,
            dmx_devs['test'].rendered
        )

        for l in lights:
            l.set_state(pan=5, x=5)
        bases.DMXLight.send_batch(dmx_devs, lights)

        self.assertEqual(
            {1: [0,5],2: [0,0],3: [0,0],4: [0,0],5: [0,0],6: [0,0],7: [255,255],8: [0,0],9: [255,255],10: [0,0],11: [0,0],12: [0,5],13: [0,0],14: [0,0],15: [0,0],16: [0,0],17: [0,0],18: [255,255],19: [0,0],20: [255,255],21: [0,0],22: [0,0],23: [0,5],24: [0,0],25: [0,0],26: [0,0],27: [0,0],28: [0,0],29: [255,255],30: [0,0],31: [255,255],32: [0,0],33: [0,0],34: [0,5],35: [0,0],36: [0,0],37: [0,0],38: [0,0],39: [0,0],40: [255,255],41: [0,0],42: [255,255],43: [0,0],44: [0,0],45: [0,5],46: [0,0],47: [0,0],48: [0,0],49: [0,0],50: [0,0],51: [255,255],52: [0,0],53: [255,255],54: [0,0],55: [0,0],56: [0,5],57: [0,0],58: [0,0],59: [0,0],60: [0,0],61: [0,0],62: [255,255],63: [0,0],64: [255,255],65: [0,0],66: [0,0],67: [0,5],68: [0,0],69: [0,0],70: [0,0],71: [255,255],72: [120,120],73: [0,0],74: [0,0],75: [0,0],76: [0,0],77: [0,0],78: [0,0],79: [0,0],80: [0,0],81: [0,0],82: [0,0],83: [0,0],84: [0,0],85: [0,5],86: [0,0],87: [0,0],88: [0,0],89: [255,255],90: [120,120],91: [0,0],92: [0,0],93: [0,0],94: [0,0],95: [0,0],96: [0,0],97: [0,0],98: [0,0],99: [0,0],100: [0,0],101: [0,0],102: [0,0]},
            dmx_devs['default'].data
        )
        self.assertEqual(
            2,
            dmx_devs['default'].rendered
        )
        self.assertEqual(
            {103: [0,0], 104: [0,0], 105: [0,5], 106: [0,0], 107: [255,255], 108: [255,255], 109: [0,0]},
            dmx_devs['test'].data
        )
        self.assertEqual(
            2,
            dmx_devs['test'].rendered
        )