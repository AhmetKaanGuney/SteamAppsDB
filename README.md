### Python Version == 3.10.1

### Roles of The Program:

- Update and manage DB daily
- Respond to API requests

### Request Limitations:

- Steamspy Request Rate: 1 request per second
- Steam Max Request Count: 100.000 per day

### Files:

/db :
- \__init__.py : Creates apps.db and executes init.sql
- appdata.py : Has AppDetails and AppSnippet classes for intefacing between functions
- applist.json : Raw applist data straight from steam api
(gets updated every time update.py is called)
- apps.db : Database for apps , tags, genres and categories
- database.py : Interface for interacting with database
- errors.py : Custom errors
- init.sql : Initialisation script for sqlite3 database
- update_log.json : Update progress is saved here
- update_logger.py : Class for managing update_log
- update.py : Gets applist from steam, then gets details from steamspy and steam
then saves app details to database