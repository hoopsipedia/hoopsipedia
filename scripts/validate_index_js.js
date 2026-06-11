// Validate that every inline <script> block in index.html parses as JavaScript.
// A single syntax error in the monolithic index.html takes down the whole site,
// so this runs in the pre-push hook AND in CI (.github/workflows/ci.yml).
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const htmlPath = path.join(__dirname, '..', 'index.html');
const html = fs.readFileSync(htmlPath, 'utf8');

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
        scripts.push({ code: html.substring(startTag + 1, end), line: html.substring(0, start).split('\n').length });
    }
    idx = end + 9;
}

let errors = 0;
for (const s of scripts) {
    try {
        vm.createScript(s.code, { filename: 'index.html' });
    } catch (e) {
        errors++;
        const errLine = e.lineNumber ? (s.line + e.lineNumber - 1) : s.line;
        console.error('❌ JS Syntax Error near line ' + errLine + ': ' + e.message);
    }
}

if (errors > 0) {
    console.error('\n❌ Found ' + errors + ' syntax error(s).');
    process.exit(1);
} else {
    console.log('✅ JavaScript syntax check passed (' + scripts.length + ' inline script blocks)');
}
