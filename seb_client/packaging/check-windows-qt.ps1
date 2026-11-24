# Run in 64-bit PowerShell. No Python or SEB startup needed.
param([string] $BundlePath = '.')

$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitProcess) {
    throw 'Use 64-bit PowerShell to check the SEB x64 bundle.'
}

$root = (Resolve-Path -LiteralPath $BundlePath).ProviderPath
if (-not (Test-Path -LiteralPath (Join-Path $root 'SEB-Client.exe') -PathType Leaf)) {
    throw 'BundlePath must point to the directory containing SEB-Client.exe.'
}
$internal = Join-Path $root '_internal'
$qt = Join-Path $internal 'PySide6'
$shiboken = Join-Path $internal 'shiboken6'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SebDllProbe {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    public static extern IntPtr AddDllDirectory(string path);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool RemoveDllDirectory(IntPtr cookie);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    public static extern IntPtr LoadLibraryExW(string path, IntPtr reserved, uint flags);
    [DllImport("kernel32.dll")]
    public static extern bool FreeLibrary(IntPtr module);
}
'@

$cookies = @()
$modules = @()
$failed = $false
try {
    foreach ($dir in @($internal, $qt, $shiboken)) {
        if (Test-Path -LiteralPath $dir -PathType Container) {
            $cookie = [SebDllProbe]::AddDllDirectory($dir)
            $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            if ($cookie -eq [IntPtr]::Zero) { throw "AddDllDirectory failed: Win32 $code" }
            $cookies += $cookie
        }
    }
    "Windows: $([Environment]::OSVersion.Version); architecture: $env:PROCESSOR_ARCHITECTURE"
    $files = @(
        (Join-Path ([Environment]::SystemDirectory) 'icuuc.dll'),
        (Join-Path $internal 'python3.dll'),
        (Join-Path $shiboken 'shiboken6.abi3.dll'),
        (Join-Path $qt 'Qt6Core.dll'),
        (Join-Path $qt 'pyside6.abi3.dll'),
        (Join-Path $qt 'QtCore.pyd')
    )
    foreach ($file in $files) {
        $name = Split-Path -Leaf $file
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            "MISSING: $name"
            $failed = $true
            continue
        }
        # Search the loaded DLL's directory, registered bundle directories
        # and Windows System32. Do not search the working directory or PATH.
        $module = [SebDllProbe]::LoadLibraryExW($file, [IntPtr]::Zero, 0xD00)
        $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if ($module -eq [IntPtr]::Zero) {
            "FAILED: $name (Win32 $code)"
            $failed = $true
        } else {
            "OK: $name"
            $modules += $module
        }
    }
} finally {
    for ($i = $modules.Count - 1; $i -ge 0; $i--) {
        [void][SebDllProbe]::FreeLibrary($modules[$i])
    }
    foreach ($cookie in $cookies) { [void][SebDllProbe]::RemoveDllDirectory($cookie) }
}
if ($failed) { exit 1 }
