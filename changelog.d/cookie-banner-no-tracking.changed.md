- Cookie banner no longer shows an operator placeholder
  (`<PLATZHALTER: name analytics/tracking services>`) and no longer offers a
  choice between "Necessary only" and "Accept all": the app loads no analytics
  or tracking (measured: no third-party request on first visit or after the
  former "Accept all", no cookie set), so both buttons had the same effect.
  The banner is now a notice with a single "Got it" button. Visitors who
  already chose either option under the old banner are not asked again.
