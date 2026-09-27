- Die Security-Header der Prod-Domains werden jetzt in CI **auf der Leitung**
  geprueft, nicht nur beschrieben: ein Testlauf faehrt den Reverse-Proxy mit
  der echten Konfiguration hoch und misst die Antwort. Zusaetzlich sichern
  statische Pruefungen die zugesagten Header-Werte ab, damit eine geaenderte
  Zahl auch dann auffaellt, wenn der Container gar nicht erst startet.

  Der Header-Test selbst schlaegt ausserdem fehl, wenn ein Lauf keine einzige
  Pruefung ausgefuehrt hat. Ein Test, der bei falscher Verwendung schweigend
  nichts prueft, erzeugt Vertrauen, das er nicht deckt — deshalb ist die Zahl
  der ausgefuehrten Pruefungen Teil seines Ergebnisses.
