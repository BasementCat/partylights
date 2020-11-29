class Stream {
    constructor(type, callback) {
        this.type = type;
        this.callback = callback;
        this.running = true;
        this._poll();
    }

    stop() {
        this.running = false;
    }

    _poll() {
        if (!this.running) return;
        let callback = this.callback;
        let buffer = '';
        let req = new XMLHttpRequest();
        req.open('GET', '/stream/' + this.type);
        req.seenBytes = 0;

        req.addEventListener('readystatechange', function() {
            if (req.readyState == 3) {
                buffer += req.responseText.substr(req.seenBytes);
                req.seenBytes = req.responseText.length;

                let full = buffer.substr(-1) == '\n';
                let parts = buffer.split('\n');
                if (full) {
                    buffer = '';
                    parts.pop();
                } else {
                    buffer = parts.pop();
                }

                parts.forEach(part => {
                    try {
                        callback(JSON.parse(part));
                    } catch (e) {
                        console.error(e);
                    }
                });
            }
        });

        req.addEventListener('load', function() {
            window.setTimeout(this._poll.bind(this), 0);
        }.bind(this));

        req.send();
    }
}

exports.__main = Stream;