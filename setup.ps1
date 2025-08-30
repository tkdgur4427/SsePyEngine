# Debug Tag
[string]$PrefixTag = '**********[sse]'

# download and install choco as package manager
Function SetupChoco {
    # prepare to install chocolatey
    [string]$PolicyType = Get-ExecutionPolicy
    if ($PolicyType -match 'Restricted') {
        Set-ExecutionPolicy Unrestricted
        $PolicyType = Get-ExecutionPolicy
    }
    [string]::Format("{0} Current ExecutionPolicy is {1}", $PrefixTag, $PolicyType)

    # install chocolatey
    if (!(test-path "C:\ProgramData\chocolatey\choco.exe")) {
        # clear env variables
        $env:ChocolateyInstall = $null
        $env:ChocolateyToolsLocation = $null
        $env:ChocolateyLastPathUpdate = $null

        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    }

    [string]$ChocoVersion = choco --v
    [string]::Format("{0} Choco version: {1}", $PrefixTag, $ChocoVersion)
}

# test whether program is installed
Function IsProgramInstalled {
    param (
        [string]$Program
    )
    
    $32BitPrograms = Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*
    $64BitPrograms = Get-ItemProperty HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*
    $ProgramsWithProgramInName = ($32BitPrograms + $64BitPrograms) | Where-Object { $null -ne $_.DisplayName -and $_.Displayname.Contains($Program) }
    $IsInstalled = $null -ne $ProgramsWithProgramInName
    return $IsInstalled
}

# update session environment for choco
Function UpdateSessionEnvForChoco {
    # refer to [https://stackoverflow.com/questions/46758437/how-to-refresh-the-environment-of-a-powershell-session-after-a-chocolatey-instal]

    # make 'refreshenv' available right away, be defining the $env.ChocolateyInstall variable
    # and importing the Chocolatey profile module
    # NOTE: using `.$PROFILE` instead *may* work, but isn't guaranteed to.
    $env:ChocolateyInstall = Convert-Path "$((Get-Command choco).Path)\..\.."
    Import-Module "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1" | Out-Null

    # refereshenv is now an alias for Update-SessionEnvironment
    # (rather than invoking refreshenv.cmd, the *batch file* for use with cmd.exe)
    # this should make git.exe accessible via the refreshed $env:PATH, so that it can be called by name only
    refreshenv | Out-Null

    # NOTE: '... | Out-Null' hides powershell output
}

# add new environment path string to env:Path at the fro
Function AddEnvPathVariable {
    # refer to set permanent change in env:Path
    # https://codingbee.net/powershell/powershell-make-a-permanent-change-to-the-path-environment-variable
    param (
        [string]$NewEnvPath
    )

    if (Test-Path $NewEnvPath) {
        # get the old path
        $OldPathArr = (Get-ItemProperty -Path 'Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment' -Name PATH).path
        
        # filter the NewEnvPath
        $RegexNewEnvPath = [regex]::Escape($NewEnvPath)
        $OldPathArr = $OldPathArr -split ';' | Where-Object { $_ -notmatch "^$RegexNewEnvPath\\?" }
        $OldPathArr = $OldPathArr -join ';'
        $NewPathArr = "$NewEnvPath;$OldPathArr"

        # debugging
        Write-Output $NewPathArr

        # apply global env variables permanently
        Set-ItemProperty -Path 'Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment' -Name PATH -Value $NewPathArr
    }
    else {
        [string]::Format("{0} {1} is not exists, plz check!", $PrefixTag, $NewEnvPath)
    }
}

Function InstallPythonPackages {
    # only install python package
    $PythonFolder = 'C:\Program Files\Python313'
    if (!(Test-Path -Path $PythonFolder)) {
        choco install python313 `
            --params '"/InstallDir:C:\Program Files\Python313"' `
            --install-arguments "'InstallAllUsers=1 Include_launcher=1 InstallLauncherAllUsers=1 PrependPath=1 Include_pip=1 Include_lib=1 /log=C:\python313_install.log'" -y --force
    }
    [string]::Format("{0} Installed Python Path: {1}", $PrefixTag, $PythonFolder)

    # set the default python version as 38-64
    [string]$PythonPath = 'C:\Program Files\Python313\'
    [string]$PythonScriptPath = [string]::Format("{0}Scripts\", $PythonPath)
    AddEnvPathVariable($PythonPath)
    AddEnvPathVariable($PythonScriptPath)

    # update session to update env.path variables
    UpdateSessionEnvForChoco
}

# install vscode
Function InstallVSCode {
    if (!(IsProgramInstalled('Visual Studio Code'))) {
        # install vscode
        choco install vscode -y
    }

    # update session to retrieve code command
    UpdateSessionEnvForChoco

    $CodeVersion = (code --version)[0]
    [string]::Format("{0} VSCode is installed: [{1}]", $PrefixTag, $CodeVersion)
}

# install git environment (including source tree)
Function InstallGitEnv {
    # check whether git is installed
    if (!(IsProgramInstalled('Git'))) {
        # install git for windows
        choco install git.install -y --force
    }

    # update session to retrieve git command
    UpdateSessionEnvForChoco
    
    $GitVersion = git --version
    [string]::Format("{0} Git is installed: [{1}]", $PrefixTag, $GitVersion)

    # set global config (autocrlf = true)
    git config --global core.autocrlf true 
}

Function Setup {
    # install choco package manager:
    SetupChoco

    # install git:
    InstallGitEnv

    # install packages
    InstallPythonPackages

    # install vscode
    InstallVSCode

    # execute powershell scripts
    py -3.13 setup.py
}

# run the setup function
Setup