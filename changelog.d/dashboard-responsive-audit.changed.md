- Dashboard-Ansicht auf schmalen Viewports abgefedert (#563): das Label des
  Statusbalkens federt seine feste Breite ab (`w-20 truncate md:w-24`), die
  Seitensteuerung des Aktivitäts-Feeds bricht auf 320px um und hält unterhalb
  `md` das 40px-Hit-Target, und die Legende der Status-Verteilung schrumpft
  mit, statt bei langen Labels zu überlaufen.
