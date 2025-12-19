"""
Hephaestus Connection Module
Manages socket connection with Blender addon
"""

import socket
import json
import time
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BlenderConnection:
    """Manages connection to Blender via socket"""

    def __init__(self, host: str = "localhost", port: int = 9876, timeout: int = 60):
        """
        Initialize Blender connection

        Args:
            host: Blender socket host
            port: Blender socket port
            timeout: Socket timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self.connected = False

    def connect(self, retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        Connect to Blender addon socket

        Args:
            retries: Number of connection attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if connected successfully
        """
        for attempt in range(retries):
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                self.socket.connect((self.host, self.port))
                self.connected = True
                logger.info(f"Connected to Blender at {self.host}:{self.port}")
                return True
            except (ConnectionRefusedError, socket.timeout, OSError) as e:
                logger.warning(f"Connection attempt {attempt + 1}/{retries} failed: {e}")
                if self.socket:
                    self.socket.close()
                    self.socket = None
                if attempt < retries - 1:
                    time.sleep(retry_delay)

        self.connected = False
        logger.error(f"Failed to connect to Blender after {retries} attempts")
        return False

    def disconnect(self):
        """Disconnect from Blender"""
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logger.warning(f"Error closing socket: {e}")
            finally:
                self.socket = None
                self.connected = False
                logger.info("Disconnected from Blender")

    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send command to Blender and receive response

        Args:
            command_type: Type of command (e.g., "get_scene_info")
            params: Command parameters

        Returns:
            Response dict with keys: status, result, message

        Raises:
            ConnectionError: If not connected or connection fails
            TimeoutError: If command times out
        """
        if not self.connected or not self.socket:
            if not self.connect():
                raise ConnectionError("Not connected to Blender. Make sure the Hephaestus addon is running.")

        # Prepare command
        command = {
            "type": command_type,
            "params": params or {}
        }

        try:
            # Send command as JSON
            message = json.dumps(command) + "\n"
            self.socket.sendall(message.encode('utf-8'))

            # Receive response
            response_data = b""
            while True:
                chunk = self.socket.recv(4096)
                if not chunk:
                    raise ConnectionError("Connection closed by Blender")
                response_data += chunk
                if b"\n" in response_data:
                    break

            # Parse JSON response
            response_str = response_data.decode('utf-8').strip()
            response = json.loads(response_str)

            # Validate response format
            if "status" not in response:
                raise ValueError("Invalid response format from Blender")

            if response["status"] == "error":
                logger.error(f"Blender error: {response.get('message', 'Unknown error')}")

            return response

        except socket.timeout:
            logger.error("Command timed out")
            self.disconnect()
            raise TimeoutError(f"Command '{command_type}' timed out after {self.timeout} seconds")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {e}")
            raise ValueError(f"Invalid JSON response from Blender: {e}")

        except Exception as e:
            logger.error(f"Command failed: {e}")
            self.disconnect()
            raise

    def execute_code(self, code: str) -> Dict[str, Any]:
        """
        Execute arbitrary Python code in Blender

        Args:
            code: Python code to execute

        Returns:
            Response dict
        """
        return self.send_command("execute_code", {"code": code})

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
        return False


# Global connection instance
_connection: Optional[BlenderConnection] = None


def get_connection() -> BlenderConnection:
    """Get or create global Blender connection"""
    global _connection
    if _connection is None:
        _connection = BlenderConnection()
    return _connection


def ensure_connected() -> BlenderConnection:
    """Ensure connection is active, reconnect if needed"""
    conn = get_connection()
    if not conn.connected:
        conn.connect()
    return conn
