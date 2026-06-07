# Installing Bun for Linky on Windows

## What Bun Is

Bun is a JavaScript and TypeScript runtime, package manager, test runner, and
script runner. In this project it is the expected package manager and command
runner for the monorepo workspaces.

The root `package.json` declares:

```json
"packageManager": "bun@1.3.9"
```

That means local development should use Bun 1.3.9 unless there is a specific
reason to upgrade the workspace.

## Our Windows Setup

We installed Bun as a portable binary inside the project workspace instead of
using the global installer. This kept the setup self-contained and avoided
writing development tooling into the user profile on `C:`.

Workspace:

```text
D:\data_codex\linky\linky-main
```

Portable Bun location:

```text
D:\data_codex\linky\linky-main\.tools\bun\bun-windows-x64\bun.exe
```

Bun package cache:

```text
D:\data_codex\linky\linky-main\.tools\bun\install-cache
```

The downloaded archive was:

```text
https://github.com/oven-sh/bun/releases/download/bun-v1.3.9/bun-windows-x64.zip
```

After extracting it, we verified the version:

```powershell
.\.tools\bun\bun-windows-x64\bun.exe --version
```

Expected output:

```text
1.3.9
```

Then we installed dependencies with the Bun cache explicitly pointed at the
workspace:

```powershell
$env:BUN_INSTALL_CACHE_DIR='D:\data_codex\linky\linky-main\.tools\bun\install-cache'
$env:npm_config_cache='D:\data_codex\.cache\npm'
$env:TEMP='D:\data_codex\.tmp'
$env:TMP='D:\data_codex\.tmp'
.\.tools\bun\bun-windows-x64\bun.exe install
```

This created `node_modules` in the workspace:

```text
D:\data_codex\linky\linky-main\node_modules
```

## Node.js Requirement

Vite 7 requires Node.js `20.19+` or `22.12+`. The machine had a system Node.js
`20.15.1`, which produced this warning:

```text
You are using Node.js 20.15.1. Vite requires Node.js version 20.19+ or 22.12+.
```

The dev server could start, but it used the system Node.js from `C:\Program
Files\nodejs`, which we wanted to avoid.

To keep runtime tooling under `D:\data_codex`, we installed portable Node.js
22.12.0 into the workspace:

```text
D:\data_codex\linky\linky-main\.tools\node\node-v22.12.0-win-x64\node.exe
```

Downloaded archive:

```text
https://nodejs.org/dist/v22.12.0/node-v22.12.0-win-x64.zip
```

Verified with:

```powershell
.\.tools\node\node-v22.12.0-win-x64\node.exe --version
```

Expected output:

```text
v22.12.0
```

## Starting the Local Dev Server

The web app dev server is started through Bun, but Vite itself runs on Node.js.
For that reason, the `PATH` used to start the server must put portable Node.js
and portable Bun first.

The effective startup command was:

```powershell
set PATH=D:\data_codex\linky\linky-main\.tools\node\node-v22.12.0-win-x64;D:\data_codex\linky\linky-main\.tools\bun\bun-windows-x64;%SystemRoot%\System32;%SystemRoot%
set TEMP=D:\data_codex\.tmp
set TMP=D:\data_codex\.tmp
set BUN_INSTALL_CACHE_DIR=D:\data_codex\linky\linky-main\.tools\bun\install-cache
cd /d D:\data_codex\linky\linky-main
.\.tools\bun\bun-windows-x64\bun.exe run dev -- --host 127.0.0.1 --port 5173
```

Local app URL:

```text
http://127.0.0.1:5173
```

In the Codex desktop environment, long-running shell child processes may be
cleaned up when the tool call ends. To keep the Vite server alive, we launched
it as a separate Windows process and redirected logs into the workspace:

```text
D:\data_codex\linky\linky-main\.tools\bun\web-app-dev.out.log
D:\data_codex\linky\linky-main\.tools\bun\web-app-dev.err.log
```

## Issues We Hit

### Bun Was Not on PATH

`bun --version` failed because Bun was not installed globally or available in
the shell `PATH`.

We avoided the global installer and used the official Windows release zip
instead.

### Global Cache Directory Was Not Writable

Creating `D:\data_codex\.cache\bun` from the sandboxed shell failed with a
permission error.

We kept the Bun cache inside the writable project workspace instead:

```text
D:\data_codex\linky\linky-main\.tools\bun\install-cache
```

### Vite Used System Node.js

The first successful dev server run used:

```text
C:\Program Files\nodejs\node.exe
```

That violated the local-only setup rule. We stopped that server and added
portable Node.js under `.tools\node`, then started Vite with a `PATH` that
prefers the workspace Node.js.

### PowerShell `Start-Process` Had a PATH Collision

PowerShell reported:

```text
Item has already been added. Key in dictionary: Path, key being added: PATH
```

This came from duplicate `Path` / `PATH` environment keys in the process
environment. We worked around it by normalizing the process environment for the
current command before using `Start-Process`, and later used Windows process
creation for the long-running dev server.

### Background Processes Were Cleaned Up

Processes started directly as children of the Codex shell did not reliably stay
alive after the tool call ended.

We used Windows process creation to launch the dev server independently and
wrote logs to files under `.tools\bun`.

## Verification

The local server was verified with an HTTP request:

```text
200 OK
```

The listening Vite process was verified to use portable Node.js from the
workspace:

```text
D:\data_codex\linky\linky-main\.tools\node\node-v22.12.0-win-x64\node.exe
```

The app opened at:

```text
http://127.0.0.1:5173
```

