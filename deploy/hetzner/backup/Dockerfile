# Backup-Container fuer den Hetzner-Stack (C5a + C5b).
# - postgresql16-client liefert `pg_dump`/`pg_restore`
# - gnupg verschluesselt den Dump mit dem Recipient-Public-Key (ADR-0011)
# - restic + openssh-client sind der Offsite-Pfad (SFTP zur Hetzner-Storage-Box)
# - curl pingt den self-hosted Heartbeat-Empfaenger (BACKUP_HEARTBEAT_URL, #541)
# - aws-cli spiegelt den SeaweedFS-Bucket (ADR-0048, W8/M3) — generischer
#   S3-Client, bewusst nicht `mc` (dessen Docker-Hub-Namespace ist derselbe,
#   den #525/#528 gerade verlassen haben)
# - sqlite liefert `VACUUM INTO` fuer die Tabellen-Store-Snapshots (ADR-0049)
# - su-exec laesst den Tabellen-Store-Lesevorgang unter der Kennung des
#   Datei-Eigentuemers laufen, damit WAL-Seitendateien nicht dem Backup-Nutzer
#   gehoeren und der Schreibpfad der API unberuehrt bleibt (Begruendung in
#   backup.sh, Stufe 3)
# Build-Context ist `deploy/hetzner/` (siehe who2be/docker-compose.yml).

FROM alpine:3.24

RUN apk add --no-cache \
      aws-cli \
      bash \
      coreutils \
      curl \
      findutils \
      gnupg \
      openssh-client \
      postgresql16-client \
      restic \
      sqlite \
      su-exec

COPY scripts/backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

# GPG-Home und SSH-Secrets werden zur Laufzeit als read-only Volume gemountet.
# Wir laufen als root, weil pg_dump-Streams ueber Unix-Pipes laufen — der Container
# hat ohnehin keine offene Surface (kein Listener, kein Web).

ENTRYPOINT ["/usr/local/bin/backup.sh"]
