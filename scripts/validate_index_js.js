// Validate that the site's JavaScript parses: app.js (the SPA, extracted from
// the old index.html monolith) plus every inline <script> block still in
// index.html. A single syntax error takes down the whole site, so this runs
// in the pre-push hook AND in CI (.github/workflows/ci.yml).
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

// Extract inline script blocks
const scripts = [];
let idx = 0;
while (true) {
    const start = html.indexOf('<script', idx);
    if (start === -1) break;
    const startTag = html.indexOf('>', start);
    const end = html.indexOf('</script>', startTag);
    if (startTag === -1 || end === -1) break;
    const tag = html.substring(start, startTag + 1);
    if (!tag.includes('src=') && !tag.includes('type="application/json"') && !tag.includes("type='application/json'")) {
        scripts.push({ code: html.substring(startTag + 1, end), line: html.substring(0, start).split('\n').length, file: 'index.html' });
    }
    idx = end + 9;
}

// External app bundle(s) referenced from index.html
const externals = ['app.js'];
for (const name of externals) {
    const p = path.join(root, name);
    if (!fs.existsSync(p)) {
        console.error('❌ Missing ' + name + ' (referenced by index.html)');
        process.exit(1);
    }
    if (!html.includes('/' + name + '?v=')) {
        console.error('❌ index.html does not reference /' + name + ' with a version stamp');
        process.exit(1);
    }
    scripts.push({ code: fs.readFileSync(p, 'utf8'), line: 1, file: name });
}

let errors = 0;
for (const s of scripts) {
    try {
        vm.createScript(s.code, { filename: s.file });
    } catch (e) {
        errors++;
        const errLine = e.lineNumber ? (s.line + e.lineNumber - 1) : s.line;
        console.error('❌ JS Syntax Error in ' + s.file + ' near line ' + errLine + ': ' + e.message);
    }
}

if (errors > 0) {
    console.error('\n❌ Found ' + errors + ' syntax error(s).');
    process.exit(1);
} else {
    console.log('✅ JavaScript syntax check passed (' + scripts.length + ' script blocks incl. ' + externals.join(', ') + ')');
}
