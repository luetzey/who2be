- dnspython von 2.9.0 auf 2.9.2, opentelemetry-api von 1.45.1 auf 1.45.2 und
  soupsieve von 2.9.2 auf 4.1.3 gehoben (nur `uv.lock`; alle drei transitiv,
  soupsieve über beautifulsoup4 in `apps/api`). Für Python < 3.11.5, das
  soupsieve 4 nicht unterstützt, löst der Lockfile soupsieve 2.10 auf.
