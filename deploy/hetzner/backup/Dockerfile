# Backup-Container fuer den Hetzner-Stack (C5a + C5b).
# - postgresql16-client liefert `pg_dump`/`pg_restore`
# - gnupg verschluesselt den Dump mit dem Recipient-Public-Key (ADR-0011)
# - restic + openssh-client sind der Offsite-Pfad (SFTP zur Hetzner-Storage-Box)
# Build-Context ist `deploy/hetzner/` (siehe who2be/docker-compose.yml).

FROM alpine:3.23

RUN apk add --no-cache \
      bash \
      coreutils \
      findutils \
      gnupg \
      openssh-client \
      postgresql16-client \
      restic

COPY scripts/backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

# GPG-Home und SSH-Secrets werden zur Laufzeit als read-only Volume gemountet.
# Wir laufen als root, weil pg_dump-Streams ueber Unix-Pipes laufen — der Container
# hat ohnehin keine offene Surface (kein Listener, kein Web).

ENTRYPOINT ["/usr/local/bin/backup.sh"]
