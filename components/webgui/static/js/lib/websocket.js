class WS {
    constructor(path) {
        this.base_url = 'ws://' + window.location.host;
        this.path = path;
        this.ws = null;
        this.handlers = {};
        this.on('error', e => this._reconnect(e, true));
        this.on('close', e => this._reconnect(e, false));
        this._connect();
    }

    on(ev, cb) {
        this.handlers[ev] = this.handlers[ev] || [];
        this.handlers[ev].push(cb);
        if (this.ws !== null) {
            this._add_listener(ev, cb);
        }
        return this;
    }

    _decode(ev) {
        try {
            return JSON.parse(ev.data);
        } catch (e) {
            console.error("Failed to parse json for %o: %o", ev, e);
            return null;
        }
    }

    _add_listener(ev, cb) {
        if (ev == 'decoded_message') {
            this.ws.addEventListener('message', function(e) { let v=this._decode(e);if(v!==null) cb(v); }.bind(this));
        } else {
            this.ws.addEventListener(ev, cb);
        }
    }

    _connect() {
        // TODO: retry
        this.ws = new WebSocket(this.base_url + this.path);
        Object.entries(this.handlers).forEach(ev => {
            this.handlers[ev] && this.handlers[ev].forEach(cb => this._add_listener(ev, cb));
        });
    }

    _reconnect(event, is_err) {
        if (is_err) {
            console.error("WebSocket connection to %s%s failed: %o, reconnecting", this.base_url, this.path, event);
            this.ws.close();
        } else {
            console.debug("WebSocket connection to %s%s is closed: %o, reconnecting", this.base_url, this.path, event);
        }
        this._connect();
    }
}

exports.__main = WS;


// let socket = new WebSocket('ws://' + window.location.host + '/lights/recv')
// let mkf = function(es) {
//     return function() {
//         console.log("%s: %o", es, arguments)
//     }
// }
// socket.addEventListener('open', mkf('open'));
// socket.addEventListener('close', mkf('close'));
// socket.addEventListener('error', mkf('error'));
// socket.addEventListener('message', mkf('message'));