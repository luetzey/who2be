# Third-Party Licenses

Who2Be selbst steht unter FSL-1.1-Apache-2.0 (siehe `LICENSE`).
Dieses Dokument listet die Drittanbieter-Abhaengigkeiten der
distribuierten Artefakte samt Lizenzen. Es wird generiert mit
`bash scripts/gen_third_party_notices.sh` und nutzt dieselben Tools
wie die CI-License-Gates (ADR-0033).

Generiert am: 2026-07-22

## Python (uv-Workspace: who2be-api, who2be-mcp, who2be-models, who2be-billing)

| Name                      | Version   | License                              |
|---------------------------|-----------|--------------------------------------|
| Authlib                   | 1.7.2     | BSD License                          |
| Deprecated                | 1.3.1     | MIT License                          |
| PyJWT                     | 2.13.0    | MIT                                  |
| PyYAML                    | 6.0.3     | MIT License                          |
| Pygments                  | 2.20.0    | BSD-2-Clause                         |
| SecretStorage             | 3.5.0     | BSD-3-Clause                         |
| aiofile                   | 3.11.1    | Apache-2.0                           |
| annotated-doc             | 0.0.4     | MIT                                  |
| annotated-types           | 0.7.0     | MIT License                          |
| anyio                     | 4.13.0    | MIT                                  |
| ast_serialize             | 0.5.0     | MIT                                  |
| asyncpg                   | 0.31.0    | Apache-2.0                           |
| attrs                     | 26.1.0    | MIT                                  |
| backports.tarfile         | 1.2.0     | MIT License                          |
| beartype                  | 0.22.9    | MIT License                          |
| cachetools                | 7.1.3     | MIT                                  |
| caio                      | 0.9.25    | Apache-2.0                           |
| certifi                   | 2026.5.20 | Mozilla Public License 2.0 (MPL 2.0) |
| cffi                      | 2.0.0     | MIT                                  |
| charset-normalizer        | 3.4.7     | MIT                                  |
| click                     | 8.4.0     | BSD-3-Clause                         |
| coverage                  | 7.14.1    | Apache-2.0                           |
| cryptography              | 49.0.0    | Apache-2.0 OR BSD-3-Clause           |
| cyclopts                  | 4.14.1    | Apache-2.0                           |
| dnspython                 | 2.8.0     | ISC License (ISCL)                   |
| docker                    | 7.1.0     | Apache-2.0                           |
| docstring_parser          | 0.18.0    | MIT License                          |
| email-validator           | 2.3.0     | The Unlicense (Unlicense)            |
| exceptiongroup            | 1.3.1     | MIT License                          |
| fastapi                   | 0.137.0   | MIT                                  |
| fastmcp                   | 3.4.2     | Apache-2.0                           |
| fastmcp-slim              | 3.4.2     | Apache-2.0                           |
| griffelib                 | 2.0.2     | ISC                                  |
| h11                       | 0.16.0    | MIT License                          |
| httpcore                  | 1.0.9     | BSD-3-Clause                         |
| httptools                 | 0.8.0     | MIT                                  |
| httpx                     | 0.28.1    | BSD License                          |
| httpx-sse                 | 0.4.3     | MIT                                  |
| idna                      | 3.15      | BSD-3-Clause                         |
| importlib_metadata        | 9.0.0     | Apache-2.0                           |
| iniconfig                 | 2.3.0     | MIT                                  |
| jaraco.classes            | 3.4.0     | MIT License                          |
| jaraco.context            | 6.1.2     | MIT                                  |
| jaraco.functools          | 4.5.0     | MIT                                  |
| jeepney                   | 0.9.0     | MIT                                  |
| joserfc                   | 1.7.2     | BSD License                          |
| jsonref                   | 1.1.0     | MIT                                  |
| jsonschema                | 4.26.0    | MIT                                  |
| jsonschema-path           | 0.5.0     | Apache Software License              |
| jsonschema-specifications | 2025.9.1  | MIT                                  |
| keyring                   | 25.7.0    | MIT                                  |
| librt                     | 0.11.0    | MIT                                  |
| limits                    | 5.8.0     | MIT                                  |
| markdown-it-py            | 4.2.0     | MIT License                          |
| mcp                       | 1.28.1    | MIT License                          |
| mdurl                     | 0.1.2     | MIT License                          |
| more-itertools            | 11.0.2    | MIT                                  |
| mypy                      | 2.1.0     | MIT                                  |
| mypy_extensions           | 1.1.0     | MIT                                  |
| openapi-pydantic          | 0.5.1     | MIT License                          |
| opentelemetry-api         | 1.42.0    | Apache-2.0                           |
| packaging                 | 26.2      | Apache-2.0 OR BSD-2-Clause           |
| pathable                  | 0.6.0     | Apache Software License              |
| pathspec                  | 1.1.1     | Mozilla Public License 2.0 (MPL 2.0) |
| platformdirs              | 4.9.6     | MIT                                  |
| pluggy                    | 1.6.0     | MIT License                          |
| py-key-value-aio          | 0.4.4     | Apache Software License              |
| pycparser                 | 3.0       | BSD-3-Clause                         |
| pydantic                  | 2.13.4    | MIT                                  |
| pydantic-settings         | 2.14.2    | MIT                                  |
| pydantic_core             | 2.46.4    | MIT                                  |
| pyperclip                 | 1.11.0    | BSD License                          |
| pytest                    | 9.1.0     | MIT                                  |
| pytest-cov                | 7.1.0     | MIT                                  |
| python-dotenv             | 1.2.2     | BSD-3-Clause                         |
| python-multipart          | 0.0.32    | Apache-2.0                           |
| redis                     | 8.0.0     | MIT                                  |
| referencing               | 0.37.0    | MIT                                  |
| requests                  | 2.34.2    | Apache Software License              |
| rich                      | 15.0.0    | MIT License                          |
| rich-rst                  | 2.0.1     | MIT                                  |
| rpds-py                   | 0.30.0    | MIT                                  |
| ruff                      | 0.15.17   | MIT                                  |
| slowapi                   | 0.1.10    | MIT License                          |
| sse-starlette             | 3.4.4     | BSD-3-Clause                         |
| starlette                 | 1.3.1     | BSD-3-Clause                         |
| structlog                 | 26.1.0    | MIT OR Apache-2.0                    |
| testcontainers            | 4.14.2    | Apache-2.0                           |
| typing-inspection         | 0.4.2     | MIT                                  |
| typing_extensions         | 4.15.0    | PSF-2.0                              |
| uncalled-for              | 0.3.2     | MIT License                          |
| urllib3                   | 2.7.0     | MIT                                  |
| uvicorn                   | 0.49.0    | BSD-3-Clause                         |
| uvloop                    | 0.22.1    | Apache Software License; MIT License |
| watchfiles                | 1.2.0     | MIT License                          |
| websockets                | 16.0      | BSD-3-Clause                         |
| wrapt                     | 2.2.1     | BSD-2-Clause                         |
| zipp                      | 4.1.0     | MIT                                  |

