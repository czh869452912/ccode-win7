#define UNICODE
#define _UNICODE

#include <shellapi.h>
#include <windows.h>

#include <sstream>
#include <string>
#include <vector>

static const wchar_t *kPythonRelativePath = L"runtime\\python\\python.exe";
static const wchar_t *kGuiScriptRelativePath = L"app\\embedagent\\frontend\\gui\\launcher.py";
static const wchar_t *kWebView2RelativePath =
    L"runtime\\webview2-fixed-runtime\\msedgewebview2.exe";

static std::wstring JoinPath(const std::wstring &left, const std::wstring &right)
{
    if (left.empty()) {
        return right;
    }
    if (left[left.size() - 1] == L'\\' || left[left.size() - 1] == L'/') {
        return left + right;
    }
    return left + L"\\" + right;
}

static bool FileExists(const std::wstring &path)
{
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

static std::wstring DecimalString(DWORD value)
{
    std::wstringstream stream;
    stream << value;
    return stream.str();
}

static std::wstring LastErrorMessage(DWORD code)
{
    wchar_t *buffer = NULL;
    DWORD flags = FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
                  FORMAT_MESSAGE_IGNORE_INSERTS;
    DWORD length = FormatMessageW(
        flags,
        NULL,
        code,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<LPWSTR>(&buffer),
        0,
        NULL);
    if (length == 0 || buffer == NULL) {
        return L"Windows error " + DecimalString(code);
    }
    std::wstring message(buffer, length);
    LocalFree(buffer);
    while (!message.empty() && (message[message.size() - 1] == L'\r' ||
                                message[message.size() - 1] == L'\n' ||
                                message[message.size() - 1] == L' ')) {
        message.erase(message.size() - 1);
    }
    return message;
}

static int Fail(const std::wstring &message, int exitCode)
{
    MessageBoxW(NULL, message.c_str(), L"EmbedAgent startup error", MB_OK | MB_ICONERROR);
    return exitCode;
}

static std::wstring QuoteArgument(const std::wstring &argument)
{
    if (argument.empty()) {
        return L"\"\"";
    }

    bool needsQuotes = argument.find_first_of(L" \t\n\v\"") != std::wstring::npos;
    if (!needsQuotes) {
        return argument;
    }

    std::wstring result = L"\"";
    size_t backslashes = 0;
    for (size_t i = 0; i < argument.size(); ++i) {
        wchar_t ch = argument[i];
        if (ch == L'\\') {
            ++backslashes;
            continue;
        }
        if (ch == L'"') {
            result.append(backslashes * 2 + 1, L'\\');
            result.push_back(ch);
            backslashes = 0;
            continue;
        }
        result.append(backslashes, L'\\');
        backslashes = 0;
        result.push_back(ch);
    }
    result.append(backslashes * 2, L'\\');
    result.push_back(L'"');
    return result;
}

static std::wstring GetEnvironmentValue(const wchar_t *name)
{
    DWORD length = GetEnvironmentVariableW(name, NULL, 0);
    if (length == 0) {
        return L"";
    }
    std::vector<wchar_t> buffer(length);
    DWORD written = GetEnvironmentVariableW(name, &buffer[0], length);
    if (written == 0 || written >= length) {
        return L"";
    }
    return std::wstring(&buffer[0], written);
}

static bool SetEnvironmentValue(const wchar_t *name, const std::wstring &value)
{
    return SetEnvironmentVariableW(name, value.c_str()) != FALSE;
}

static bool PrependPath(const std::vector<std::wstring> &entries)
{
    std::wstring existing = GetEnvironmentValue(L"PATH");
    std::wstring combined;
    for (size_t i = 0; i < entries.size(); ++i) {
        if (entries[i].empty()) {
            continue;
        }
        if (!combined.empty()) {
            combined += L";";
        }
        combined += entries[i];
    }
    if (!existing.empty()) {
        if (!combined.empty()) {
            combined += L";";
        }
        combined += existing;
    }
    return SetEnvironmentValue(L"PATH", combined);
}

static std::wstring ExecutableDirectory()
{
    std::vector<wchar_t> buffer(MAX_PATH);
    DWORD length = GetModuleFileNameW(NULL, &buffer[0], static_cast<DWORD>(buffer.size()));
    while (length == buffer.size()) {
        buffer.resize(buffer.size() * 2);
        length = GetModuleFileNameW(NULL, &buffer[0], static_cast<DWORD>(buffer.size()));
    }
    if (length == 0) {
        return L"";
    }
    std::wstring path(&buffer[0], length);
    size_t slash = path.find_last_of(L"\\/");
    if (slash == std::wstring::npos) {
        return L"";
    }
    return path.substr(0, slash);
}

static bool ConfigureEnvironment(const std::wstring &bundleRoot)
{
    std::wstring pythonHome = JoinPath(bundleRoot, L"runtime\\python");
    std::wstring pythonPath =
        JoinPath(bundleRoot, L"app") + L";" + JoinPath(bundleRoot, L"runtime\\site-packages");

    if (!SetEnvironmentValue(L"EMBEDAGENT_BUNDLE_ROOT", bundleRoot)) {
        return false;
    }
    if (!SetEnvironmentValue(L"PYTHONHOME", pythonHome)) {
        return false;
    }
    if (!SetEnvironmentValue(L"PYTHONPATH", pythonPath)) {
        return false;
    }
    if (!SetEnvironmentValue(L"PYTHONNOUSERSITE", L"1")) {
        return false;
    }

    if (GetEnvironmentValue(L"EMBEDAGENT_HOME").empty()) {
        std::wstring userProfile = GetEnvironmentValue(L"USERPROFILE");
        if (!userProfile.empty()) {
            SetEnvironmentValue(L"EMBEDAGENT_HOME", JoinPath(userProfile, L".embedagent"));
        }
    }

    std::vector<std::wstring> pathEntries;
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\git\\cmd"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\git\\bin"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\rg"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\ctags"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\llvm\\bin"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\llvm\\libexec"));
    return PrependPath(pathEntries);
}

