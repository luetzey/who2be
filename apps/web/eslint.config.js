import path from 'node:path'
import { fileURLToPath } from 'node:url'

import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tailwind from 'eslint-plugin-tailwindcss'
import tseslint from 'typescript-eslint'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const tailwindEntry = path.join(__dirname, 'src/styles/globals.css')

const FEATURES = ['auth', 'personas', 'playbooks', 'tokens']

const RAW_HTML_FORBIDDEN = [
  {
    selector: "JSXOpeningElement[name.name='button']",
    message:
      'Direkter <button>-Tag verboten. Verwende <Button> aus @/components/ui/button.',
  },
  {
    selector: "JSXOpeningElement[name.name='input']",
    message:
      'Direkter <input>-Tag verboten. Verwende <Input> aus @/components/ui/input (bzw. <Checkbox>).',
  },
  {
    selector: "JSXOpeningElement[name.name='textarea']",
    message:
      'Direkter <textarea>-Tag verboten. Verwende <Textarea> aus @/components/ui/textarea.',
  },
  {
    selector: "JSXOpeningElement[name.name='a']",
    message:
      'Direkter <a>-Tag verboten. Verwende <Link> aus react-router-dom (ggf. <Button asChild><Link/></Button>).',
  },
]

const crossFeatureOverrides = FEATURES.map((name) => ({
  files: [`src/features/${name}/**/*.{ts,tsx}`],
  rules: {
    'no-restricted-imports': [
      'error',
      {
        patterns: FEATURES.filter((other) => other !== name).flatMap((other) => [
          {
            group: [
              `@/features/${other}/pages/*`,
              `@/features/${other}/components/*`,
              `@/features/${other}/hooks/*`,
              `@/features/${other}/lib/*`,
            ],
            message: `Cross-Feature-Import in features/${name} → features/${other} verboten. Geteiltes nach @/components oder @/hooks hochziehen.`,
          },
        ]),
      },
    ],
  },
}))

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      tailwindcss: tailwind,
    },
    settings: {
      tailwindcss: {
        callees: ['cn', 'clsx', 'twMerge', 'cva'],
        config: tailwindEntry,
      },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'tailwindcss/classnames-order': 'warn',
      'tailwindcss/no-contradicting-classname': 'error',
      'tailwindcss/no-custom-classname': 'off',
    },
  },
  {
    files: [
      'src/features/**/*.{ts,tsx}',
      'src/components/layout/**/*.{ts,tsx}',
      'src/components/data/**/*.{ts,tsx}',
      'src/app/**/*.{ts,tsx}',
    ],
    rules: {
      'no-restricted-syntax': ['error', ...RAW_HTML_FORBIDDEN],
    },
  },
  {
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: ['**/*.test.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': 'off',
      'no-restricted-imports': 'off',
    },
  },
  ...crossFeatureOverrides,
)
