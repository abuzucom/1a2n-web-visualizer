// ESLint config backing AGENTS.md's "Code quality" section. Only the
// mechanically-lintable rules are enforced here (nesting depth, function
// size, line length, empty catches, assignment-in-conditionals); the
// semantic/architectural ones (regex backtracking, single responsibility,
// composition over inheritance, safe collection mutation, divisor checks)
// have no direct ESLint equivalent and stay as human-reviewed guidance.
// AGENTS.md's "under 10 locals per function" also has no core ESLint rule
// and is not enforced here.
const js = require('@eslint/js');

const codeQualityRules = {
  'max-depth': ['error', 3],
  'max-lines-per-function': ['error', { max: 60, skipBlankLines: true, skipComments: true }],
  'max-len': ['error', { code: 120 }],
  'no-empty': ['error', { allowEmptyCatch: false }],
  'no-cond-assign': ['error', 'always'],
};

module.exports = [
  {
    files: ['src/js/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        window: 'readonly',
        document: 'readonly',
        navigator: 'readonly',
        console: 'readonly',
        // Provided by visualizer-core.js, loaded via its own <script> tag
        // before obs-ui.js/fullscreen-ui.js (classic scripts, not modules).
        BCViz: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        requestAnimationFrame: 'readonly',
        AudioContext: 'readonly',
        localStorage: 'readonly',
        location: 'readonly',
        fetch: 'readonly',
        // AudioWorklet globals, available only inside render-tick-processor.js,
        // which the browser loads through audioWorklet.addModule.
        AudioWorkletProcessor: 'readonly',
        registerProcessor: 'readonly',
        sampleRate: 'readonly',
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      ...codeQualityRules,
    },
  },
  {
    files: ['tools/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'commonjs',
      globals: {
        require: 'readonly',
        module: 'readonly',
        process: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        console: 'readonly',
        Buffer: 'readonly',
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      ...codeQualityRules,
    },
  },
];
