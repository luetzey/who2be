import path from 'node:path'
import { fileURLToPath } from 'node:url'

import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tailwind from 'eslint-plugin-tailwindcss'
import tseslint from 'typescript-eslint'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const tailwindEntry = path.join(__dirname, 'src/styles/globals.css')

const FEATURES = ['auth', 'dashboard', 'personas', 'playbooks', 'tokens']

const APP_SHELL_RESTRICTED_PATH = {
  name: '@/components/layout/AppShell',
  message:
    'AppShell darf nur aus src/app/** importiert werden. Pages mounten den Shell nicht selbst — das macht <AppLayout> auf Route-Ebene.',
}

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
  {
    selector: "JSXOpeningElement[name.name='label']",
    message:
      'Direkter <label>-Tag verboten. Verwende <Label> aus @/components/ui/label oder <FormLabel> innerhalb von <FormItem>.',
  },
]

const crossFeatureOverrides = FEATURES.map((name) => ({
  files: [`src/features/${name}/**/*.{ts,tsx}`],
  rules: {
    'no-restricted-imports': [
      'error',
      {
        paths: [APP_SHELL_RESTRICTED_PATH],
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
  // `e2e/` faehrt unter Playwright (eigener Runner/Globals), nicht unter dem
  // App-/Vitest-ESLint-Profil — daher hier ignoriert (ADR-0032, Phase 4).
  { ignores: ['dist', 'e2e', 'playwright-report', 'test-results'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
    },
    plugins: {
      'jsx-a11y': jsxA11y,
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
      ...jsxA11y.flatConfigs.recommended.rules,
      // eslint-plugin-react-hooks v7 aktiviert die neuen React-Compiler-Regeln
      // als `error`. Das Projekt nutzt den React Compiler (noch) nicht; diese
      // Regeln feuern auf bestehende, legitime Muster (fetch->setState im
      // Effect, BlockNote-/Mantine-Interop u. a.). Bis zu einer bewussten
      // Compiler-Migration advisory (`warn`) — sichtbar, ohne den Build zu
      // brechen. Die klassischen Regeln (rules-of-hooks, exhaustive-deps)
      // bleiben unveraendert `error`.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/incompatible-library': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/use-memo': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'tailwindcss/classnames-order': 'warn',
      'tailwindcss/no-contradicting-classname': 'error',
      'tailwindcss/no-custom-classname': 'off',
    },
  },
  {
    // Roh-HTML-Verbot ueberall ausser den Primitiven selbst: features, app und
    // alle components/** (inkl. editor/, forms/, version/) — nur components/ui/**
    // (die Primitive-Quelle) ist ausgenommen (Override unten). So bricht eine
    // rohe Form-Control kuenftig auch in der Editor-Ecke den Build.
    files: [
      'src/features/**/*.{ts,tsx}',
      'src/components/**/*.{ts,tsx}',
      'src/app/**/*.{ts,tsx}',
    ],
    rules: {
      'no-restricted-syntax': ['error', ...RAW_HTML_FORBIDDEN],
    },
  },
  {
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      // Die Primitive sind die einzige erlaubte Quelle roher HTML-Controls
      // (<Button>/<Input>/<Checkbox>/<RadioGroupItem> kapseln sie hier).
      'no-restricted-syntax': 'off',
      'react-refresh/only-export-components': 'off',
      // shadcn-Primitives nehmen Children via Spread an, jsx-a11y kann das
      // statisch nicht erkennen. Konsumenten setzen die Children — die
      // Page-/Catalog-Tests pruefen das Endergebnis.
      'jsx-a11y/heading-has-content': 'off',
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: [
      'src/app/**/*.{ts,tsx}',
      'src/components/layout/AppShell.tsx',
      'src/features/**/*.{ts,tsx}',
      '**/*.test.{ts,tsx}',
    ],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [APP_SHELL_RESTRICTED_PATH],
        },
      ],
    },
  },
  {
    // Test-Dateien und Test-Helfer (`*.test-utils.tsx`) sind nicht Teil des
    // Fast-Refresh-Graphen — der only-export-components-Check (gemischte
    // Komponenten-/Konstanten-Exports) gilt fuer sie nicht.
    files: ['**/*.test.{ts,tsx}', '**/*.test-utils.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': 'off',
      'no-restricted-imports': 'off',
      'react-refresh/only-export-components': 'off',
    },
  },
  ...crossFeatureOverrides,
)