static std::wstring BuildCommandLine(
    const std::wstring &pythonExe,
    const std::wstring &guiScript,
    int argc,
    wchar_t **argv)
{
    std::wstring command = QuoteArgument(pythonExe) + L" " + QuoteArgument(guiScript);
    for (int i = 1; i < argc; ++i) {
        command += L" ";
        command += QuoteArgument(argv[i]);
    }
    return command;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int)
{
    std::wstring bundleRoot = ExecutableDirectory();
    if (bundleRoot.empty()) {
        return Fail(L"Unable to determine the EmbedAgent bundle root.", 1);
    }

    std::wstring pythonExe = JoinPath(bundleRoot, kPythonRelativePath);
    std::wstring guiScript = JoinPath(bundleRoot, kGuiScriptRelativePath);
    std::wstring webview2Exe = JoinPath(bundleRoot, kWebView2RelativePath);

    if (!FileExists(pythonExe)) {
        return Fail(
            L"Bundled Python runtime not found:\n" + pythonExe +
                L"\n\nRepair or rebuild the offline bundle.",
            1);
    }
    if (!FileExists(guiScript)) {
        return Fail(
            L"GUI launcher script not found:\n" + guiScript +
                L"\n\nRepair or rebuild the offline bundle.",
            1);
    }
    if (!FileExists(webview2Exe)) {
        return Fail(
            L"Bundled Fixed Version WebView2 runtime not found:\n" + webview2Exe +
                L"\n\nGUI does not fall back to IE11. Use TUI/CLI or repair the bundle.",
            1);
    }
    if (!ConfigureEnvironment(bundleRoot)) {
        return Fail(L"Failed to configure the EmbedAgent bundle environment.", 1);
    }

    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == NULL) {
        return Fail(L"Failed to parse command-line arguments.", 1);
    }

    std::wstring commandLine = BuildCommandLine(pythonExe, guiScript, argc, argv);
    LocalFree(argv);

    std::vector<wchar_t> mutableCommand(commandLine.begin(), commandLine.end());
    mutableCommand.push_back(L'\0');

    STARTUPINFOW startupInfo;
    ZeroMemory(&startupInfo, sizeof(startupInfo));
    startupInfo.cb = sizeof(startupInfo);

    PROCESS_INFORMATION processInfo;
    ZeroMemory(&processInfo, sizeof(processInfo));

    BOOL created = CreateProcessW(
        pythonExe.c_str(),
        &mutableCommand[0],
        NULL,
        NULL,
        TRUE,
        0,
        NULL,
        bundleRoot.c_str(),
        &startupInfo,
        &processInfo);

    if (!created) {
        DWORD error = GetLastError();
        return Fail(
            L"Failed to start the EmbedAgent GUI process:\n" + pythonExe +
                L"\n\n" + LastErrorMessage(error),
            1);
    }

    WaitForSingleObject(processInfo.hProcess, INFINITE);
    DWORD exitCode = 1;
    GetExitCodeProcess(processInfo.hProcess, &exitCode);
    CloseHandle(processInfo.hThread);
    CloseHandle(processInfo.hProcess);
    return static_cast<int>(exitCode);
}
