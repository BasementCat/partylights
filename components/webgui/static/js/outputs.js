let util = require('lib/util');

class Output {
    constructor(light) {
        this.light = light;
    }

    monitor_event(event) {}

    select_light(light) {}

    deselect_light(light) {}

    render() {}

    destroy() {}
}

class TableRowOutput extends Output {
    constructor(light, fields) {
        super(light);
        this.fields = fields;
        this.tr = document.createElement('tr');
        this.tdmap = {};
        this.fields.forEach(n => {
            var td = document.createElement('td');
            var link = document.createElement('a');
            this.tdmap[n] = td
            this.tr.appendChild(td);
        });
        this.selected = false;
    }

    select_light(light) {
        if (light === this.light)
            this.selected = true;
    }

    deselect_light(light) {
        if (light === this.light)
            this.selected = false;
    }

    render() {
        this.fields.forEach(n => {
            this.tdmap[n].innerHTML = this.light[n] || this.light.state[n] || '';
        });
        if (this.selected && !this.tr.classList.contains('selected'))
            this.tr.classList.add('selected');
        else if (!this.selected && this.tr.classList.contains('selected'))
            this.tr.classList.remove('selected');
    }
}

class TableOutput {
    constructor(dest, lights) {
        this.dest = dest;
        this.table = document.createElement('table');
        this.thead = document.createElement('thead');
        this.tbody = document.createElement('tbody');

        this.table.classList.add('props');
        this.table.classList.add('table');
        this.table.classList.add('table-striped');

        var headers = ['name', 'type', 'effects', 'state_effects'];
        Object.entries(lights).forEach(l => {
            Object.entries(l[1].functions).forEach(f => headers.indexOf(f[0]) < 0 && headers.push(f[0]));
        });

        headers.forEach(h => {
            var th = document.createElement('th');
            th.innerHTML = h;
            this.thead.appendChild(th);
        });

        Object.entries(lights).forEach(l => {
            var o = new TableRowOutput(l[1], headers);
            l[1].add_output(o);
            this.tbody.appendChild(o.tr);
        });

        this.table.appendChild(this.thead);
        this.table.appendChild(this.tbody);
        this.dest.appendChild(this.table);
    }

    destroy() {
        this.dest.removeChild(this.table);
    }
}

class MovingHeadOutput extends Output {
    constructor(dest, light) {
        if (!light.is_movinghead) return;
        super(light);

        this.color_set = null;
        if (this.light.is_fixed_colors) {
            this.color_set = {};
            Object.entries(this.light.functions.color.map).forEach(v => {
                var color;
                if (/_/.test(v[0])) {
                    color = v[0].split('_');
                } else {
                    color = [v[0], v[0]];
                }
                for (var i = v[1][0]; i <= v[1][1]; i++) {
                    this.color_set[i] = color;
                }
            });
        }

        this.gobo_set = null;
        if (this.light.is_gobo) {
            this.gobo_set = {};
            Object.entries(this.light.functions.gobo.map).forEach(v => {
                var gobo, dither
                if (/^dither_/.test(v[0])) {
                    gobo = v[0].substring(7);
                    dither = true;
                } else {
                    gobo = v[0];
                    dither = false;
                }
                for (var i = v[1][0]; i <= v[1][1]; i++) {
                    this.gobo_set[i] = {'gobo': gobo, 'dither': dither};
                }
            });
        }

        this.dest = dest;

        this.effects = {};
        this.state_effects = {};

        // All the elements that make up the light
        this.gobo_img = null;
        if (this.gobo_set) {
            this.gobo_img = util.make_el('img', null, ['gobo']);
        }
        this.light_bulb = util.make_el('div', this.gobo_img, ['light_bulb']);
        this.light_head = util.make_el('div', this.light_bulb, ['light_head']);
        this.light_name = util.make_el('span', this.light.type + ' ' + this.light.name, ['light_name']);
        this.light_body = util.make_el('div', [this.light_head, this.light_name], ['light_body']);
        this.effects_list = util.make_el('ul', null, ['info_list', 'effects']);
        this.state_effects_list = util.make_el('ul', null, ['info_list', 'state_effects']);
        this.light_container = util.make_el('div', [this.light_body, this.state_effects_list, this.effects_list], ['light_container']);

        this.dest.appendChild(this.light_container);
    }

