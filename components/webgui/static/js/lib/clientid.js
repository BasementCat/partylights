exports.__main = function() {
    if (!window.sessionStorage.getItem('partylights-clientid')) {
        window.sessionStorage.setItem('partylights-clientid', '' + Math.random());
    }
    return window.sessionStorage.getItem('partylights-clientid');
}