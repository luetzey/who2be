- German error messages in the web interface now use real umlauts and ß as
  well, for example "Ungültige oder fehlende Anmeldedaten" and "Persona oder
  Template existiert nicht in diesem Workspace". Only the German web
  translations under `common.errors.*` change; the error codes and the API's
  own error texts stay unchanged. The umlaut test now covers these messages
  too, so only the slash-menu search aliases keep their ASCII spelling.