## Web (apps/web, Production-Bundle ohne devDependencies)

- [@babel/runtime@7.29.2](https://github.com/babel/babel) - MIT
- [@blocknote/core@0.51.4](https://github.com/TypeCellOS/BlockNote) - MPL-2.0
- [@blocknote/mantine@0.51.4](https://github.com/TypeCellOS/BlockNote) - MPL-2.0
- [@blocknote/react@0.51.4](https://github.com/TypeCellOS/BlockNote) - MPL-2.0
- [@emoji-mart/data@1.2.1](https://github.com/missive/emoji-mart) - MIT
- [@floating-ui/core@1.7.5](https://github.com/floating-ui/floating-ui) - MIT
- [@floating-ui/dom@1.7.6](https://github.com/floating-ui/floating-ui) - MIT
- [@floating-ui/react-dom@2.1.8](https://github.com/floating-ui/floating-ui) - MIT
- [@floating-ui/react@0.27.19](https://github.com/floating-ui/floating-ui) - MIT
- [@floating-ui/utils@0.2.11](https://github.com/floating-ui/floating-ui) - MIT
- [@handlewithcare/prosemirror-inputrules@0.1.4](undefined) - MIT
- [@hookform/resolvers@5.4.0](https://github.com/react-hook-form/resolvers) - MIT
- [@jridgewell/gen-mapping@0.3.13](https://github.com/jridgewell/sourcemaps) - MIT
- [@jridgewell/remapping@2.3.5](https://github.com/jridgewell/sourcemaps) - MIT
- [@jridgewell/resolve-uri@3.1.2](https://github.com/jridgewell/resolve-uri) - MIT
- [@jridgewell/sourcemap-codec@1.5.5](https://github.com/jridgewell/sourcemaps) - MIT
- [@jridgewell/trace-mapping@0.3.31](https://github.com/jridgewell/sourcemaps) - MIT
- [@mantine/core@8.3.18](https://github.com/mantinedev/mantine) - MIT
- [@mantine/hooks@8.3.18](https://github.com/mantinedev/mantine) - MIT
- [@oxc-project/types@0.133.0](https://github.com/oxc-project/oxc) - MIT
- [@radix-ui/primitive@1.1.4](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-arrow@1.1.9](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-collection@1.1.9](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-compose-refs@1.1.3](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-context@1.1.4](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-dialog@1.1.16](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-direction@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-dismissable-layer@1.1.12](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-dropdown-menu@2.1.17](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-focus-guards@1.1.4](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-focus-scope@1.1.9](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-id@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-label@2.1.9](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-menu@2.1.17](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-popover@1.1.16](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-popper@1.3.0](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-portal@1.1.11](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-presence@1.1.6](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-primitive@2.1.5](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-radio-group@1.4.0](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-roving-focus@1.1.12](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-slot@1.2.5](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-tooltip@1.2.9](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-callback-ref@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-controllable-state@1.2.3](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-effect-event@0.0.3](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-escape-keydown@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-layout-effect@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-previous@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-rect@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-use-size@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/react-visually-hidden@1.2.5](https://github.com/radix-ui/primitives) - MIT
- [@radix-ui/rect@1.1.2](https://github.com/radix-ui/primitives) - MIT
- [@rolldown/binding-linux-x64-gnu@1.0.3](https://github.com/rolldown/rolldown) - MIT
- [@rolldown/binding-linux-x64-musl@1.0.3](https://github.com/rolldown/rolldown) - MIT
- [@rolldown/pluginutils@1.0.1](https://github.com/rolldown/plugins) - MIT
- [@shikijs/types@4.1.0](https://github.com/shikijs/shiki) - MIT
- [@shikijs/vscode-textmate@10.0.2](https://github.com/shikijs/vscode-textmate) - MIT
- [@standard-schema/utils@0.3.0](https://github.com/standard-schema/standard-schema) - MIT
- [@supabase/auth-js@2.108.1](https://github.com/supabase/supabase-js) - MIT
- [@supabase/functions-js@2.108.1](https://github.com/supabase/supabase-js) - MIT
- [@supabase/phoenix@0.4.2](https://github.com/supabase/phoenix) - MIT
- [@supabase/postgrest-js@2.108.1](https://github.com/supabase/supabase-js) - MIT
- [@supabase/realtime-js@2.108.1](https://github.com/supabase/supabase-js) - MIT
- [@supabase/storage-js@2.108.1](https://github.com/supabase/supabase-js) - MIT
- [@supabase/supabase-js@2.108.1](https://github.com/supabase/supabase-js) - MIT
- [@tailwindcss/node@4.3.1](https://github.com/tailwindlabs/tailwindcss) - MIT
- [@tailwindcss/oxide-linux-x64-gnu@4.3.1](https://github.com/tailwindlabs/tailwindcss) - MIT
- [@tailwindcss/oxide-linux-x64-musl@4.3.1](https://github.com/tailwindlabs/tailwindcss) - MIT
- [@tailwindcss/oxide@4.3.1](https://github.com/tailwindlabs/tailwindcss) - MIT
- [@tailwindcss/vite@4.3.1](https://github.com/tailwindlabs/tailwindcss) - MIT
- [@tanstack/react-store@0.7.7](https://github.com/TanStack/store) - MIT
- [@tanstack/store@0.7.7](https://github.com/TanStack/store) - MIT
- [@tiptap/core@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-bold@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-bubble-menu@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-code@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-floating-menu@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-horizontal-rule@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-italic@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-paragraph@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-strike@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-text@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-underline@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extensions@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/pm@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/react@3.23.6](https://github.com/ueberdosis/tiptap) - MIT
- [@types/hast@3.0.4](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/node@25.9.3](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/prop-types@15.7.15](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/react-dom@18.3.7](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/react@18.3.29](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/unist@3.0.3](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/use-sync-external-store@0.0.6](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/use-sync-external-store@1.5.0](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [aria-hidden@1.2.6](https://github.com/theKashey/aria-hidden) - MIT
- [class-variance-authority@0.7.1](https://github.com/joe-bell/cva) - Apache-2.0
- [clsx@2.1.1](https://github.com/lukeed/clsx) - MIT
- [cookie@1.1.1](https://github.com/jshttp/cookie) - MIT
- [csstype@3.2.3](https://github.com/frenic/csstype) - MIT
- [detect-libc@2.1.2](https://github.com/lovell/detect-libc) - Apache-2.0
- [detect-node-es@1.1.0](https://github.com/thekashey/detect-node) - MIT
- [emoji-mart@5.6.0](https://github.com/missive/emoji-mart) - MIT
- [enhanced-resolve@5.21.6](https://github.com/webpack/enhanced-resolve) - MIT
- [fast-deep-equal@3.1.3](https://github.com/epoberezkin/fast-deep-equal) - MIT
- [fast-equals@5.4.0](https://github.com/planttheidea/fast-equals) - MIT
- [fdir@6.5.0](https://github.com/thecodrr/fdir) - MIT
- [get-nonce@1.0.1](https://github.com/theKashey/get-nonce) - MIT
- [graceful-fs@4.2.11](https://github.com/isaacs/node-graceful-fs) - ISC
- [html-parse-stringify@3.0.1](https://github.com/henrikjoreteg/html-parse-stringify) - MIT
- [i18next-browser-languagedetector@8.2.1](https://github.com/i18next/i18next-browser-languageDetector) - MIT
- [i18next@26.3.1](https://github.com/i18next/i18next) - MIT
- [iceberg-js@0.8.1](https://github.com/supabase/iceberg-js) - MIT
- [isomorphic.js@0.2.5](https://github.com/dmonad/isomorphic.js) - MIT
- [jiti@2.7.0](https://github.com/unjs/jiti) - MIT
- [js-tokens@4.0.0](https://github.com/lydell/js-tokens) - MIT
- [lib0@0.2.117](https://github.com/dmonad/lib0) - MIT
- [lightningcss-linux-x64-gnu@1.32.0](https://github.com/parcel-bundler/lightningcss) - MPL-2.0
- [lightningcss-linux-x64-musl@1.32.0](https://github.com/parcel-bundler/lightningcss) - MPL-2.0
- [lightningcss@1.32.0](https://github.com/parcel-bundler/lightningcss) - MPL-2.0
- [lodash.merge@4.6.2](https://github.com/lodash/lodash) - MIT
- [loose-envify@1.4.0](https://github.com/zertosh/loose-envify) - MIT
- [lucide-react@1.18.0](https://github.com/lucide-icons/lucide) - ISC
- [magic-string@0.30.21](https://github.com/Rich-Harris/magic-string) - MIT
- [nanoid@3.3.12](https://github.com/ai/nanoid) - MIT
- [orderedmap@2.1.1](https://github.com/marijnh/orderedmap) - MIT
- [picocolors@1.1.1](https://github.com/alexeyraspopov/picocolors) - ISC
- [picomatch@4.0.4](https://github.com/micromatch/picomatch) - MIT
- [postcss@8.5.15](https://github.com/postcss/postcss) - MIT
- [prosemirror-changeset@2.4.1](git+https://code.haverbeke.berlin/prosemirror/prosemirror-changeset) - MIT
- [prosemirror-commands@1.7.1](https://github.com/prosemirror/prosemirror-commands) - MIT
- [prosemirror-dropcursor@1.8.2](https://github.com/prosemirror/prosemirror-dropcursor) - MIT
- [prosemirror-gapcursor@1.4.1](https://github.com/prosemirror/prosemirror-gapcursor) - MIT
- [prosemirror-highlight@0.15.1](https://github.com/ocavue/prosemirror-highlight) - MIT
- [prosemirror-history@1.5.0](https://github.com/prosemirror/prosemirror-history) - MIT
- [prosemirror-keymap@1.2.3](https://github.com/prosemirror/prosemirror-keymap) - MIT
- [prosemirror-model@1.25.7](git+https://code.haverbeke.berlin/prosemirror/prosemirror-model) - MIT
- [prosemirror-schema-list@1.5.1](https://github.com/prosemirror/prosemirror-schema-list) - MIT
- [prosemirror-state@1.4.4](https://github.com/prosemirror/prosemirror-state) - MIT
- [prosemirror-tables@1.8.5](https://github.com/ProseMirror/prosemirror-tables) - MIT
- [prosemirror-transform@1.12.0](https://github.com/prosemirror/prosemirror-transform) - MIT
- [prosemirror-view@1.41.8](git+https://code.haverbeke.berlin/prosemirror/prosemirror-view) - MIT
- [react-dom@18.3.1](https://github.com/facebook/react) - MIT
- [react-hook-form@7.79.0](https://github.com/react-hook-form/react-hook-form) - MIT
- [react-i18next@17.0.8](https://github.com/i18next/react-i18next) - MIT
- [react-icons@5.6.0](https://github.com/react-icons/react-icons) - MIT
- [react-number-format@5.4.5](https://github.com/s-yadav/react-number-format) - MIT
- [react-remove-scroll-bar@2.3.8](https://github.com/theKashey/react-remove-scroll-bar) - MIT
- [react-remove-scroll@2.7.2](https://github.com/theKashey/react-remove-scroll) - MIT
- [react-router-dom@7.17.0](https://github.com/remix-run/react-router) - MIT
- [react-router@7.17.0](https://github.com/remix-run/react-router) - MIT
- [react-style-singleton@2.2.3](https://github.com/theKashey/react-style-singleton) - MIT
- [react-textarea-autosize@8.5.9](https://github.com/Andarist/react-textarea-autosize) - MIT
- [react@18.3.1](https://github.com/facebook/react) - MIT
- [rolldown@1.0.3](https://github.com/rolldown/rolldown) - MIT
- [rope-sequence@1.3.4](https://github.com/marijnh/rope-sequence) - MIT
- [scheduler@0.23.2](https://github.com/facebook/react) - MIT
- [set-cookie-parser@2.7.2](https://github.com/nfriedly/set-cookie-parser) - MIT
- [sonner@2.0.7](https://github.com/emilkowalski/sonner) - MIT
- [source-map-js@1.2.1](https://github.com/7rulnik/source-map-js) - BSD-3-Clause
- [tabbable@6.4.0](https://github.com/focus-trap/tabbable) - MIT
- [tailwind-merge@3.6.0](https://github.com/dcastil/tailwind-merge) - MIT
- [tailwindcss-animate@1.0.7](undefined) - MIT
- [tailwindcss@4.3.1](https://github.com/tailwindlabs/tailwindcss) - MIT
- [tapable@2.3.3](https://github.com/webpack/tapable) - MIT
- [tinyglobby@0.2.17](https://github.com/SuperchupuDev/tinyglobby) - MIT
- [tslib@2.8.1](https://github.com/Microsoft/tslib) - 0BSD
- [type-fest@4.41.0](https://github.com/sindresorhus/type-fest) - (MIT OR CC0-1.0)
- [typescript@6.0.3](https://github.com/microsoft/TypeScript) - Apache-2.0
- [undici-types@7.24.6](https://github.com/nodejs/undici) - MIT
- [use-callback-ref@1.3.3](https://github.com/theKashey/use-callback-ref) - MIT
- [use-composed-ref@1.4.0](https://github.com/Andarist/use-composed-ref) - MIT
- [use-isomorphic-layout-effect@1.2.1](https://github.com/Andarist/use-isomorphic-layout-effect) - MIT
- [use-latest@1.3.0](https://github.com/Andarist/use-latest) - MIT
- [use-sidecar@1.1.3](https://github.com/theKashey/use-sidecar) - MIT
- [use-sync-external-store@1.6.0](https://github.com/facebook/react) - MIT
- [vite@8.0.16](https://github.com/vitejs/vite) - MIT
- [void-elements@3.1.0](https://github.com/pugjs/void-elements) - MIT
- [w3c-keyname@2.2.8](https://github.com/marijnh/w3c-keyname) - MIT
- [y-prosemirror@1.3.7](https://github.com/yjs/y-prosemirror) - MIT
- [y-protocols@1.0.7](https://github.com/yjs/y-protocols) - MIT
- [yjs@13.6.31](https://github.com/yjs/yjs) - MIT
- [zod@4.4.3](https://github.com/colinhacks/zod) - MIT

