let util = require('lib/util');
let outputs = require('outputs');
let Stream = require('lib/stream');

let container = document.getElementById('main');

class Page {
    constructor() {}
    render() {}
    unrender() {
        container.innerText = '';
    }
}

class MonitorPage extends Page {
    constructor() {
        super();
        this.audio_graph = null;
        this.raw_lights = null;
        this.lights = null;
        this.l_stream = null;
        this.a_stream = null;
    }

    render() {
        this.audio_graph = new outputs.AudioGraphOutput(container);
        this.a_stream = new Stream('audio', this._handle_audio.bind(this));
        $.get('/lights', function(d) {
            this._handle_lights(d.lights);
            this._handle_state(d.state);
            this.l_stream = new Stream('lights', this._handle_state.bind(this));
        }.bind(this));
    }

    _handle_lights(data) {
        this.raw_lights = data;
        this._really_render();
    }

    _handle_state(data) {
        for (var k in data) {
            if (this.lights[k]) this.lights[k].state = data[k];
        }
    }

    _handle_audio(data) {
        this.audio_graph.update(data)
    }

    _really_render() {
        this.lights = {};
        for (var name in this.raw_lights) {
            var light = this.lights[name] = new outputs.Light(this.raw_lights[name]);
            if (light.is_movinghead) {
                light.add_output(new outputs.MovingHeadOutput(container, light))
            }
        }
        new outputs.TableOutput(container, this.lights);
        console.log(this.lights);
    }

    unrender() {
        this.l_stream.stop();
        this.a_stream.stop();
        this.lights = null;
        super.unrender();
    }
}

exports.__main = {
    monitor: new MonitorPage()
}