#!/usr/bin/env python3

import asyncio
import logging
import datetime
import math
import random
import shutil
import socket
import aiohttp
import aioping
import eternalegypt

logger = logging.getLogger(__name__)

class UplinkMonitor:
    def __init__(self, config):
        self.config = config
        self.failed = False
        self.tasks = set()
        # aioping.ping() has no interface parameter so we
        # monkey patch its helper send_one_ping() to always
        # ping via our primary_interface
        real_send_one_ping = aioping.send_one_ping
        async def primary_send_one_ping(my_socket, dest_addr, id_, timeout, family):
            my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self.config['interfaces']['primary'].encode())
            return await real_send_one_ping(my_socket, dest_addr, id_, timeout, family)
        aioping.send_one_ping = primary_send_one_ping

    async def run(self, cmd, *args):
        fullcmd = shutil.which(cmd)
        logger.debug(f"Running command: '{fullcmd}'")

        proc = await asyncio.create_subprocess_exec(
            fullcmd, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()
        stdout, stderr = (stdout.decode(), stderr.decode())
        rc = proc.returncode
        logger.debug(f"Result: rc={rc} stdout='{stdout}' stderr='{stderr}'")
        return (proc.returncode, stdout, stderr)

    def background_task(self, code):
        task = asyncio.create_task(code)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def sms(self, message):
        if sms := self.config.get('sms'):
            try:
                logger.info(f"Sending text message via {sms['modem']}")
                jar = aiohttp.CookieJar(unsafe=True)
                websession = aiohttp.ClientSession(cookie_jar=jar)

                modem = eternalegypt.Modem(hostname=sms['modem'], websession=websession)
                await modem.login(password=sms['password'])

                for target in sms['recipients']:
                    await modem.sms(phone=target, message=message)

                await modem.logout()
                await websession.close()
            except eternalegypt.eternalegypt.Error as ex:
                logger.warning(f"Sending failed: {ex}")


    async def failover(self):
        logger.warning("Failover")
        await self.run('ip', 'route', 'add', 'default', 'dev', self.config['interfaces']['secondary'].encode(), 'metric', '1')
        await self.run('conntrack', '-F')
        self.failed = True

    async def failback(self):
        logger.warning("Failback")
        await self.run('ip', 'route', 'del', 'default', 'dev', self.config['interfaces']['secondary'].encode(), 'metric', '1')
        self.failed = False

    async def ping(self, ips):
        # Ping first for 0.5s
        logger.debug(f"Pinging first host: {ips[0]}")
        tasks = { asyncio.create_task(aioping.ping(ips[0])): ips[0] }
        (done, pending) = await asyncio.wait(tasks.keys(), timeout=0.5)

        if len(done) == 0:
            slow_logger = logger.debug if self.failed else logger.info
            slow_logger(f"Slow reply from {ips[0]}, also trying {ips[1:]}")

            # Ping all for another 0.5s
            for ip in ips[1:]:
                tasks[asyncio.create_task(aioping.ping(ip))] = ip
            (done, pending) = await asyncio.wait(tasks.keys(), timeout=0.5, return_when=asyncio.FIRST_COMPLETED)

        ok = False
        for d in done:
            try:
                delay = d.result()
                logger.debug(f"Received a ping reply from {tasks[d]}, rtt={delay:.3f}")
                ok = True
            except Exception as exc:
                pass

        if pending:
            logger.debug(f"Cancelling {[tasks[p] for p in pending]}")

            for p in pending:
                if p.cancel():
                    try:
                        await p
                    except asyncio.CancelledError:
                        logger.debug(f"{tasks[p]} got asyncio.CancelledError")
                        pass
                    except Exception as exc:
                        logger.debug(f"{tasks[p]} got exception {exc}")
                        pass
                else:
                    logger.debug(f"Cancelling of {[tasks[p]]} failed")

        logger.debug(f"Ping success = {ok}")
        return ok

    async def alive(self):
        ips = self.config['monitor']['targets'].copy()
        random.shuffle(ips)
        return await self.ping(ips)

    async def failing(self):
        ok = 0
        while ok < self.config['monitor']['recover']:
            if await self.alive():
                ok = ok + 1
                logger.info(f"Recovered {ok}")
                await asyncio.sleep(1)
            else:
                ok = 0

    async def loop(self):
        logger.info("Starting uplink monitoring")
        fail = 0
        while True:
            if await self.alive():
                if fail > 0:
                    logger.info("No longer failing")
                    fail = 0
                await asyncio.sleep(1)
            else:
                fail = fail + 1
                logger.info(f"Fail {fail}")
                if fail == self.config['monitor']['fail']:
                    await self.failover()
                    fail_time = datetime.datetime.now()
                    self.background_task(self.sms("Failed over"))
                    await self.failing()
                    await self.failback()
                    fail_duration = (datetime.datetime.now() - fail_time).total_seconds()
                    (min, sec) = divmod(math.ceil(fail_duration), 60)
                    (hour, min) = divmod(min, 60)
                    if hour > 0:
                        duration = f"{hour}h{min:02}m{sec:02}s"
                    elif min > 0:
                        duration = f"{min}m{sec:02}s"
                    else:
                        duration = f"{sec}s"

                    self.background_task(self.sms(f"Failed back after {duration}"))
                    fail = 0
