import os
import subprocess
import tempfile


def prepare_py_env(py_version: str, is_x86=False) -> bool:
    # logic to prepare python environment
    if py_version == "313":
        py_version = "3.13"

    python_cmd = f"py -{py_version}"
    return python_cmd


def get_python_x86_path(py_version: str) -> str:
    python_x86_path = os.path.join(
        os.environ["ProgramFiles(x86)"], f"Python{py_version}-32", "python.exe"
    )
    return python_x86_path


def get_python_x64_path(py_version: str) -> str:
    python_x64_path = os.path.join(
        os.environ["PROGRAMW6432"], f"Python{py_version}", "python.exe"
    )
    return python_x64_path


def is_python_installed(py_version: str, is_x86=False) -> bool:
    python_path = None
    if is_x86:
        python_path = get_python_x86_path(py_version)
    else:
        python_path = get_python_x64_path(py_version)
    return os.path.exists(python_path)


"""
powershell script format sets
"""
script_set_environment_var = """
[System.Environment]::SetEnvironmentVariable(${0}, ${1}, [System.EnvironmentVariableTarget]::Machine)
"""
script_run_as_admin = """
# Self-elevate the script if required
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator'))
{
    if ([int](Get-CimInstance -Class Win32_OperatingSystem | Select-Object -ExpandProperty BuildNumber) -ge 6000) 
    {
        $CommandLine = "-File `"" + $MyInvocation.MyCommand.Path + "`" " + $MyInvocation.UnboundArguments
        $proc = Start-Process -FilePath PowerShell.exe -Verb Runas -ArgumentList $CommandLine -PassThru
        while(!($proc.HasExited))
        {
            Start-Sleep -Seconds 2
        }
        Exit
    }
}
"""
script_generate_argument = """
${0} = $args[{1}]
"""
script_debug_argument = """
"VAR_LOG[{0}][${1}]"
"""
script_write_host = """
write-host {0}
"""
script_mklink = """
cmd /c mklink /d "{0}" "{1}"
"""


class PowershellInlineScript:
    # set environment variable struct
    class SetEnvironmentVariable:
        def __init__(self, name_var, value_var):
            self.name_var = name_var
            self.value_var = value_var
            return

        def generate_cmd(self):
            script = script_set_environment_var.format(self.name_var, self.value_var)
            return script

    # make symbolic link
    class MakeLink:
        def __init__(self, dest, src):
            self._dest = dest
            self._src = src
            return

        def generate_cmd(self):
            script = script_mklink.format(self._dest, self._src)
            return script

    # powershell commands
    class PowerShellCommand:
        def __init__(self, command):
            self.cmd = command
            return

        def generate_cmd(self):
            return self.cmd

    def __init__(self):
        self.cmd = ""

        # option
        self.is_debugging_arguments = True
        self.is_file_exec = True

        if self.is_file_exec == True:
            # make temp file path
            self.tempfile_path = tempfile.mktemp(suffix=".ps1")
            # self.tempfile_path = os.path.join(os.getcwd(), 'temp.ps1')

        # powershell script properties
        self.run_as_admin = False
        self.arguments = {}
        self.argument_data = {}
        self.set_environment_variables = []
        self.mklinks = []
        self.commands = []
        return

    def __del__(self):
        os.remove(self.tempfile_path)
        return

    def add_run_as_admin(self):
        self.run_as_admin = True
        return

    def generate_run_as_admin_code(self):
        script = script_run_as_admin
        self.cmd += script
        return

    def add_argument_data(self, argument_index, argument_data):
        self.argument_data[argument_index] = argument_data
        return

    def get_argument_cmd(self):
        args_cmd = []
        for arg_index in self.argument_data:
            args_cmd.append(self.argument_data[arg_index])
        return args_cmd

    def add_argument_code(self, argument_index, argument_name):
        self.arguments[argument_index] = argument_name
        return

    def generate_arguments(self):
        for argument_key in self.arguments:
            # generate argument scripts
            script = script_generate_argument.format(
                self.arguments[argument_key], argument_key
            )
            self.cmd += script
            # debug code
            if self.is_debugging_arguments:
                script = script_debug_argument.format(
                    argument_key, self.arguments[argument_key]
                )
                self.add_log_code(script)
        return

    def add_log_code(self, log):
        powershell_cmd = self.PowerShellCommand(script_write_host.format(log))
        self.commands.append(powershell_cmd)
        return

    def add_command(self, command):
        powershell_cmd = self.PowerShellCommand(command)
        self.commands.append(powershell_cmd)
        return

    def generate_commands(self):
        for command in self.commands:
            self.cmd += command.cmd
        return

    def add_set_environment_variable(self, environment_name_var, environment_value_var):
        set_environment_variable = self.SetEnvironmentVariable(
            environment_name_var, environment_value_var
        )
        self.set_environment_variables.append(set_environment_variable)
        return

    def generate_set_environment_variables(self):
        for set_env_var in self.set_environment_variables:
            script = set_env_var.generate_cmd()
            self.cmd += script
        return

    def add_mklink(self, src_dir, dest_dir):
        new_mklink = self.MakeLink(dest_dir, src_dir)
        self.mklinks.append(new_mklink)
        return

    def generate_mklinks(self):
        for mklink in self.mklinks:
            script = mklink.generate_cmd()
            self.cmd += script
        return

    def generate_cmd(self):
        if self.run_as_admin == True:
            self.generate_run_as_admin_code()

        self.generate_arguments()
        self.generate_set_environment_variables()
        self.generate_mklinks()

        # generate combined cmds from self.commands (stacked-commands)
        self.generate_commands()

        if self.is_file_exec == True:
            with open(self.tempfile_path, "w") as temp_ps1:
                temp_ps1.write(self.cmd)
            return self.tempfile_path

        return self.cmd


