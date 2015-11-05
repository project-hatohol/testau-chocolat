#!/usr/bin/env python
import argparse
import subprocess
import logging
import sys
import traceback
import time
import signal
import re
import json

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))
logger.setLevel(logging.INFO)


class Manager(object):
    def __init__(self, args):
        self.__args = args
        self.__proc_zabbix_emu = None
        self.__proc_simple_sv = None
        self.__hap2_zabbix_api = None
        self.__subprocs = [
            self.__proc_zabbix_emu,
            self.__proc_simple_sv,
            self.__hap2_zabbix_api,
        ]

        signal.signal(signal.SIGCHLD, self.__child_handler)

    def __del__(self):
        def terminate(proc):
            if proc is None:
                return
            logger.info("Terminate: PID: %s" % proc.pid)
            proc.terminate()

        for proc in self.__subprocs:
            terminate(proc)

    def __child_handler(self, signum, frame):
        logger.error("Got SIGCHLD")
        assert False

    def __call__(self):
        self.__launch_zabbix_emulator()
        self.__launch_simple_server()
        self.__launch_hap2_zabbix_api()

        while True:
            print self.__proc_simple_sv.stdout.readline().rstrip()


    def __launch_zabbix_emulator(self):
        args = "%s" % self.__args.zabbix_emulator_path
        kwargs = {
            "stdout": self.__args.zabbix_emulator_log,
            "stderr": subprocess.STDOUT,
        }
        self.__proc_zabbix_emu = subprocess.Popen(args, **kwargs)
        logger.info("Launched zabbix emulator: PID: %s" % \
                    self.__proc_zabbix_emu.pid)

    def __generate_ms_info_file(self):
        ms_info = {
            "serverId": 1,
            "url": "http://localhost/zabbix/api_jsonrpc.php",
            "type": "8e632c14-d1f7-11e4-8350-d43d7e3146fb",
            "nickName": "HAP test server",
            "userName": "Admin",
            "password": "zabbix",
            "pollingIntervalSec": 30,
            "retryIntervalSec": 10,
            "extendedInfo": "",
        }
        f = self.__args.ms_info_file
        f.write(json.dumps(ms_info))
        f.close()

    def __launch_simple_server(self):
        self.__generate_ms_info_file()
        args = [
            "%s" % self.__args.simple_server_path,
            "--ms-info", self.__args.ms_info_file.name,
        ]
        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
        self.__proc_simple_sv = subprocess.Popen(args, **kwargs)
        logger.info("Launched simple server: PID: %s" % \
                    self.__proc_simple_sv.pid)

        self.__wait_for_ready_of_simple_server()

    def __launch_hap2_zabbix_api(self):
        args = "%s" % self.__args.hap2_zabbix_api_path
        kwargs = {
            "stdout": self.__args.hap2_zabbix_api_log,
            "stderr": subprocess.STDOUT,
        }
        self.__hap2_zabbix_api = subprocess.Popen(args, **kwargs)
        logger.info("Launched hap2_zabbix_api: PID: %s" % \
                    self.__hap2_zabbix_api.pid)

    def __wait_for_ready_of_simple_server(self):
        # I don't know the reason why any two characters after the number (pid)
        # is required.
        re_dispatcher = re.compile("deamonized: \d+..(Dispatcher)")
        re_receiver = re.compile("deamonized: \d+..(Receiver)")
        found_dispatcher_msg = False
        found_receiver_msg = False
        while not found_dispatcher_msg or not found_receiver_msg:
            line = self.__proc_simple_sv.stdout.readline().rstrip()
            msg = self.__extract_message(line)
            if re_dispatcher.match(msg) is not None:
                found_dispatcher_msg = True
                logger.info("Found simple_sever:dispatcher line.")
            elif re_receiver.match(msg) is not None:
                found_receiver_msg = True
                logger.info("Found simple_sever:receiver line.")

    def __extract_message(self, line):
        maxsplit = 2
        severity, component, msg = line.split(":", maxsplit)
        return msg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-z", "--zabbix-emulator-path", type=str,
                        default="zabbix_emulator.py")
    parser.add_argument("-Z", "--zabbix-emulator-log",
                        type=argparse.FileType('w'),
                        default="zabbix-emulator.log")
    parser.add_argument("-a", "--hap2-zabbix-api-path", type=str,
                        default="hap2_zabbix_api.py")
    parser.add_argument("-A", "--hap2-zabbix-api-log",
                        type=argparse.FileType('w'),
                        default="hap2-zabbix-api.log")
    parser.add_argument("-s", "--simple-server-path", type=str,
                        default="simple_server.py")
    parser.add_argument("-m", "--ms-info-file", type=argparse.FileType('w'),
                        help="MonitoringServerInfo file path that is created by this program",
                        default="ms-info.json")
    args = parser.parse_args()

    manager = Manager(args)
    manager()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        logger.error("------- GOT Exception ------")
        logger.error(traceback.format_exc())
