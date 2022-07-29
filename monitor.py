#! /usr/bin/python3
from dvrip import DVRIPCam, SomethingIsWrongWithCamera
from signal import signal, SIGINT, SIGTERM
from sys import argv, stdout, exit
from datetime import datetime
from pathlib import Path
from time import sleep, time
import logging

baseDir = argv[3]
retryIn = 5
rebootWait = 10
camIp = argv[1]
camName = argv[2]
cam = None
isShuttingDown = False
chunkSize = 60 # new file every 1 minute
logFile = baseDir + '/' + camName + '/log.log'

def log(str):
    logging.info(str)

def mkpath():
    path = baseDir + '/' + camName + "/" + datetime.today().strftime('%Y/%m/%d/%H.%M.%S')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path

def shutDown():
    global isShuttingDown
    isShuttingDown = True
    log('Shutting down...')
    try:
        cam.stop_monitor()
        close()
    except (RuntimeError, TypeError, NameError, Exception):
        pass
    log('done')
    exit(0)

def handler(signum, b):
    log('Signal ' + str(signum) + ' received')
    shutDown()

signal(SIGINT, handler)
signal(SIGTERM, handler)

def close():
    cam.close()

def theActualJob():

    prevtime = 0
    video = None
    audio = None

    def receiver(frame, meta, user):
        nonlocal prevtime, video, audio
        if frame is None:
            log('Empty frame')
        else:
            tn = time()
            delta = tn - prevtime

            if delta >= chunkSize:
                # print(f'{delta}\n')
                if video != None:
                    video.close()
                    audio.close()
                prevtime = tn
                path = mkpath()
                log('Starting files: ' + path)
                video = open(path + '.video', "wb")
                audio = open(path + '.audio', "wb")
            if 'type' in meta and meta["type"] == "g711a":
                audio.write(frame)
            elif 'frame' in meta:
                video.write(frame)
            else:
                log(f'Bad frame: {frame}\n')

    log('Starting to grab streams...')
    cam.start_monitor(receiver)

def syncTime():
    log('Synching time...')
    cam.set_time()
    log('done')

def jobWrapper():
    global cam
    log('Logging in to camera ' + camIp + '...')
    cam = DVRIPCam(camIp, user="vlad", password="vlad37650")
    if cam.login():
        log('done')
    else:
        raise SomethingIsWrongWithCamera('Cannot login')
    syncTime()
    theActualJob()

def theJob():
    while True:
        try:
            jobWrapper()
        except (TypeError, ValueError) as err:
            if isShuttingDown:
                exit(0)
            else:
                log(f'{err}\n')
                # try:
                #     log('Error. Attempting to reboot camera...')
                #     cam.reboot()
                #     log('Waiting for ' + str(rebootWait) + 's for reboot...')
                #     sleep(rebootWait)
                # except (UnicodeDecodeError, ValueError, TypeError):
                #     raise SomethingIsWrongWithCamera('Failed to reboot')

def main():
    Path(logFile).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=logFile, level=logging.INFO, format='[%(asctime)s] %(message)s')
    while True:
        try:
            theJob()
        except SomethingIsWrongWithCamera as err:
            close()
            log(str(err) + '. Waiting for ' + str(retryIn) + ' seconds before trying again...')
            sleep(retryIn)

if __name__ == "__main__":
    main()