// Temporary standalone config for the a11y static scan (claude-a11y-skill).
import jsxA11y from "eslint-plugin-jsx-a11y";
import tseslint from "typescript-eslint";

export default [
  {
    files: ["src/**/*.tsx", "src/**/*.jsx"],
    plugins: { "jsx-a11y": jsxA11y },
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: { ...jsxA11y.flatConfigs.recommended.rules },
  },
];
