#!/usr/bin/env python3

import asyncio

async def run_cat():
    import subprocess
    import shlex

    command = 'nc --send-only -4 -l -p 8888'
    filepath = 'commit.tar'

    with open(filepath, 'rb') as fh:
        print('reading data...')
        data = fh.read()
        print('opening filesocket...')
        proc = subprocess.Popen(shlex.split(command),
                                stdin=subprocess.PIPE)
        try:
            proc.communicate(input=data, timeout=60)
            print('transmitting...')
        except subprocess.TimeoutExpired:
            proc.kill()
        finally:
            print('closing socket...')
            proc.terminate()
            print('exiting process.')

async def main():
    await asyncio.gather(run_cat())

if __name__ == '__main__':
    asyncio.run(main())

