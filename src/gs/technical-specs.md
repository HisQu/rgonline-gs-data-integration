# Germania Sacra API Technical Specifications

## Fetching a TTL file of all persons
```http request
GET https://personendatenbank.germania-sacra.de/api/v1.0/person?query[0][field]=person.vorname&query[0][operator]=contains&query[0][value]=&query[0][connector]=and&query[1][field]=person.familienname&query[1][operator]=contains&query[1][value]=&query[1][connector]=and&query[2][field]=amt.bezeichnung&query[2][operator]=contains&query[2][value]=&query[2][connector]=and&query[3][field]=fundstelle.bandtitel&query[3][operator]=contains&query[3][value]=&format=turtle
```