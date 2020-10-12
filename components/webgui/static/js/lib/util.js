exports.make_el = function(tag, html, classes) {
    var el = document.createElement(tag);
    var add_el = function(v) {
        if (v) {
            if (typeof v === 'string')
                el.appendChild(document.createTextNode(v));
            else if (typeof v.push !== 'undefined')
                v.map(add_el);
            else
                el.appendChild(v);
        }
    }
    add_el(html);
    (classes || []).forEach(c => el.classList.add(c));
    return el;
}

exports.array_has = function(arr, items) {
    for (var i = 0; i < items.length; i++) {
        if (arr.indexOf(items[i]) < 0) return false;
    }
    return true;
}