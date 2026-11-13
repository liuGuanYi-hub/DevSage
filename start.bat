@echo off
rem DevSage 一键启动：后端 (uvicorn :8000) + 前端 (vite :5173)
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"

set "BACKEND_PY=%ROOT%backend\.venv\Scripts\python.exe"
if not exist "%BACKEND_PY%" (
    echo [错误] 未找到后端虚拟环境: %BACKEND_PY%
    echo 请先创建 backend\.venv 并安装依赖。
    pause
    exit /b 1
)

set "FRONTEND_DIR=%ROOT%frontend"
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [错误] 未找到前端依赖: %FRONTEND_DIR%\node_modules
    echo 请先在 frontend 目录执行 npm install。
    pause
    exit /b 1
)

echo 正在启动后端 http://127.0.0.1:8000 ...
start "DevSage Backend" cmd /k "cd /d "%ROOT%" && "%BACKEND_PY%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000"

echo 正在启动前端 http://127.0.0.1:5173 ...
start "DevSage Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173"

echo 两个窗口已启动，关闭对应窗口即可停止服务。
endlocal
