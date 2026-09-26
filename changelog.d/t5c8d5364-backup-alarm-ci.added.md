### Backup-Alarm-Suite laeuft in der CI

Der CI-Job `backup-alarm` fuehrt `deploy/hetzner/tests/test_backup_alarm.sh`
aus und haengt an `all-green`. Die Suite (14 Faelle, 60 Assertions) belegt die
Kernzusagen der Backup-Automatisierung — Teilerfolg loest keinen gruenen
Heartbeat aus (#541, W8/M3), der Lauf verbiegt den SQLite-Schreibpfad der API
nicht, ein volllaufendes Backup-Ziel macht den Lauf rot und laesst den letzten
guten Snapshot unversehrt. Bis hierher lief sie in keinem Workflow; die
Assertions hingen daran, dass jemand das Skript von Hand startet.

- `BACKUP_ALARM_REQUIRE_ALL=1` macht jeden uebersprungenen Fall zum Fehlschlag
  (Haltung wie `WHO2BE_REQUIRE_DB=1` und `assert_skips_within_budget.py`:
  uebersprungen ist nicht bestanden). Der CI-Job setzt den Schalter, lokal
  bleibt das Verhalten unveraendert. Belegt mit einer Negativprobe: bei
  erzwungenem Skip ist der Lauf ohne Schalter gruen, mit Schalter rot.
- Die Suite bilanziert am Ende `CASES_TOTAL`/`CASES_RUN`/`CASES_SKIPPED`/
  `SKIPPED_CASES` (auch in der Step-Summary). Damit ist ablesbar, welche der
  14 Faelle auf dem Runner wirklich gelaufen sind, statt es zu vermuten — die
  Faelle 12–14 brauchen unprivilegierte User-Namespaces und ein eigenes tmpfs;
  ein eigener Job-Step misst diese Faehigkeiten und protokolliert sie.
- Die Fälle 12–14 brauchen unprivilegierte User-Namespaces; `ubuntu-latest`
  (24.04) sperrt die per AppArmor (gemessen: `CASES_RUN=12`, der Job wurde
  dadurch rot). Ein Job-Step schaltet sie per
  `kernel.apparmor_restrict_unprivileged_userns=0` frei und prüft die Fähigkeit
  fail-closed; danach laufen auf dem Runner alle 14 Fälle (`CASES_SKIPPED=0`).
- `scripts/ci/test_all_green_matrix.py` lief selbst in keinem Job (`testpaths`
  kennt `scripts/tests`, nicht `scripts/ci`). Der Wrapper
  `scripts/tests/test_ci_all_green_matrix.py` bindet die Wahrheitstabelle in die
  pytest-Suite; eine neue Zusicherung prueft, dass jeder Job in
  `all-green.needs` auch seine `env`-Variable und seine `expect`-Zeile hat, und
  eine zweite, dass `GATED_JOBS` die gegateten Jobs aus `ci.yml` vollstaendig
  kennt.
