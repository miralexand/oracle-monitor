@echo off
setlocal
cd /d "%~dp0"

echo [1/4] 准备虚拟环境...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || goto :error
)

echo [2/4] 安装依赖...
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller || goto :error

echo [3/4] 打包 EXE...
".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm oracle_monitor.spec || goto :error

echo [4/4] 完成！分发目录: dist\
echo   将 dist\oracle_monitor.exe 单独拷贝给用户即可。
echo   首次运行会在 exe 同目录生成 config.ini，编辑后再次运行。
goto :eof

:error
echo.
echo 构建失败，请检查上方错误信息。
exit /b 1
