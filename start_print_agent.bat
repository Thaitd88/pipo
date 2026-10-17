@echo off
title PiPo Garden - Tram In Bep Tu Dong (KOT Print Agent)
chcp 65001 > nul
echo ========================================================
echo       PIPO GARDEN - TRAM IN BEP TU DONG (KOT AGENT)
echo   Ket noi: wss://pipogarden.com/ws/printer
echo   May in Bep (T80W): 192.168.31.251:9100
echo   May in Bar/Thu ngan: 192.168.31.252:9100
echo ========================================================
echo.
echo [*] Dang khoi dong Print Agent...
python run_agent.py
pause
