/*
 * Teste pentru logica de potrivire din userscript-ul generat de FocusPilot.
 *
 * Rulare:  node tests/test_userscript.js
 *
 * Funcțiile sunt extrase din fișierul .user.js generat efectiv, nu copiate
 * aici, ca testul să nu se desincronizeze de la cod.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const SCRIPT = path.join(__dirname, '..', 'integrations',
                         'focuspilot_browser_highlighter.user.js');

if (!fs.existsSync(SCRIPT)) {
    console.error('Userscript-ul lipsește. Porniți FocusPilot o dată, sau rulați:');
    console.error('  python -c "from core.config_manager import ConfigManager; ' +
                  'from integrations.userscript_generator import generate_userscript; ' +
                  'generate_userscript(ConfigManager())"');
    process.exit(1);
}

const source = fs.readFileSync(SCRIPT, 'utf8');

/* Extrage o declarație `function nume(...) {...}` din sursă, prin numărarea
   acoladelor de la deschiderea corpului. */
function extract(name) {
    const start = source.indexOf('function ' + name + '(');
    assert.notStrictEqual(start, -1, 'funcția ' + name + ' nu a fost găsită în userscript');
    let depth = 0;
    let i = source.indexOf('{', start);
    const bodyStart = i;
    for (; i < source.length; i++) {
        if (source[i] === '{') { depth++; }
        else if (source[i] === '}') {
            depth--;
            if (depth === 0) { break; }
        }
    }
    return source.slice(start, i + 1);
}

const NAMES = ['wildcardToRegExp', 'patternMatches', 'textMatches', 'criteriaOf', 'hexToRgba'];
const body = NAMES.map(extract).join('\n') + '\nreturn {' + NAMES.join(', ') + '};';
// eslint-disable-next-line no-new-func
const { patternMatches, textMatches, criteriaOf, hexToRgba } = new Function(body)();

let passed = 0;
let failed = 0;

function check(label, fn) {
    try {
        fn();
        passed++;
        console.log('  ok    ' + label);
    } catch (err) {
        failed++;
        console.log('  FAIL  ' + label + '\n        ' + err.message);
    }
}

console.log('\nPotrivirea paginii (URL și titlu):');

check('"*" se potrivește cu orice', function () {
    assert.ok(patternMatches('*', 'https://example.com'));
    assert.ok(patternMatches('', 'https://example.com'));
});

check('wildcard pe URL', function () {
    assert.ok(patternMatches('*tima.siemens.com/otwg20*',
                             'https://tima.siemens.com/otwg20/#/main'));
    assert.ok(!patternMatches('*tima.siemens.com/otwg20*',
                              'https://intranet.example.com/home'));
});

check('cuvânt-cheie fără wildcard = subșir', function () {
    assert.ok(patternMatches('TIMA', 'My TIMA Portal'));
    assert.ok(!patternMatches('TIMA', 'Notepad'));
});

check('alternative separate prin |', function () {
    assert.ok(patternMatches('*Service Platform*|*GSP*', 'GSP Console'));
    assert.ok(patternMatches('*Service Platform*|*GSP*', 'Service Platform Industry'));
    assert.ok(!patternMatches('*Service Platform*|*GSP*', 'Notepad'));
});

check('un URL cu caractere de regex nu strică potrivirea', function () {
    // Un '?' sau '+' din adresă nu trebuie interpretat ca metacaracter regex.
    assert.ok(patternMatches('*search?q=x*', 'https://site.test/search?q=x&page=2'));
    assert.ok(patternMatches('*a+b*', 'https://site.test/a+b/c'));
});

console.log('\nCondițiile de text:');

check('contains', function () {
    assert.ok(textMatches('category', 'Please change category', 'contains', false, false));
    assert.ok(!textMatches('category', 'nothing', 'contains', false, false));
});

check('equals respinge potrivirea parțială', function () {
    assert.ok(textMatches('Status', 'Status', 'equals', false, false));
    assert.ok(!textMatches('Status', 'Status changed', 'equals', false, false));
});

check('starts_with', function () {
    assert.ok(textMatches('Please', 'Please change', 'starts_with', false, false));
    assert.ok(!textMatches('change', 'Please change', 'starts_with', false, false));
});

check('constellation cere toate cuvintele', function () {
    const page = 'ticket merged and waiting';
    assert.ok(textMatches('merged;waiting', page, 'constellation', false, false));
    assert.ok(!textMatches('merged;rejected', page, 'constellation', false, false));
});

check('regex', function () {
    assert.ok(textMatches('ID-\\d{4}', 'ticket ID-2048', 'regex', false, false));
    assert.ok(!textMatches('ID-\\d{4}', 'ticket ID-20', 'regex', false, false));
});

check('regex invalid nu arunca excepție', function () {
    assert.strictEqual(textMatches('[unclosed', 'x', 'regex', false, false), false);
});

check('sensibilitatea la majuscule', function () {
    assert.ok(textMatches('STATUS', 'status', 'contains', false, false));
    assert.ok(!textMatches('STATUS', 'status', 'contains', true, false));
});

check('APOSTROFURILE sunt tratate literal', function () {
    // Textul care spargea XPath-ul din varianta anterioară.
    const needle = "Changed from 'Merge' to 'Wait for Merge'";
    assert.ok(textMatches(needle, 'log: ' + needle + ' today', 'contains', false, false));
    assert.ok(!textMatches(needle, 'unrelated row', 'contains', false, false));
});

check('ghilimelele duble sunt tratate literal', function () {
    const needle = 'field "Priority" is required';
    assert.ok(textMatches(needle, 'error: ' + needle, 'contains', false, false));
});

check('textul cu ; nu este despicat', function () {
    const needle = 'Priority: high; escalate';
    assert.ok(textMatches(needle, 'row ' + needle, 'contains', false, false));
    assert.ok(!textMatches(needle, 'escalate', 'contains', false, false));
});

console.log('\nCriterii:');

check('criteriul principal rămâne o singură frază', function () {
    const out = criteriaOf({ search_text: "Changed from 'Merge' to 'Wait for Merge'" });
    assert.deepStrictEqual(out, ["Changed from 'Merge' to 'Wait for Merge'"]);
});

check('criterii suplimentare din listă', function () {
    const out = criteriaOf({ search_text: 'a', additional_criteria: ['b', 'c'] });
    assert.deepStrictEqual(out, ['a', 'b', 'c']);
});

check('fără criterii', function () {
    assert.deepStrictEqual(criteriaOf({}), []);
});

console.log('\nCulori:');

check('hex -> rgba cu opacitatea configurată', function () {
    assert.strictEqual(hexToRgba('#FF3333', 0.25), 'rgba(255,51,51,0.25)');
});

check('hex invalid cade pe o valoare utilizabilă', function () {
    assert.ok(hexToRgba('nu-e-culoare', 0.2).startsWith('rgba('));
});

console.log('\n' + passed + ' trecute, ' + failed + ' eșuate.');
process.exit(failed === 0 ? 0 : 1);
