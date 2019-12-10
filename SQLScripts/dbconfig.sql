CREATE TABLE IF NOT EXISTS apks (package_name char(255), sha256 char(255) PRIMARY KEY, filename char(255) UNIQUE, malware BOOL DEFAULT 1, downloaded BOOL DEFAULT 0, download_failed BOOL DEFAULT 0, download_url TEXT DEFAULT "NONE" );
CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY , info char(255) UNIQUE);
CREATE TABLE IF NOT EXISTS apk_tags (apk char(255), tag INTEGER, UNIQUE(apk, tag));
CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY, info char(255) UNIQUE)
CREATE TABLE IF NOT EXISTS apk_permissions(apk char(255), permission INTEGER, UNIQUE(apk, permission))
CREATE TABLE IF NOT EXISTS functionalities (id INTEGER PRIMARY KEY, info varchar UNIQUE)
CREATE TABLE IF NOT EXISTS apk_functionalities(apk char(255), functionality INTEGER, UNIQUE(apk, functionality))
CREATE TABLE IF NOT EXISTS commands(id INTEGER PRIMARY KEY, info varchar UNIQUE)
CREATE TABLE IF NOT EXISTS apk_commands(apk char(255), command INTEGER, UNIQUE(apk, command))
CREATE TABLE IF NOT EXISTS libraries(id INTEGER PRIMARY KEY, info varchar UNIQUE)
CREATE TABLE IF NOT EXISTS apk_libraries(apk char(255), library INTEGER, UNIQUE(apk, library))
CREATE TABLE IF NOT EXISTS failing_servers(id INTEGER PRIMARY KEY)