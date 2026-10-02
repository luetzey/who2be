- Der Einladungslink, den Admins in der Mitgliederverwaltung kopieren, trägt den
  Token jetzt im URL-Fragment (`/invitations/accept#token=…`) statt im Pfad.

  Der Token ist URL-sicher kodiert und erreicht damit weder Server- noch
  Proxy-Logs; die Accept-Seite liest ihn aus dem Fragment und nimmt per Body an.
