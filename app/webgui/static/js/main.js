require('pages');

let socket = new WebSocket('ws://' + window.location.host + '/lights/recv')
let mkf = function(es) {
    return function() {
        console.log("%s: %o", es, arguments)
    }
}
socket.addEventListener('open', mkf('open'));
socket.addEventListener('close', mkf('close'));
socket.addEventListener('error', mkf('error'));
socket.addEventListener('message', mkf('message'));