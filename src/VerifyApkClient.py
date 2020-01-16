import json
import socket
import argparse
import os
import time

def main():
    
    argparser = argparse.ArgumentParser(description='Verify Apk')
    argparser.add_argument('--apk', '-a', help="APK input file", required=False)
    argparser.add_argument('--port', '-p', help="Server port to listen for requests", required=False, default=3000, type=int)

    args = argparser.parse_args()
    apk_path = os.path.abspath(args.apk)

    request = {"path" : apk_path}
    srequest = json.dumps(request)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", args.port))
    print("Connection found")

    client.send(str.encode(srequest))
    sresp = client.recv(4096)
    resp = json.loads(sresp)
    print(resp)

    time.sleep(10)



if __name__ == "__main__":
    main()