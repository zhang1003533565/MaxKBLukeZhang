param(
    [switch]$StopDepsOnExit,
    [switch]$SkipPyDeps
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LocalDir = Join-Path $RootDir ".local\maxkb"
$UiDir = Join-Path $RootDir "ui"
$VenvDir = Join-Path $RootDir ".venv"
$Processes = @()

function Write-DevLog {
    param([string]$Message)
    Write-Host "[dev-all] $Message"
}

function Set-DefaultEnv {
    param(
        [string]$Name,
        [string]$Value
    )

    $current = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($current)) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    }
}

function Wait-Tcp {
    param(
        [string]$Name,
        [string]$HostName,
        [int]$Port,
        [int]$MaxAttempts = 60
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $connect = $client.BeginConnect($HostName, $Port, $null, $null)
            if ($connect.AsyncWaitHandle.WaitOne(1000, $false)) {
                $client.EndConnect($connect)
                return
            }
        }
        catch {
        }
        finally {
            $client.Close()
        }
        Start-Sleep -Seconds 1
    }

    throw "$Name is not reachable at ${HostName}:${Port}. Run: docker compose -f docker-compose.dev.yml ps"
}

function Start-DevProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )

    Write-DevLog "Starting $Name..."
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -NoNewWindow `
        -PassThru
    $script:Processes += $process
}

function Stop-DevProcesses {
    if ($script:Processes.Count -gt 0) {
        Write-DevLog "Stopping backend, celery, and frontend..."
        foreach ($process in $script:Processes) {
            if ($null -ne $process -and -not $process.HasExited) {
                try {
                    taskkill.exe /PID $process.Id /T /F | Out-Null
                }
                catch {
                    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }
}

try {
    New-Item -ItemType Directory -Force -Path `
        (Join-Path $LocalDir "logs"), `
        (Join-Path $LocalDir "tmp"), `
        (Join-Path $LocalDir "model\base"), `
        (Join-Path $LocalDir "model\embedding"), `
        (Join-Path $LocalDir "sandbox\python-packages") | Out-Null

    Set-DefaultEnv "MAXKB_CONFIG" "ENV"
    Set-DefaultEnv "MAXKB_CONFIG_TYPE" "ENV"
    Set-DefaultEnv "MAXKB_VERSION" "dev-source"
    Set-DefaultEnv "MAXKB_DEFAULT_PASSWORD" "LiuguangKB@123.."
    Set-DefaultEnv "MAXKB_DEBUG" "true"
    Set-DefaultEnv "MAXKB_LOG_LEVEL" "DEBUG"
    Set-DefaultEnv "MAXKB_KNOWLEDGE_ONLY" "true"
    Set-DefaultEnv "MAXKB_LOG_DIR" (Join-Path $LocalDir "logs")
    Set-DefaultEnv "MAXKB_TMP_DIR" (Join-Path $LocalDir "tmp")
    Set-DefaultEnv "MAXKB_BACKEND_PORT" "8082"
    Set-DefaultEnv "VITE_BACKEND_PORT" $env:MAXKB_BACKEND_PORT
    Set-DefaultEnv "HF_HOME" (Join-Path $LocalDir "model\base")
    Set-DefaultEnv "TMPDIR" (Join-Path $LocalDir "tmp")
    Set-DefaultEnv "TMP" (Join-Path $LocalDir "tmp")
    Set-DefaultEnv "TEMP" (Join-Path $LocalDir "tmp")

    Set-DefaultEnv "MAXKB_DB_NAME" "maxkb"
    Set-DefaultEnv "MAXKB_DB_HOST" "127.0.0.1"
    Set-DefaultEnv "MAXKB_DB_PORT" "5432"
    Set-DefaultEnv "MAXKB_DB_USER" "root"
    Set-DefaultEnv "MAXKB_DB_PASSWORD" "Password123@postgres"
    Set-DefaultEnv "MAXKB_DB_MAX_OVERFLOW" "80"

    Set-DefaultEnv "MAXKB_REDIS_HOST" "127.0.0.1"
    Set-DefaultEnv "MAXKB_REDIS_PORT" "6380"
    Set-DefaultEnv "MAXKB_REDIS_PASSWORD" "Password123@redis"
    Set-DefaultEnv "MAXKB_REDIS_DB" "0"
    Set-DefaultEnv "MAXKB_REDIS_MAX_CONNECTIONS" "100"

    Set-DefaultEnv "MAXKB_EMBEDDING_MODEL_PATH" (Join-Path $LocalDir "model\embedding")
    Set-DefaultEnv "MAXKB_EMBEDDING_MODEL_NAME" (Join-Path $LocalDir "model\embedding\disabled-local-embedding")
    Set-DefaultEnv "MAXKB_SANDBOX_PYTHON_PACKAGE_PATHS" "$($VenvDir)\Lib\site-packages,$(Join-Path $LocalDir "sandbox\python-packages")"
    Set-DefaultEnv "PYTHONUTF8" "1"
    Set-DefaultEnv "PYTHONIOENCODING" "utf-8"

    Set-Location $RootDir

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker Desktop is required. Install and start Docker Desktop, then rerun this script."
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv is required. Install it first: py -m pip install uv"
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "Node.js/npm is required. Install Node.js 22+ or 24+, then rerun this script."
    }

    Write-DevLog "Starting PostgreSQL and Redis..."
    docker compose -f docker-compose.dev.yml up -d --wait

    Wait-Tcp "PostgreSQL" $env:MAXKB_DB_HOST ([int]$env:MAXKB_DB_PORT)
    Wait-Tcp "Redis" $env:MAXKB_REDIS_HOST ([int]$env:MAXKB_REDIS_PORT)

    if (-not $SkipPyDeps) {
        Write-DevLog "Syncing Python dependencies with uv..."
        uv sync --python 3.11
        if ($LASTEXITCODE -ne 0) {
            throw "Python dependency sync failed with code $LASTEXITCODE."
        }
    }

    $UvRunArgs = @("run")
    if ($SkipPyDeps) {
        $UvRunArgs += "--no-sync"
    }

    $UiEnv = Join-Path $UiDir "env\.env"
    $UiEnvExample = Join-Path $UiDir "env\.env.example"
    if (-not (Test-Path $UiEnv)) {
        Copy-Item $UiEnvExample $UiEnv
    }

    if (-not (Test-Path (Join-Path $UiDir "node_modules"))) {
        Write-DevLog "Installing frontend dependencies..."
        Push-Location $UiDir
        npm install
        Pop-Location
    }

    if ($env:MAXKB_DEV_SKIP_PREP -ne "true") {
        Write-DevLog "Preparing backend static files..."
        uv @UvRunArgs python "main.py" "collect_static"
        if ($LASTEXITCODE -ne 0) {
            throw "Backend static preparation failed with code $LASTEXITCODE."
        }

        Write-DevLog "Applying database migrations..."
        uv @UvRunArgs python "main.py" "upgrade_db"
        if ($LASTEXITCODE -ne 0) {
            throw "Database migration failed with code $LASTEXITCODE."
        }
    }

    [Environment]::SetEnvironmentVariable("MAXKB_SKIP_DEV_PREP", "true", "Process")

    Write-DevLog "Starting backend, celery, and frontend..."
    Start-DevProcess "backend" "uv" ($UvRunArgs + @("python", "main.py", "dev", "web")) $RootDir
    Start-DevProcess "celery" "uv" ($UvRunArgs + @("python", "main.py", "dev", "celery")) $RootDir
    Start-DevProcess "frontend" "npm.cmd" @("run", "dev") $UiDir

    Write-DevLog "Ready:"
    Write-DevLog "  Frontend: http://localhost:3000/admin"
    Write-DevLog "  Backend:  http://localhost:$env:MAXKB_BACKEND_PORT"
    Write-DevLog "Press Ctrl+C to stop app processes."
    Write-DevLog "Docker dependencies stay running by default. Use -StopDepsOnExit to stop them on exit."

    while ($true) {
        foreach ($process in $Processes) {
            if ($process.HasExited) {
                throw "A development process exited with code $($process.ExitCode)."
            }
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    Stop-DevProcesses
    if ($StopDepsOnExit) {
        Write-DevLog "Stopping Docker dependencies..."
        Set-Location $RootDir
        docker compose -f docker-compose.dev.yml down
    }
}
