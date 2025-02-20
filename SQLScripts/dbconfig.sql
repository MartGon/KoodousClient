CREATE TABLE IF NOT EXISTS apks (package_name char(255), sha256 char(255) PRIMARY KEY, filename char(255) UNIQUE, malware BOOL DEFAULT 1, downloaded BOOL DEFAULT 0, download_failed BOOL DEFAULT 0, download_url TEXT DEFAULT "NONE" );
CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY , info char(255) UNIQUE);
CREATE TABLE IF NOT EXISTS apk_tags (apk char(255), tag INTEGER, UNIQUE(apk, tag));

CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY, info char(255) UNIQUE);
CREATE TABLE IF NOT EXISTS apk_permissions(apk char(255), permission INTEGER, UNIQUE(apk, permission));

CREATE TABLE IF NOT EXISTS functionalities (id INTEGER PRIMARY KEY, info varchar UNIQUE);
CREATE TABLE IF NOT EXISTS apk_functionalities(apk char(255), functionality INTEGER, UNIQUE(apk, functionality));

CREATE TABLE IF NOT EXISTS commands(id INTEGER PRIMARY KEY, info varchar UNIQUE);
CREATE TABLE IF NOT EXISTS apk_commands(apk char(255), command INTEGER, UNIQUE(apk, command));

CREATE TABLE IF NOT EXISTS libraries(id INTEGER PRIMARY KEY, info varchar UNIQUE);
CREATE TABLE IF NOT EXISTS apk_libraries(apk char(255), library INTEGER, UNIQUE(apk, library));

CREATE TABLE IF NOT EXISTS misc_features(id INTEGER PRIMARY KEY, info varchar UNIQUE);
CREATE TABLE IF NOT EXISTS apk_misc_features(apk char(255), misc_feature INTEGER, UNIQUE(apk, misc_feature));
CREATE TABLE IF NOT EXISTS apk_misc_continuous_features (apk char(255) PRIMARY KEY, cert_entropy FLOAT NOT NULL DEFAULT 0.0 , pkg_entropy FLOAT NOT NULL DEFAULT 0.0, cert_name_length INTEGER NOT NULL DEFAULT 0, pkg_name_length INTEGER NOT NULL DEFAULT 0, files INTEGER NOT NULL DEFAULT 0, activities INTEGER NOT NULL DEFAULT 0, services INTEGER NOT NULL DEFAULT 0, providers INTEGER NOT NULL DEFAULT 0, receivers INTEGER NOT NULL DEFAULT 0, permissions INTEGER NOT NULL DEFAULT 0, declared_permissions INTEGER NOT NULL DEFAULT 0, third_party_permissions INTEGER NOT NULL DEFAULT 0, sdk_version INTEGER NOT NULL DEFAULT 0, main_activity_name_length INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS static_features(id INTEGER PRIMARY KEY, kind INTEGER, info varchar UNIQUE);
CREATE TABLE IF NOT EXISTS apk_static_features(apk char(255), static_feature INTEGER, count INTEGER, UNIQUE(apk, static_feature));

CREATE TABLE IF NOT EXISTS failing_servers(id INTEGER PRIMARY KEY);