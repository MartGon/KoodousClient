CREATE TABLE IF NOT EXISTS apks (package_name char(255), sha256 char(255) PRIMARY KEY, filename char(255) UNIQUE, malware BOOL DEFAULT 1, downloaded BOOL DEFAULT 0, download_failed BOOL DEFAULT 0, download_url TEXT DEFAULT "NONE" );
CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY , info char(255) UNIQUE);
CREATE TABLE IF NOT EXISTS apk_tags (apk char(255), tag INTEGER);
CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY, info char(255) UNIQUE)
CREATE TABLE IF NOT EXISTS apk_permissions(apk char(255), permission INTEGER)
CREATE TABLE IF NOT EXISTS failing_servers(id INTEGER PRIMARY KEY)