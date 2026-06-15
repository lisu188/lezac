param(
    [string]$BuildDir = "build-win-codex-vs3",
    [string]$Configuration = "Debug",
    [string]$VcpkgRoot = "C:\vcpkg",
    [string]$VsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat",
    [string]$PkgConfigExe = "",
    [string]$Generator = "Visual Studio 17 2022",
    [string]$Platform = "x64",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

function Require-Path($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "missing $Label`: $Path"
    }
}

function Set-SinglePathVariable {
    $vars = [System.Environment]::GetEnvironmentVariables("Process")
    $pathValue = $vars["Path"]
    if ([string]::IsNullOrEmpty($pathValue)) {
        $pathValue = $vars["PATH"]
    }
    [System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
    [System.Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
}

function Invoke-DevCmd($Command) {
    $escapedVsDevCmd = $VsDevCmd.Replace('"', '\"')
    $fullCommand = "call `"$escapedVsDevCmd`" -arch=$Platform >nul && $Command"
    & cmd /s /c $fullCommand
    if ($LASTEXITCODE -ne 0) {
        throw "command failed ($LASTEXITCODE): $Command"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sdlPackage = Join-Path $VcpkgRoot "packages\sdl2_x64-windows"
$sdlPkgConfigDir = Join-Path $sdlPackage "lib\pkgconfig"
$sdlBinDir = Join-Path $sdlPackage "bin"
$pkgConfigToolDir = Join-Path $VcpkgRoot "downloads\tools\msys2\3e71d1f8e22ab23f\mingw64\bin"
if ([string]::IsNullOrEmpty($PkgConfigExe)) {
    $PkgConfigExe = Join-Path $pkgConfigToolDir "pkg-config.exe"
}

Require-Path $VsDevCmd "Visual Studio developer command"
Require-Path (Join-Path $sdlPackage "include\SDL2\SDL.h") "vcpkg SDL2 header"
Require-Path (Join-Path $sdlPackage "lib\SDL2.lib") "vcpkg SDL2 library"
Require-Path (Join-Path $sdlBinDir "SDL2.dll") "vcpkg SDL2 runtime"
Require-Path (Join-Path $sdlPkgConfigDir "sdl2.pc") "vcpkg SDL2 pkg-config file"
Require-Path $PkgConfigExe "pkg-config executable"

Set-SinglePathVariable
$env:PKG_CONFIG_PATH = $sdlPkgConfigDir
$env:Path = "$sdlBinDir;$pkgConfigToolDir;$env:Path"

$buildPath = Join-Path $repoRoot $BuildDir
$pkgConfigCmake = $PkgConfigExe.Replace("\", "/")
$vsInstance = (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $VsDevCmd))).Replace("\", "/")

Push-Location $repoRoot
try {
    $configure = "cmake -S . -B `"$buildPath`" -G `"$Generator`" -A $Platform -T host=$Platform -DPKG_CONFIG_EXECUTABLE=`"$pkgConfigCmake`" -DCMAKE_GENERATOR_INSTANCE=`"$vsInstance`""
    Invoke-DevCmd $configure

    $build = "cmake --build `"$buildPath`" --config $Configuration --target lezac_cpp -j 2"
    Invoke-DevCmd $build
    $buildOutputDir = Join-Path $buildPath $Configuration
    Require-Path (Join-Path $buildOutputDir "lezac_cpp.exe") "built executable"
    Require-Path (Join-Path $buildOutputDir "SDL2.dll") "built SDL2 runtime copy"

    if (-not $SkipTests) {
        $env:Path = "$sdlBinDir;$env:Path"
        & ctest --test-dir $buildPath -C $Configuration --output-on-failure
        if ($LASTEXITCODE -ne 0) {
            throw "ctest failed ($LASTEXITCODE)"
        }
    }

    Write-Output "native_windows_validation=ok build_dir=$BuildDir configuration=$Configuration sdl2_runtime=1 tests=$([int](-not $SkipTests))"
} finally {
    Pop-Location
}
