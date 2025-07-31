import re
import subprocess
import shlex
from typing import List, Optional, Union

# Safe patterns for validation
IP_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
MAC_PATTERN = re.compile(r'^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$')

def validate_ip_address(ip: str) -> bool:
    """Validate IP address format"""
    if not ip or not isinstance(ip, str):
        return False
    return bool(IP_PATTERN.match(ip.strip()))

def validate_mac_address(mac: str) -> bool:
    """Validate MAC address format"""
    if not mac or not isinstance(mac, str):
        return False
    return bool(MAC_PATTERN.match(mac.strip()))

def sanitize_input(value: str, pattern: re.Pattern, max_length: int = 100) -> Optional[str]:
    """Sanitize input against pattern and length"""
    if not value or not isinstance(value, str):
        return None
    
    value = value.strip()[:max_length]
    
    if pattern.match(value):
        return value
    return None

def safe_subprocess_run(cmd: List[str], timeout: int = 10, **kwargs) -> subprocess.CompletedProcess:
    """
    Safely execute subprocess with validation
    
    Args:
        cmd: List of command arguments (no shell=True)
        timeout: Command timeout in seconds
        **kwargs: Additional subprocess.run arguments
    
    Returns:
        CompletedProcess result
        
    Raises:
        ValueError: If command validation fails
        subprocess.TimeoutExpired: If command times out
    """
    if not isinstance(cmd, list) or not cmd:
        raise ValueError("Command must be a non-empty list")
    
    # Validate command executable
    executable = cmd[0]
    allowed_executables = {
        'ping', 'arp', 'ip', 'iptables', 'tc', 'systemctl', 
        'gpio', 'dpkg', 'apt-get', 'modprobe', 'zerotier-cli'
    }
    
    if executable not in allowed_executables:
        raise ValueError(f"Executable '{executable}' not in allowed list")
    
    # Set safe defaults
    safe_kwargs = {
        'capture_output': True,
        'text': True,
        'timeout': timeout,
        'shell': False,  # Never use shell=True
        'check': False,
    }
    safe_kwargs.update(kwargs)
    
    # Remove dangerous options
    safe_kwargs.pop('shell', None)
    
    try:
        return subprocess.run(cmd, **safe_kwargs)
    except subprocess.TimeoutExpired as e:
        raise subprocess.TimeoutExpired(e.cmd, e.timeout, e.output, e.stderr)
    except Exception as e:
        raise RuntimeError(f"Command execution failed: {e}")

def safe_ping_command(ip_address: str) -> Optional[subprocess.CompletedProcess]:
    """Safely execute ping command for TTL detection"""
    if not validate_ip_address(ip_address):
        return None
    
    import platform
    system = platform.system().lower()
    
    if system == "windows":
        cmd = ['ping', '-n', '1', ip_address]
    else:
        cmd = ['ping', '-c', '1', ip_address]
    
    try:
        return safe_subprocess_run(cmd, timeout=5)
    except Exception:
        return None

def safe_arp_command(ip_address: str) -> Optional[subprocess.CompletedProcess]:
    """Safely execute ARP command"""
    if not validate_ip_address(ip_address):
        return None
    
    try:
        cmd = ['arp', '-a', ip_address]
        return safe_subprocess_run(cmd, timeout=2)
    except Exception:
        return None

def safe_iptables_command(rule_parts: List[str]) -> Optional[subprocess.CompletedProcess]:
    """Safely execute iptables command with validated parts"""
    if not isinstance(rule_parts, list) or not rule_parts:
        return None
    
    # Basic validation of iptables arguments
    allowed_args = {
        '-t', '-A', '-D', '-I', '-F', '-L', '-N', '-X', '-P',
        '-s', '-d', '-p', '-m', '-j', '--sport', '--dport',
        '--to-port', '--set-dscp', '--set-mark', 'mangle',
        'ACCEPT', 'DROP', 'REJECT', 'DSCP', 'MARK'
    }
    
    # Validate each argument
    for arg in rule_parts:
        if arg.startswith('-') and arg not in allowed_args:
            return None
    
    cmd = ['iptables'] + rule_parts
    
    try:
        return safe_subprocess_run(cmd, timeout=10)
    except Exception:
        return None