"""
PiPo Garden - Print Agent Launcher
Khởi chạy dịch vụ lắng nghe và in phiếu bếp tự động.
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    agent_path = os.path.join(os.path.dirname(__file__), "print_agent", "agent.py")
    sys.exit(subprocess.call([sys.executable, agent_path]))
