from androguard.misc import APK
from androguard.core.bytecodes.axml import ResParserError
from DatasetMgr.DBDatasetUpdater import DBDatasetUpdater

import argparse
import os
import zipfile
import shutil
import base64

def main():

    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--dest-folder', '-df', help = 'Download destination folder', required=True)
    argparser.add_argument('--database-file', '-dbf', help = 'Database file', required=True)

    args = argparser.parse_args()

    count = 0
    for apkfile in os.listdir(args.dest_folder):
        # Extract icon filename
        apk_path = os.path.join(args.dest_folder, apkfile)
        apk = APK(apk_path)

        icon_path = None
        try:
            icon_path = apk.get_app_icon()
        except ResParserError as e:
            pass

        if icon_path:
            # Extract icon to byte array
            zipi = zipfile.ZipFile(apk_path)

            try:
                zipi.extract(icon_path)

                icon_file = open(icon_path, 'rb')
                data = icon_file.read()
                icon_file.close()

                # Encode into b64 str
                b64 = base64.b64encode(data)

                # Save into DB
                dbu = DBDatasetUpdater()
                dbu.connect_db(args.database_file)

                sha256 = dbu.sha256(apk_path)

                query = {'sha256' : sha256, 'b64' : b64}
                #print(query)
                dbu.dbclient.execute("UPDATE apks SET icon = :b64 where sha256 = :sha256", query)
                dbu.dbclient.commit()
                dbu.disconnect_db()

                # Remove extracted file
                shutil.rmtree(icon_path.split(os.path.sep)[0])

                count = count + 1
                print("%i/%i APK icons extracted" % (count, len(os.listdir(args.dest_folder))), end='\r')

            except KeyError:
                pass

            

if __name__ == "__main__":
    main()