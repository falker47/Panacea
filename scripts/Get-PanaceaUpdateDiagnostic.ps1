# Windows PowerShell 5.1+; prints JSON. Does not start or change Panacea.
[CmdletBinding()]
param([string]$ExecutablePath, [switch]$Offline)
$ErrorActionPreference = 'Stop'
if (-not $ExecutablePath) {
    Add-Type -AssemblyName System.Windows.Forms
    $picker = New-Object System.Windows.Forms.OpenFileDialog
    try {
        $picker.Title = 'Select the Panacea.exe used when the error occurred'
        $picker.Filter = 'Panacea.exe|Panacea.exe'
        if ($picker.ShowDialog() -ne 'OK') { return }
        $ExecutablePath = $picker.FileName
    } finally { $picker.Dispose() }
}
$file = Get-Item -LiteralPath $ExecutablePath
if ($file -isnot [IO.FileInfo] -or $file.Name -ine 'Panacea.exe') { throw 'Select the installed Panacea.exe.' }
$known = @{
    '67319fdeca35ba0e8e7cd36031c7098d42f3d535a8598935bd865c03fe77aab9' = '1.47'
    '3e483228dbef5fd1298777382a848aa5eb92a883c64c93873cfe03d64c79c0ed' = '2.0.0'
    'abb1b95410c29147686dc4be4acfe3dd5586f74e64cf08de0f1d9bdf5d1f7119' = '2.0.1'
    'e390d2f26f84e108c0e076d834f61927554a77175fe19c22108667f04ec1161f' = '2.0.2'
    '684121592593afd16042fceab7b6027bf81718aab276fc024ae6d6bf5baf056c' = '2.1.0'
}
$sha = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$displayPath = $file.FullName
if ($env:USERPROFILE -and $displayPath.StartsWith(($env:USERPROFILE + '\'), [StringComparison]::OrdinalIgnoreCase)) {
    $displayPath = '%USERPROFILE%' + $displayPath.Substring($env:USERPROFILE.Length)
}
$api = 'https://api.github.com/repos/falker47/Panacea/releases/latest'
$result = [ordered]@{
    observedUtc = [DateTime]::UtcNow.ToString('o'); path = $displayPath; bytes = $file.Length
    sha256 = $sha; matchesPublishedVersion = $known[$sha]; fileVersion = $file.VersionInfo.FileVersion
    api = $api; manifestStatus = 'not requested'
}
if (-not $Offline) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $api -Headers @{'User-Agent'='Panacea-Update-Diagnostic'; Accept='application/vnd.github+json'} -TimeoutSec 20 -MaximumRedirection 0
        $manifest = $response.Content | ConvertFrom-Json
        $tag = [string]$manifest.tag_name
        if ($tag -cnotmatch '^v?[0-9]+(\.[0-9]+){1,3}$') { throw 'Unexpected tag' }
        $result.tag = $tag
        $expected = "https://github.com/falker47/Panacea/releases/tag/$tag"
        $result.pageMatchesExpected = [string]$manifest.html_url -cmatch ('^(?i:https://github\.com/falker47/Panacea)/releases/tag/' + [regex]::Escape($tag) + '$')
        # Never emit arbitrary URLs (queries, userinfo or paths can carry credentials).
        $result.releasePage = if ($result.pageMatchesExpected) { $expected } else { '[unexpected or missing]' }
        $result.requiredAssets = @(
            foreach ($name in 'Panacea.exe','Panacea.exe.sha256') {
                $found = @($manifest.assets | Where-Object { $_.name -ceq $name })
                $pattern = '^(?i:https://github\.com/falker47/Panacea)/releases/download/' + [regex]::Escape("$tag/$name") + '$'
                [ordered]@{ name=$name; count=$found.Count; exactReleaseUrl=($found.Count -eq 1 -and $found[0].browser_download_url -cmatch $pattern) }
            }
        )
        $result.manifestStatus = 'read'
    } catch {
        $result.manifestStatus = 'request or parse failed'
        $result.errorType = $_.Exception.GetType().Name
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $result.httpStatus = [int]$_.Exception.Response.StatusCode }
    }
}
$result | ConvertTo-Json -Depth 4