def execute_powershell_script(
    inline_powershell_script: PowershellInlineScript, cwd: str = None
):
    script_or_filename = inline_powershell_script.generate_cmd()

    # generate big command line
    command_line = [r"Powershell.exe", "-ExecutionPolicy", "Bypass", script_or_filename]

    args = inline_powershell_script.get_argument_cmd()
    args.insert(0, "'")
    args.append("'")
    command_line.extend(args)

    # call powershell script
    cwd_path = os.getcwd()
    if cwd != None:
        cwd_path = cwd
    script_process = subprocess.Popen(
        command_line,
        cwd=cwd_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # hook log from subprocess
    is_logging = True
    if is_logging:
        with script_process.stdout:

            def log_subprocess_output(pipe):
                for line in iter(pipe.readline, b""):
                    try:
                        str_line = line.decode("cp949")
                    except:
                        continue

            log_subprocess_output(script_process.stdout)

    # This makes the wait possible
    script_process.wait()

    return


def execute_powershell_content(
    content: str, cwd: str = None, run_as_admin: bool = False
):
    script = PowershellInlineScript()
    script.add_command(content)
    if run_as_admin:
        script.add_run_as_admin()

    # execute powershell script
    execute_powershell_script(script, cwd=cwd)

    return


root_dir: str = os.path.abspath(".")


def main():
    # set python version 3.13.X
    py_version = "313"

    # check if python is installed
    if not is_python_installed(py_version):
        raise RuntimeError("Python is not installed. Please install Python 3.13.X")

    # get python command
    py_command = prepare_py_env(py_version)

    # execute pip command
    pip_content = f"""
# install x86 and x64 virtual env
{py_command} -m pip install virtualenv;

# set the cwd
cd "{root_dir}";

# create virtual enviornment
{py_command} -m virtualenv .venv;

# activate .venv
. .venv/Scripts/activate;

# log the state
python --version;

# install packages
pip install -r requirements.txt;
"""
    # execute powershell script:
    execute_powershell_content(pip_content)

    return


# main entry:
main()
