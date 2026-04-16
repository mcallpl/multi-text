"""Database connection via SSH tunnel to remote MySQL."""

import subprocess
import socket
import time
import atexit

import mysql.connector
import config

_tunnel_proc = None
_tunnel_port = None
_connection = None


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_tunnel_port():
    """Start an SSH tunnel subprocess and return the local port."""
    global _tunnel_proc, _tunnel_port

    if _tunnel_proc and _tunnel_proc.poll() is None:
        return _tunnel_port

    _tunnel_port = _find_free_port()
    _tunnel_proc = subprocess.Popen(
        [
            "ssh", "-N", "-L",
            f"{_tunnel_port}:127.0.0.1:3306",
            f"{config.SSH_USER}@{config.SSH_HOST}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ExitOnForwardFailure=yes",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for tunnel to be ready
    for _ in range(30):
        try:
            s = socket.create_connection(("127.0.0.1", _tunnel_port), timeout=1)
            s.close()
            return _tunnel_port
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)

    raise RuntimeError("SSH tunnel failed to start")


def get_connection():
    """Return a live MySQL connection through the SSH tunnel."""
    global _connection
    port = get_tunnel_port()
    if _connection is None or not _connection.is_connected():
        _connection = mysql.connector.connect(
            host="127.0.0.1",
            port=port,
            user=config.DB_USER,
            password=config.DB_PASS,
            database=config.DB_NAME,
            connection_timeout=10,
        )
    return _connection


def _reconnect():
    """Force a fresh connection (tunnel may have died)."""
    global _connection, _tunnel_proc
    if _connection:
        try:
            _connection.close()
        except Exception:
            pass
        _connection = None
    if _tunnel_proc:
        try:
            _tunnel_proc.terminate()
            _tunnel_proc.wait(timeout=3)
        except Exception:
            pass
        _tunnel_proc = None
    return get_connection()


def query(sql, params=None, fetchall=True):
    """Run a SELECT and return rows as list of dicts. Auto-retries once on failure."""
    for attempt in range(2):
        try:
            conn = get_connection() if attempt == 0 else _reconnect()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, params or ())
            rows = cursor.fetchall() if fetchall else [cursor.fetchone()]
            cursor.close()
            return rows
        except Exception:
            if attempt == 1:
                raise


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE and return lastrowid. Auto-retries once on failure."""
    for attempt in range(2):
        try:
            conn = get_connection() if attempt == 0 else _reconnect()
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            conn.commit()
            last_id = cursor.lastrowid
            cursor.close()
            return last_id
        except Exception:
            if attempt == 1:
                raise


def shutdown():
    """Close DB connection and SSH tunnel."""
    global _connection, _tunnel_proc
    if _connection and _connection.is_connected():
        _connection.close()
        _connection = None
    if _tunnel_proc and _tunnel_proc.poll() is None:
        _tunnel_proc.terminate()
        _tunnel_proc.wait(timeout=5)
        _tunnel_proc = None


atexit.register(shutdown)
