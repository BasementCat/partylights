(function() {
    window.pl_pre_mod = window.pl_pre_mod || {};
    let modules = {};
    let loading = [];

    window.require = function(mod_name) {
        if (typeof modules[mod_name] !== 'undefined')
            return modules[mod_name];

        if (typeof window.pl_pre_mod[mod_name] === 'undefined')
            throw "No module named " + mod_name;

        if (loading.indexOf(mod_name) > -1)
            throw "Circular dependency: " + loading.join(', ') + ', ' + mod_name;

        loading.push(mod_name);
        let exports = {};
        let rv = window.pl_pre_mod[mod_name](exports);
        let mod = rv || exports;
        if (typeof mod.__main !== 'undefined')
            mod = mod.__main;
        modules[mod_name] = mod;
        delete window.pl_pre_mod[mod_name];
        loading.pop();
        return mod;
    };
})();