    _transition_duration(attr) {
        if (!(this.light.functions[attr] && this.light.functions[attr].speed))
            return 0;
        let ts = this.light.functions[attr].speed;
        var s = this.light.state.speed;
        return ts[0] + ((s / 255) * (ts[1] - ts[0]));
    }

    monitor_event(event) {
        var obj = this[event.op.toLowerCase() + 's'];
        if (event.op_state == 'NEW') {
            obj[event.op_name] = [event.op_name, [event.state.start, event.state.end, event.state.done].join('->'), event.state.duration].join(' ');
        } else if (event.op_state == 'DONE') {
            delete obj[event.op_name];
        }
    }

    render() {
        // TODO: gobo
        // TODO: white, uv, amber
        // TODO: speed
        // TODO: pan fine
        // TODO: tilt fine

        if (this.light.is_rgb) {
            var c = [this.light.state.red, this.light.state.green, this.light.state.blue].join(', ');
            this.light_bulb.style.backgroundColor = 'rgb(' + c + ')';
        } else if (this.color_set) {
            var color = this.color_set[this.light.state.color];
            if (typeof color === 'undefined')
                color = this.color_set[0];
            this.light_bulb.style.background = 'linear-gradient(90deg, ' + color[0] + ' 0%, ' + color[0] + ' 50%, ' + color[1] + ' 50%, ' + color[1] + ' 100%)';
        }

        if (this.gobo_set) {
            var gobo = this.gobo_set[this.light.state.gobo];
            if (!gobo || gobo.gobo == 'none') {
                this.gobo_img.style.display = 'none';
            } else {
                this.gobo_img.style.display = 'block';
                this.gobo_img.src = '/static/img/gobos/' + gobo.gobo + '.png';
                // TODO: dither
            }
        }

        // TODO: do this better
        this.light_bulb.style.opacity = this.light.state.dim / 255;

        // TODO: don't assume 540
        this.light_head.style.transition = 'transform ' + this._transition_duration('pan') + 's';
        this.light_head.style.transform = 'rotate(' + ((this.light.state.pan / 255) * 540) + 'deg)';

        this.light_bulb.style.transition = 'top ' + this._transition_duration('tilt') + 's';
        this.light_bulb.style.top = ((this.light.state.tilt / 255) * 70) + '%';

        this.effects_list.innerHTML = Object.entries(this.effects).map((n, v) => '<li>' + v + '</li>');
        this.state_effects_list.innerHTML = Object.entries(this.state_effects).map((n, v) => '<li>' + v + '</li>');
    }

    destroy() {
        this.dest && this.dest.removeChild(this.light_container);
    }
}

class Light {
    constructor(light_data) {
        this.name = light_data.Name;
        this.type = light_data.Type;
        this.functions = light_data.Functions;
        // this._state = light_data.state;
        // TODO: get state on connect
        this._state = {};
        // TODO: must define speeds in config
        // this.speeds = light_data.speeds;
        this.outputs = [];
    }

    add_output(out) {
        this.outputs.push(out);
    }

    set state(state) {
        for (var k in state) {
            this._state[k] = state[k];
        }
        this.outputs.forEach(o => o.render());
    }
    get state() {
        return this._state;
    }

    get is_movinghead() {
        return (typeof this.functions.pan !== 'undefined') && (typeof this.functions.tilt !== 'undefined');
    }
    get is_rgb() {
        return (typeof this.functions.red !== 'undefined')
            && (typeof this.functions.green !== 'undefined')
            && (typeof this.functions.blue !== 'undefined');
    }
    get is_fixed_colors() {
        return (typeof this.functions.color !== 'undefined')
            && (typeof this.functions.color.map !== 'undefined');
    }
    get is_gobo() {
        return (typeof this.functions.gobo !== 'undefined');
    }
    // TODO: check speed, dim, strobe

    monitor_event(event) {
        this.outputs.forEach(o => {o.monitor_event(event); o.render();});
    }

    select() {
        this.outputs.forEach(o => {o.select_light(this); o.render();})
    }

    deselect() {
        this.outputs.forEach(o => {o.deselect_light(this); o.render();})
    }

    destroy() {
        this.outputs.forEach(o => o.destroy());
    }
}

return {
    'Light': Light,
    'TableOutput': TableOutput,
    'MovingHeadOutput': MovingHeadOutput,
}