let util = require('lib/util');
let WS = require('lib/websocket');
let clientid = require('lib/clientid');
let outputs = require('outputs');

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
        this.raw_lights = null;
        this.lights = null;
        this.ws = null;
    }

    render() {
        this.ws = new WS('/lights/recv?clientid=' + clientid());
        this.ws.on('decoded_message', this._handle_message.bind(this));
    }

    _handle_message(data) {
        if (data[0] === 'lights') {
            console.log(data[1]);
            this.raw_lights = data[1];
            this._really_render();
        } else if (data[0] === 'state') {
            this.lights[data[1]] && (this.lights[data[1]].state = data[2]);
        }
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
        this.ws.close();
        this.lights = null;
        super.unrender();
    }
}

exports.__main = {
    monitor: new MonitorPage()
}