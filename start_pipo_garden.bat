@echo off
title PiPo Garden - Khoi Dong He Thong
chcp 65001 > nul
echo ========================================================
echo     HE THONG QUAN LY NHA HANG PIPO GARDEN
echo   Goi Mon Qua Ma QR & Tu Dong In Phieu Bep (KOT)
echo ========================================================
echo.
echo [*] Dang khoi dong Server Backend & WebSockets...
start "PiPo Garden - Server" cmd /k "python run_server.py"

echo [*] Dang khoi dong Local Print Agent (In bep tu dong)...
start "PiPo Garden - Print Agent" cmd /k "python run_agent.py"

echo [*] Cho he thong san sang trong 2 giay...
timeout /t 2 /nobreak > nul

echo [*] Dang mo Trang chu PiPo Garden tren trinh duyet...
start http://localhost:8000/

echo.
echo ========================================================
echo  KHOI DONG THANH CONG!
echo  - Trang Chu & Dang Nhap  : http://localhost:8000/
echo  - Thu Ngan & Quan Tri POS: http://localhost:8000/pos
echo  - Khong Gian Bep (KDS+BOM): http://localhost:8000/kitchen
echo  - Nhan Vien Phuc Vu      : http://localhost:8000/waiter
echo  - Quan Ly Kho & Nhap NVL : http://localhost:8000/inventory
echo  - May In Bep Ao (Thermal): http://localhost:8000/printer-monitor
echo ========================================================
