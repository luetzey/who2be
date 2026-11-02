- Cloud-Deploy: Die Rechnungs-Schalter `WHO2BE_INVOICE_TAX_MODE` (ohne
  Default, leer heißt Checkout 503 und keine Rechnung) und
  `WHO2BE_INVOICE_PRICE_BASIS` (Default `net`) kommen jetzt in allen drei
  Cloud-Overlays (Root, Hetzner, Dokploy) in `api` und `worker` an. Der
  `worker` bekommt außerdem `MOLLIE_API_KEY`; ohne ihn brach die Routine
  `invoice-retry` ab und es entstand keine Rechnung. `.env.example` nennt
  beide Schalter.

  Doku nach ADR-0061: GoBD-Verfahrensdokumentation §1, §4 und §5 neu gefasst
  (Rechnung je Zahlung, Archiv, Schalter, Storno), Storno-Ablauf und
  Fehlerbilder in der Cloud-Erstinbetriebnahme, ausgestellte Rechnungen im
  VVT und im Löschkonzept.
